# -*- coding: utf-8 -*-
"""
cadastre_app.ui
Tkinter UI for the cadastre app:
- geocodes an address (Addok),
- fetches WFS buildings/parcelles in a bbox around the address,
- reprojects to CC zone EPSG based on postcode,
- writes a DXF with two layers (Batiment / Parcelle),
- non-blocking UI with a progress dialog.

Requires sibling modules:
  cadastre_app.config
  cadastre_app.geocode
  cadastre_app.wfs
  cadastre_app.crsmap
  cadastre_app.dxfwriter
"""

import os
from pathlib import Path
import re
import threading
import queue
from tkinter import StringVar, IntVar, filedialog, BooleanVar, Checkbutton

from customtkinter import CTk, CTkToplevel, CTkLabel, CTkButton, CTkEntry, CTkFrame, CTkProgressBar, CTkComboBox, CTkSlider

import geopandas as gpd
from pyproj import Transformer
from shapely.geometry import box

from .config import TEXT_FONT, BUTTON_FONT, ENTRY_FONT, DEFAULT_CRS, DEFAULT_STEP, EMPTY_ALTI, INFO_FONT
from .geocode import geocode, Address
from .wfs import fetch_buildings, fetch_parcelles, fetch_alti
from .crsmap import epsg_from_postcode
from .dxfwriter import write_dxf_two_layers


class App:
    def __init__(self):
        self.root = CTk()
        self.root.title("Import parcelle et bati")
        self.distance_var = IntVar(value=20)
        self.distance_pas = IntVar(value=5)
        self.manual_val = StringVar()
        self.selected = StringVar()
        self._dpi_setup()
        self._contour = True
        self._contour_var = BooleanVar(value=self._contour)
        self._contour_var.trace_add("write", lambda *a: setattr(self, "_contour", self._contour_var.get()))
        self.calculated_pts = StringVar(value= f"  ( {((self.distance_var.get()*2)//self.distance_pas.get()+2)**2} points à créer)")
        self.msg_queue = queue.Queue()
        self._candidates = []
        self._selected_addr = None
        
        self._layout()

        
    # -------- window / DPI --------
    def _dpi_setup(self):
        self.scaling_factor = 1.0
        if self.root.tk.call("tk", "windowingsystem") == "win32":
            from ctypes import windll
            try:
                windll.shcore.SetProcessDpiAwareness(1)
                self.scaling_factor = windll.shcore.GetScaleFactorForDevice(0) / 100.0
            except Exception:
                pass
        sw = int(self.root.winfo_screenwidth() * self.scaling_factor)
        sh = int(self.root.winfo_screenheight() * self.scaling_factor)
        ww, wh = max(560, sw // 5), max(380, sh // 5)
        x, y = (sw - ww) // 2, (sh - wh) // 2
        self.root.geometry(f"{ww}x{wh}+{x}+{y}")
        self.screen_w, self.screen_h = sw, sh

        
    def update_pt_nb(self, *args):
        try:
            d = self.distance_var.get()
            pas = self.distance_pas.get()
            n = ((2*d // pas) + 2) ** 2
            self.calculated_pts.set(f"  ( {n if self._contour else "-"} points à créer)")
        except Exception:
            self.calculated_pts.set("  ( -- points à créer)")
        
    # -------- static layout --------
    def _layout(self):
        r = self.root
        for i in range(5):
            r.rowconfigure(i, weight=1 if i < 4 else 5)
        r.columnconfigure(0, weight=1)

        champ = CTkLabel(r, text=" Entrez l'adresse à rechercher :  ",  font=TEXT_FONT)
        champ.grid(row=0, column=0, padx=8, pady=8, sticky="w")

        self.entree = CTkEntry(r, textvariable=self.manual_val, font=ENTRY_FONT)
        self.entree.grid(row=1, column=0, sticky="new", padx=8)
        
        def _invalidate_if_changed(_evt=None):
            if self._selected_addr and self.manual_val.get().strip() != self._selected_addr.label:
                self._selected_addr = None
        self.entree.bind("<KeyRelease>", _invalidate_if_changed)


        text_distance = CTkLabel(
            r,
            text="Rayon à prendre en compte autour de l'adresse : ",
            font=TEXT_FONT,
        )
        text_distance.grid(row=2, column=0, padx=8, sticky="w")

        slider_frame = CTkFrame(self.root, bg=self.root["bg"])
        slider_frame.grid(row=3, column=0, padx=8, sticky="we")
        slider_frame.columnconfigure(0, weight=1)
        
        
        def integer_callback(value):
            try:
                v = float(value)
            except Exception:
                v = 20
            v = max(20, min(1000, round(v)))
            self.distance_var.set(v)
        

        curseur_distance = CTkSlider(
            slider_frame, from_=20, to=1000, command=integer_callback, variable=self.distance_var
        )
        curseur_distance.grid(row=0, column=0, sticky="we", padx=(8, 6))

        valeur_distance = CTkEntry(slider_frame, textvariable=self.distance_var, font=ENTRY_FONT, width=5)
        valeur_distance.grid(row=0, column=1, sticky="e")

        CTkLabel(slider_frame, text=" m").grid(row=0, column=2, sticky="w", padx=4)

        checkbox_frame = CTkFrame(self.root, bg=self.root["bg"])
        checkbox_frame.grid(row=4, column=0, padx=8, sticky="we",pady=(35,0))
        checkbox_frame.columnconfigure(0, weight=1)
        
        dl_contour_txt = CTkLabel(checkbox_frame, text="Télécharger les points altimétriques : ", font=TEXT_FONT)
        dl_contour_txt.pack(side="left")
        
        chk = Checkbutton(checkbox_frame,variable=self._contour_var, command=self.update_pt_nb)
        chk.pack(side="left")
        
        pas_frame = CTkFrame(self.root, bg=self.root["bg"])
        pas_frame.grid(row=5, column=0, padx=8, sticky="we")
        pas_frame.columnconfigure(0, weight=1)
        
        pas_text_01 = CTkLabel(pas_frame, text="Un point tous les ", font=TEXT_FONT)
        pas_text_01.pack(side="left")
        
        valeur_pas = CTkEntry(pas_frame, textvariable=self.distance_pas, font=ENTRY_FONT, width=2)
        valeur_pas.pack(side="left")
        

        
        pas_text_02 = CTkLabel(pas_frame, text="mètre(s)", font=TEXT_FONT)
        pas_text_02.pack(side="left")
        
        pas_text_03 = CTkLabel(pas_frame, textvariable=self.calculated_pts, font=ENTRY_FONT)
        pas_text_03.pack(side="left")

        self.distance_var.trace_add("write", self.update_pt_nb)
        self.distance_pas.trace_add("write", self.update_pt_nb)
        
        bouton_v = CTkButton(r, text="Valider", command=self._go, font=BUTTON_FONT)
        bouton_v.grid(row=6, column=0, pady=(35,12), sticky="ne", padx=100)
        self.entree.bind("<Return>", lambda event: (bouton_v.invoke() if self.entree.get() else None))
        
        licence = CTkLabel(r,text= "Données issues des dernières mises à jours disponibles sur la Géoplateforme – Licence Ouverte 2.0", font=INFO_FONT,fg="gray35")
        licence.grid(row=7,column=0,sticky="sw")

    # -------- helpers --------
    def meters_bbox_around_lonlat(self, lon, lat, meters, to_metric_crs=DEFAULT_CRS):
        """Transform WGS84 lon/lat to metric CRS and expand a square bbox by `meters` in each direction."""
        t = Transformer.from_crs("EPSG:4326", to_metric_crs, always_xy=True)
        x, y = t.transform(lon, lat)
        d = float(meters)
        return (x - d, y - d, x + d, y + d)

    def select_filepath(self, addr):
        safe_name = re.sub(r'[\\/*?:"<>|]', "_", addr.label)
        folder = filedialog.asksaveasfilename(title="Choisir un dossier pour enregister les fichiers", initialfile=safe_name,defaultextension=".dxf")
        return folder or None

    def prompt_after_save(self, out_path):
        win = CTkToplevel(self.root)
        win.title("Export DXF")
        win.transient(self.root)
        win.grab_set()
        w, h = 460, 200
        x = (self.screen_w - w) // 2
        y = (self.screen_h - h) // 2
        win.geometry(f"{w}x{h}+{x}+{y}")
        CTkLabel(win, text="Fichier créé avec succès", font=TEXT_FONT).pack(padx=16, pady=(18, 6))
        CTkLabel(win, text=os.path.basename(out_path), font=ENTRY_FONT).pack(padx=16, pady=(0, 12))
        btns = CTkFrame(win)
        btns.pack(padx=16, pady=12, fill="x")

        def quitter():
            try:
                self.root.quit()
            finally:
                self.root.destroy()

        def continuer():
            win.destroy()
        
        def open_folder(out_path) :
            folder_path = Path(out_path).parent
            print(folder_path)
            if folder_path.exists():
                os.startfile(str(folder_path))

        CTkButton(btns, text="Continuer", command=continuer, font=BUTTON_FONT).pack(
            side="left", expand=True, fill="x", padx=0
        )
        CTkButton(btns, text="Ouv. dossier", command=lambda p=out_path: open_folder(p), font=BUTTON_FONT).pack(
            side="left", expand=True, fill="x", padx=12
        )
        CTkButton(btns, text="Quitter", command=quitter, font=BUTTON_FONT).pack(
            side="left", expand=True, fill="x", padx=0
        )

    def _progress_window(self):
        w = CTkToplevel(self.root)
        w.overrideredirect(True)
        ww = max(360, self.screen_w // 6)
        wh = 120
        x = (self.screen_w - ww) // 2
        y = (self.screen_h - wh) // 2
        w.geometry(f"{ww}x{wh}+{x}+{y}")
        frame = CTkFrame(w, padding=4, style="cad.Progress.TFrame")
        frame.pack(fill="both", expand=True)
        bar = CTkProgressBar(frame, orient="horizontal", mode="indeterminate")
        bar.place(rely=0.5, relheight=0.5, relwidth=1.0)
        label = CTkLabel(frame, text="Connexion WFS …", font=TEXT_FONT, bg="grey")
        label.place(relheight=0.5, relwidth=1.0)
        return w, bar, label

    def _start_worker(self, addr) :
        out_path = self.select_filepath(addr)
        if not out_path:
            return

        pw, bar, label = self._progress_window()

        def update_label(msg):
            self.msg_queue.put(msg)

        def worker():
            try:
                # 1) bbox in EPSG:2154 (meters)
                bbox_2154 = self.meters_bbox_around_lonlat(addr.lon, addr.lat, self.distance_var.get(), DEFAULT_CRS)
                minx, miny, maxx, maxy = bbox_2154
                bbox_poly = box(minx, miny, maxx, maxy)

                # 2) fetch layers
                update_label("Récupération des bâtiments …")
                gdf_b = fetch_buildings(bbox_2154, crs=DEFAULT_CRS, max_per_page=5000)
                update_label("Récupération des parcelles …")
                gdf_p = fetch_parcelles(bbox_2154, crs=DEFAULT_CRS, max_per_page=5000)

                # 3) target EPSG from postcode
                target_epsg = epsg_from_postcode(addr.postcode)
                
                #3b) points alti
                if self._contour :
                    update_label("Récupération des points altimetriques …")
                    gdf_alti = fetch_alti(addr, self.distance_var.get(), self.distance_pas.get())
                else :
                    gdf_alti = EMPTY_ALTI.copy()
                    
                if gdf_b.empty and gdf_p.empty and gdf_alti.empty :
                    raise RuntimeError("Aucune entité trouvée dans l’emprise demandée.")
                
                # 4) reproject
                gdf_b2 = gdf_b.to_crs(target_epsg) if not gdf_b.empty else gdf_b
                gdf_p2 = gdf_p.to_crs(target_epsg) if not gdf_p.empty else gdf_p
                gdf_alti2 = gdf_alti.to_crs(target_epsg) if not gdf_alti.empty else gdf_alti

                # 5) write DXF
                #safe_name = re.sub(r'[\\/*?:"<>|]', "_", addr.label)
                #out_path = os.path.join(out_dir, f"cadastre-{safe_name}.dxf")
                nb, npoly, pt_alti = write_dxf_two_layers(
                    gdf_b2,
                    gdf_p2,
                    gdf_alti2,
                    out_path,
                    layer_building="Batiment",
                    layer_parcelle="Parcelle",
                    layer_point_alti="Point_Altimetrique",
                    address_for_note=addr.label,
                    target_epsg_for_note=target_epsg,
                    point_alti=self._contour
                )
                update_label(f"Terminé : {nb} bâtiments, {npoly} parcelles, {pt_alti} points altimétriques (CRS {target_epsg})")
                # success prompt on main thread
                self.root.after(0, lambda: self.prompt_after_save(out_path))    
            except Exception as e:
                update_label(f"ERREUR : {e}")
            finally:
                bar.stop()
                # destroy after a small delay (let the last message be visible)
                self.root.after(1200, pw.destroy)

        def poll():
            # periodically update label from queue
            try:
                while True:
                    m = self.msg_queue.get_nowait()
                    label.configure(text=m)
            except queue.Empty:
                pass
            finally:
                if pw.winfo_exists():
                    self.root.after(150, poll)

        # disable main widgets while working
        for w in self.root.winfo_children():
            try:
                w.configure(state="disabled")
            except Exception:
                pass

        def reenable_all(_evt=None):
            for w in self.root.winfo_children():
                try:
                    w.configure(state="normal")
                except Exception:
                    pass

        pw.bind("<Destroy>", reenable_all)
        bar.start()
        threading.Thread(target=worker, daemon=True).start()
        poll()

    # -------- actions --------
    def _go(self):
        address_input = self.manual_val.get().strip()
        if not address_input:
            return
        
        if self._selected_addr and address_input == self._selected_addr.label:
            self._start_worker(self._selected_addr)
            return
        
        res = geocode(address_input, limit=20)
        if res is None:
            self._set_champ("Adresse introuvable, essayez à nouveau : ")
            return

        if isinstance(res, list):
            # Multiple choices: show a combobox
            self._candidates = res
            self._show_choice([a.label for a in res])
            return

        self._selected_addr = res
        self.manual_val.set(res.label)
        self._start_worker(res)

    # -------- multiple choice view --------
    def _show_choice(self, labels):
        # Clear rows ≥ 1 and show a simple combobox to pick an address
        for child in list(self.root.grid_slaves()):
            info = child.grid_info()
            if int(info.get("row", -1)) >= 0:
                child.grid_forget()
                
        wrapper = CTkFrame(self.root, bg=self.root["bg"])
        wrapper.grid(row=0, column=0, sticky="nsew", padx=0, pady=20)
        wrapper.columnconfigure(0, weight=1)

        CTkLabel(wrapper, text="Sélectionnez l'adresse dans la liste:", font=TEXT_FONT).grid(
            row=1, column=0, padx=8, pady=8, sticky="w"
        )
        cb = CTkComboBox(wrapper, values=labels, font=ENTRY_FONT)
        cb.grid(row=2, column=0, padx=8, sticky="new")
        cb.bind("<<ComboboxSelected>>", lambda e: self.entree.delete(0, "end"))

        CTkButton(
            wrapper, text="Valider", command=lambda: self._use_choice(cb.get()), font=BUTTON_FONT
        ).grid(row=3, column=0, pady=8, sticky="ne", padx=100)
        
        CTkLabel(wrapper, text="Ou faites une nouvelle recherche :", font=TEXT_FONT).grid(
            row=4, column=0, padx=8, pady=8, sticky="w"
        )
        
        self.entree = CTkEntry(wrapper, textvariable=self.manual_val, font=ENTRY_FONT)
        self.entree.grid(row=5, column=0, sticky="new", padx=8)
        
        CTkButton(
            wrapper, text="Rechercher", command=self._go, font=BUTTON_FONT
        ).grid(row=6, column=0, pady=8, sticky="ne", padx=100)

    def _use_choice(self, text):
        if not text:
            return
        
        addr = next((a for a in self._candidates if a.label == text), None)
        
        
        #if addr is None:
        prev_dist = self.distance_var.get()
        # Reset to original layout and reuse normal flow
        for w in self.root.grid_slaves():
            w.grid_forget()
        self._layout()
        self.distance_var.set(prev_dist)
        self.entree.insert(0, text)
        self._selected_addr = addr
        
        #else :
        #    self._start_worker(addr)

    # -------- misc --------
    def _set_champ(self, msg):
        for w in self.root.winfo_children():
            if str(w).endswith(".champ"):
                w.configure(text=msg)
                break

    def run(self):
        self.root.mainloop()
