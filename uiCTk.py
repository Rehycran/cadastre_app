from tkinter import END, StringVar, IntVar, filedialog, BooleanVar, PhotoImage, Frame

from customtkinter import CTk, CTkLabel, CTkEntry, CTkFrame, CTkSlider, CTkButton, CTkCheckBox, CTkScrollableFrame, CTkSwitch, CTkProgressBar
import customtkinter
from CTkListbox import CTkListbox

from tkintermapview import TkinterMapView, canvas_button

from pyproj import Transformer
from math import ceil
import re
import threading
import os 
from pathlib import Path
import requests


from .config import TEXT_FONT, HEADER_FONT, BUTTON_FONT, ENTRY_FONT, DEFAULT_CRS, DEFAULT_STEP, INFO_FONT, MARKER_ICON_PATH, WFS_LAYERS
from .geocode import geocode, autocomplete, Address, inverse_geocode
from .crsmap import epsg_from_postcode
from .wfs import fetch_layer, fetch_alti
from .dxfwriter import create_dxf


def normalize_decimal(text : str) -> float | None :
    try :
        return float(text.strip().replace(",","."))
    except ValueError :
        return None

def check_coordinates(address : str) -> tuple[float, float] | None :
    blank_separator = [x for x in address.split(" ") if len(x)]
    comma_separator = [x for x in address.split(",") if len(x)]
    if len(blank_separator) == 2 :
        lat, lon = (normalize_decimal(x) for x in blank_separator)
        if None not in (lat, lon) :
            return (lat, lon)
            
    elif len(comma_separator) == 2 :
        lat, lon = (normalize_decimal(x) for x in comma_separator)
        if None not in (lat, lon) :
            return (lat, lon)
    else :
        return None

def bbox_meters_to_degree(lat : float, lon : float,
                          delta_lat : float, delta_lon : float,
                          address = None
                          ):
    if isinstance(address, Address) :
        t1 = Transformer.from_crs("EPSG:4326", epsg_from_postcode(address), always_xy=True)
        t2 = Transformer.from_crs(epsg_from_postcode(address), "EPSG:4326", always_xy=True)
    else :
        t1 = Transformer.from_crs("EPSG:4326", DEFAULT_CRS, always_xy=True)
        t2 = Transformer.from_crs(DEFAULT_CRS, "EPSG:4326", always_xy=True)
    x, y = t1.transform(lon, lat)
    [(x1,y1), (x2,y2), (x3, y3), (x4,y4)] = [t2.transform(x-delta_lon, y-delta_lat),
            t2.transform(x+delta_lon, y-delta_lat),
            t2.transform(x+delta_lon, y+delta_lat),
            t2.transform(x-delta_lon, y+delta_lat)
            ]
    return [(y1, x1), (y2, x2), (y3, x3), (y4,x4)]

def select_filepath(address_label: str="") -> str | None :
    safe_name = re.sub(r'[\\/*?:"<>|]', "_", address_label)
    file_path = filedialog.asksaveasfilename(title="Choisir un dossier pour enregister les fichiers", initialfile=safe_name,defaultextension=".dxf")
    return file_path or None

def get_all_children(widget):
    children = widget.winfo_children()
    all_children = []

    for child in children:
        all_children.append(child)
        all_children.extend(get_all_children(child))  # récursion

    return all_children

def freeze_slider(slider) :
    slider._canvas.bind("<Button-1>", lambda e: "break")
    slider._canvas.bind("<B1-Motion>", lambda e: "break")
    slider._canvas.bind("<ButtonRelease-1>", lambda e: "break")
    
    slider.configure(command=None)

customtkinter.set_default_color_theme("blue")
customtkinter.set_appearance_mode("system")

class App(CTk) :
    def __init__(self) :
        super().__init__()
        
        #window config
        self.geometry(f'1400x900+{int(self.winfo_screenwidth()/2-700)}+{int(self.winfo_screenheight()/2-450)}')
        self.title("Import parcelle et bati3D")
        self.minsize(750,500)
        
        #cancellation event init
        self.cancel_event = None
        
        #Adress searching values
        self.searched_addr = StringVar()
        self.candidates_listvariable = StringVar(value = str([" "]))
        self.selected_addr = None
        self.debounce_id = None #used to avoid requesting autocomplete too often 
        
        #Area defining values
        self.distance_var_x = IntVar(value=100)
        self.distance_var_y = IntVar(value=100)
        self.poly=None
        self.lat=None
        self.lon=None
        self.lock_status = "unlock"
        
        #Alti points special values
        self.distance_step = IntVar(value=DEFAULT_STEP)
        self.calculated_pts = StringVar(value=f"m. Soit ~{(ceil(self.distance_var_x.get()*2/self.distance_step.get())+1)*(1+ceil(self.distance_var_y.get()*2/self.distance_step.get()))} points à créer")
        
        #Selected layer values
        self.available_layers = {}
        for layer_name, layer_value in WFS_LAYERS.items() :
            self.available_layers[layer_name] = (
                layer_value[0],
                BooleanVar(value=layer_value[1])
            )
        self.points_alti = BooleanVar(value=True)
        
        
        
        self.main_layout()

#---------General window configuration---------
    def focus_click(self, event):#Used to hode the dropdown on click elsewhere
        if hasattr(event.widget, "focus_set") :
            event.widget.focus_set()
        else :
            self.focus_set()

    def main_layout(self) :
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        
        
        self.bind("<Button-1>", self.focus_click)
        
        self.menu_layout()
        self.build_search_block()
        self.build_slider_block()
        self.build_layer_block()
        self.build_download_block()
        self.map_layout()



#---------Left menu configuration---------
    def menu_layout(self) : 
        self.menu = CTkFrame(master=self,
                        border_color=("#BABABA","#363636"),
                        border_width=3,
                        fg_color=("gray93","gray15")
                        )
        self.menu.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        self.menu.grid_columnconfigure(0, weight=0, minsize=640)

#Search bar, button and candidates dropdown
    def build_search_block(self):
        self.search_frame = CTkFrame(self.menu, fg_color="transparent")
        self.search_frame.grid(row=1, sticky="new", padx=35, pady=(60, 0))
        self.search_frame.grid_columnconfigure(0, weight=1)

        self.search_hint = CTkLabel(
            self.search_frame,
            text="Adresse ou coordonnées",
            font=HEADER_FONT,
        )
        self.search_hint.grid(row=0, columnspan=2, sticky="w", pady=(0, 10))

        self.search_bar = CTkEntry(
            self.search_frame,
            font=ENTRY_FONT,
            textvariable=self.searched_addr,
        )
        self.search_bar.grid(row=1, column=0, sticky="we", padx=(5, 0))

        self.search_button = CTkButton(
            self.search_frame,
            text="🔍 Recherche",
            width=140,
            font=BUTTON_FONT,
            command=self.search_address,
        )
        self.search_button.grid(row=1, column=1, sticky="e", padx=(5, 0))

        # dropdown created once
        self.search_dropdown = CTkListbox(
            master=self,
            listvariable=self.candidates_listvariable,
            font=ENTRY_FONT,
            height=ENTRY_FONT[1] * 8,
        )
        self.bind_search_widgets()

    def bind_search_widgets(self):
        self.search_bar.bind("<Return>", lambda e: (self.search_button.invoke() if self.search_bar.get() else None))
        self.search_bar.bind("<KeyRelease>", self.on_key_press)
        self.search_bar.bind("<Button-1>", self.on_key_press)
        self.search_bar.bind("<FocusOut>", lambda e: self.hide_dropdown() if self.focus_get() != self.search_dropdown else None)
        self.search_bar.bind("<Escape>", self.hide_dropdown)
        self.search_bar.bind(
            "<Down>",
            lambda e: (
                self.search_dropdown.focus(),
                self.search_dropdown.select(0)
            ) if self.search_dropdown and self.search_dropdown.winfo_exists() else None
        )

        self.search_dropdown.bind("<ButtonRelease-1>", self.select_addr)
        self.search_dropdown.bind("<FocusOut>", self.hide_dropdown)
        self.search_dropdown.bind("<Down>", self.scroll_down)
        self.search_dropdown.bind("<Up>", self.scroll_up)
        self.search_dropdown.bind("<Return>", self.select_addr)
        self.search_dropdown.bind("<Escape>", lambda event : self.search_bar.focus())

    def on_key_press(self, event=None) :
        if event.keysym in ("Escape", "Return") :
            return
        if self.debounce_id is not None :
            self.after_cancel(self.debounce_id)
        
        self.debounce_id = self.after(200, self.search_autocomplete)

    def search_autocomplete(self) :
        candidates = autocomplete(self.searched_addr.get())
        if candidates :
            listvariable = "["+" ".join(['"'+c+'",' for c in candidates])+"]"
            self.candidates_listvariable.set(listvariable)
            self.show_dropdown()

    def show_dropdown(self, event=None) :
        x = self.search_bar.winfo_x() + self.search_frame.winfo_x()+self.menu.winfo_x()
        y = self.search_bar.winfo_y()+self.search_bar.winfo_height()+self.search_frame.winfo_y()+self.menu.winfo_y()
        w = self.search_bar.winfo_width()
        self.search_dropdown.place(x=x, y=y, anchor="nw")
        self.search_dropdown.configure(width=w)
        self.search_dropdown.lift()

    def hide_dropdown(self, event=None) :
        if self.search_dropdown and self.search_dropdown.winfo_exists() :
            self.search_dropdown.place_forget()

    def scroll_down(self, event = None) :
        if self.search_dropdown.curselection() is None :
            self.search_dropdown.select(0)
        
        elif self.search_dropdown.curselection()+1 < self.search_dropdown.size() :
            self.search_dropdown.select(self.search_dropdown.curselection()+1)
            self.search_dropdown.see(self.search_dropdown.curselection())

    def scroll_up(self, event = None) :
        if not self.search_dropdown.curselection() :
            self.search_dropdown.select(0)
        
        elif self.search_dropdown.curselection()-1 >= 0 :
            self.search_dropdown.select(self.search_dropdown.curselection()-1)
            self.search_dropdown.see(self.search_dropdown.curselection())

    def select_addr(self, event=None) :
        if isinstance(self.search_dropdown.get(), str) :
            self.searched_addr.set(self.search_dropdown.get())
        
        self.after(150, self.search_address)
        self.search_bar.focus()
        self.search_bar.icursor(END)

    def search_address(self) :
        geocoded = geocode(self.searched_addr.get())
        
        coords = check_coordinates(self.searched_addr.get().strip())
        if coords is not None :
            self.lat, self.lon = coords
            if -180 < self.lon < 180 and -90 < self.lat < 90 :
                self.draw_poly(self.selected_addr)
                self.draw_marker()
                self.map_widget.set_position(self.lat, self.lon)
                self.map_widget.set_zoom(17)
        
        if isinstance(geocoded, Address) :
            self.selected_addr = geocoded
            self.lat, self.lon = geocoded.lat, geocoded.lon
            self.draw_poly(self.selected_addr)
            self.draw_marker()
            self.map_widget.set_position(self.lat, self.lon)
            self.map_widget.set_zoom(17)

#Defining area of interest
    def add_slider_row(self, parent, row, text, var, command):
        label = CTkLabel(parent, text=text, bg_color="transparent", font=TEXT_FONT, anchor="nw")
        label.grid(column=0, row=row, padx=(5, 2), pady=(5 if row > 1 else 0, 0), sticky="nsew")

        slider = CTkSlider(parent, from_=20, to=1000, bg_color="transparent", variable=var, command=command)
        slider.grid(column=1, row=row, sticky="we", pady=(5 if row > 1 else 0, 0))

        entry = CTkEntry(parent, textvariable=var, font=ENTRY_FONT, bg_color="transparent", width=70)
        entry.grid(column=2, row=row, sticky="nsew", padx=(3, 0), pady=(5 if row > 1 else 0, 0))

        unit = CTkLabel(parent, text="m", bg_color="transparent", anchor="w")
        unit.grid(column=3, row=row, padx=10, sticky="nsew", pady=(5 if row > 1 else 0, 0))

        return label, slider, entry, unit

    def build_slider_block(self):
        self.slider_frame = CTkFrame(self.menu, fg_color="transparent")
        self.slider_frame.grid(row=3, sticky="we", padx=35, pady=(30, 0))
        for col in range(4):
            self.slider_frame.grid_columnconfigure(col, weight=1 if col == 1 else 0)

        self.slider_hint = CTkLabel(self.slider_frame, text="Emprise à télécharger ", font=HEADER_FONT, anchor="w")
        self.slider_hint.grid(row=0, columnspan=4, sticky="nsew", pady=(0, 10))

        # lon
        self.add_slider_row(
            parent=self.slider_frame,
            row=1,
            text="lon : ",
            var=self.distance_var_x,
            command=self.update_poly,
        )
        # lat
        self.add_slider_row(
            parent=self.slider_frame,
            row=2,
            text="lat : ",
            var=self.distance_var_y,
            command=self.update_poly,
        )
        

#Layers to download
    def add_layer_box(self, parent, text, variable=None) :
        if text in self.available_layers.keys() :
            variable = self.available_layers[text][1]
        
        check_topo = CTkCheckBox(
            master=parent,
            text=text,
            font=TEXT_FONT,
            checkbox_height=18,
            checkbox_width=18,
            corner_radius=5,
            border_width=2,
            variable=variable
            )
        check_topo.pack(side="top", fill='x',padx=(3,0))

    def build_layer_block(self):
        self.layer_frame = CTkFrame(self.menu, fg_color="transparent")
        self.layer_frame.grid(row=4, sticky="nwe", padx=35, pady=(30,0))
        
        self.layer_header = CTkLabel(
            master=self.layer_frame,
            text="Informations à intégrer",
            font=HEADER_FONT,
            anchor="w"
            )
        self.layer_header.pack(side="top", fill="x", pady=(0,10))
        
        self.pts_alti_frame = CTkFrame(
            self.layer_frame,
            fg_color="transparent"
            )
        self.pts_alti_frame.pack(side="top", anchor="w",pady=(0,3),fill="x")
        
        
        check_alti = CTkSwitch(
            master=self.pts_alti_frame,
            text="Points altimétriques",
            font=TEXT_FONT,
            switch_height=18,
            switch_width=36,
            corner_radius=18,
            border_width=2,
            variable=self.points_alti,
            command=self.update_calculated_pts
            )
        check_alti.pack(side="left",padx=(3,5))
        text1_alti = CTkLabel(self.pts_alti_frame, font=TEXT_FONT, text="au pas de ")
        text1_alti.pack(side="left")
        pas_alti = CTkEntry(self.pts_alti_frame, textvariable=self.distance_step, width=30)
        pas_alti.pack(side="left")
        text2_alti = CTkLabel(self.pts_alti_frame, font=TEXT_FONT, textvariable=self.calculated_pts)
        text2_alti.pack(side="left", anchor="w")
        
        self.distance_var_x.trace_add("write", self.update_calculated_pts)
        self.distance_var_y.trace_add("write", self.update_calculated_pts)
        self.distance_step.trace_add("write", self.update_calculated_pts)
        
        self.layer_simple = CTkFrame(self.layer_frame, fg_color="transparent")
        self.layer_simple.pack(side="top", fill="both")
        
        self.add_layer_box(self.layer_simple,"Batiment")
        self.add_layer_box(self.layer_simple,"Parcelle")

        self.show_button = CTkButton(
            self.layer_frame,
            text="Voir plus",
            fg_color="transparent",
            font=ENTRY_FONT,
            border_color=None,
            text_color=("#154f7c","#2078bc"),
            hover_color=("#b6b6b6","#383838"),
            width=30,
            command=self.show_more
            )
        self.show_button.pack(side="top")
        
        self.layer_scroll = CTkScrollableFrame(
            self.layer_frame,
            fg_color="transparent",
            height=235,
            border_width=0
            )
        for layer_name in WFS_LAYERS :
            self.add_layer_box(self.layer_scroll,layer_name)
        
        self.less_button = CTkButton(
            self.layer_frame,
            text="Voir moins",
            fg_color="transparent",
            font=ENTRY_FONT,
            border_color=None,
            text_color=("#154f7c","#2078bc"),
            hover_color=("#b6b6b6","#383838"),
            width=30,
            command=self.show_less
            )

    def show_more(self) :
        self.layer_simple.pack_forget()
        self.show_button.pack_forget()
        self.layer_scroll.pack(side="top",fill="both")
        self.less_button.pack(side="top")

    def show_less(self) :
        self.layer_scroll.pack_forget()
        self.less_button.pack_forget()
        for layer in self.layer_simple.winfo_children() :
            if layer.cget("text") not in ["Batiment", "Parcelle"] :
                layer.destroy()
        for selected_layer_name, selected_layer_val in self.available_layers.items() :
            if selected_layer_name not in ["Batiment", "Parcelle"] and selected_layer_val[1].get() :
                self.add_layer_box(self.layer_simple,selected_layer_name)
        self.layer_simple.pack(side="top",fill="both")
        self.show_button.pack(side="top")

    def update_calculated_pts(self, *args) :
        try:
            x = self.distance_var_x.get()
            y = self.distance_var_y.get()
            pas = self.distance_step.get()
            n = (1+ceil(x*2/pas))*(1+ceil(y*2/pas))
            self.calculated_pts.set(f"m. Soit ~{n if self.points_alti.get() else "-"} points à créer")
        except Exception:
            self.calculated_pts.set("m. Soit - points à créer")

#Downloading process
    def build_download_block(self):
        self.download_button = CTkButton(
            master=self.menu,
            text="Télécharger DXF",
            font=BUTTON_FONT,
            height=40,
            command=self.download
            )
        self.download_button.grid(row=5, sticky="nsew", padx=100, pady=30)

    def build_progress_bar(self) :
        self.progress_bar = CTkProgressBar(
            master=self.menu,
            width=200,
            height=20,
            mode="indeterminate",
            indeterminate_speed=0.5,
            orientation="horizontal"
            )
        self.progress_bar.grid(row=6, sticky="nsew", padx=100, pady=0)
        self.progress_bar.start()

    def transform_to_cancel(self):
        self.download_button.configure(
            text= "Annuler",
            command=self.on_cancel_clicked,
            fg_color="#594c4c"
            )
        for w in get_all_children(self) :
            try :
                if not w.cget("text") == "Annuler" :
                    w.configure(state="disabled")
            except :
                pass
            if isinstance(w, CTkSlider) :
               freeze_slider(w)
        self.map_overlay = Frame(self.map_frame, bg="", cursor="arrow")
        self.map_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

    def reenable_all(self):
        for w in get_all_children(self) :
            try :
                w.configure(state="normal")
                if isinstance(w, CTkSlider) :
                    w._create_bindings()
                    w.configure(command=self.update_poly)
            except Exception :
                pass
        self.map_overlay.destroy()

    def on_cancel_clicked(self):
        if self.cancel_event is not None:
            self.cancel_event.set()
            
            self.reenable_all()
            self.transform_to_download()
            self.destroy_progress_bar()

    def transform_to_download(self) :
        self.download_button.configure(
            text="Télécharger DXF",
            command=self.download,
            fg_color="#1f6aa5"
            )
        self.reenable_all()

    def destroy_progress_bar(self) :
        if hasattr(self, "progress_bar") and self.progress_bar is not None:
            self.progress_bar.stop()
            self.progress_bar.destroy()
            self.progress_bar = None
            self.transform_to_download()

    def build_open_frame(self, path):
        
        dir_path = Path(path).parent
        
        self.open_frame = CTkFrame(
            master=self.menu,
            height=27,
            fg_color="transparent"
        )
        self.open_frame.grid(row=6, sticky="nsew", padx = 100)
        
        self.open_file = CTkButton(
            master=self.open_frame,
            text="Ouvrir dxf",
            font=BUTTON_FONT,
            command= lambda : os.startfile(str(path))
            )
        self.open_file.pack(side="left", fill="both",expand=True,padx=(0,2))
        
        self.open_dir = CTkButton(
            master=self.open_frame,
            text="Ouvrir dossier",
            font=BUTTON_FONT,
            command= lambda : os.startfile(str(dir_path))
            )
        self.open_dir.pack(side="left", fill="both",expand=True,padx=(2,0))
        
    def http_error_feedback(self, error = "") :
        fulltext = error
        textlist=[]
        if len(fulltext) > 45 :
            text_block = "\n".join(fulltext[i:i+45] for i in range(0, len(fulltext), 45))
        else :
            text_block = fulltext
            
        self.error_msg = CTkLabel(
            master=self.menu,
            text="Essayez de relancer le téléchargement\n\n"+"erreur : \n"+text_block,
            font=INFO_FONT
        )
        self.error_msg.grid(row=7, sticky="nsew")
        
    def download(self):
        
        if self.poly is None :
            return
        
        (y1, x1), (y2, x2), (y3, x3), (y4,x4) = bbox_meters_to_degree(
                self.lat,
                self.lon,
                self.distance_var_y.get(),
                self.distance_var_x.get(),
                self.selected_addr
                )
        bbox = (y1, x1, y3, x3)
        bbox_polygon=((x1, y1), (x2,y2), (x3,y3), (x4,y4))
        
        selected_layers = {x:y[0] for x,y in self.available_layers.items() if y[1].get()}
        
        if self.selected_addr is None :
            self.selected_addr = inverse_geocode(self.lon, self.lat)
        
        if self.selected_addr is not None :
            file_path = select_filepath(self.selected_addr.label)
        else :
            file_path = select_filepath("")
            
        if not file_path :
            return
        
        self.build_progress_bar()
        self.transform_to_cancel()
        
        self.cancel_event = threading.Event()
        
        def worker() :
            try :
                gdf_dict = {}
                for layer_name, layer_value in selected_layers.items() :
                    gdf_dict[layer_name] = fetch_layer(layer_value, bbox, cancel_event=self.cancel_event)
                
                if self.points_alti.get() :
                    alti_pts = fetch_alti(
                        bbox=bbox,
                        pas_metre=self.distance_step.get(),
                        cancel_event=self.cancel_event
                        )
                else :
                    alti_pts = None
                
                create_dxf(
                    out_path=file_path,
                    bbox_polygon=bbox_polygon,
                    gdf_dict=gdf_dict,
                    gdf_alti=alti_pts,
                    address= self.selected_addr,
                    point_alti=self.points_alti.get(),
                    cancel_event=self.cancel_event
                    )
                
                if Path(file_path).exists() :
                    self.after(0,self.build_open_frame(file_path))
                
            except requests.exceptions.HTTPError as e :
                self.http_error_feedback(str(e))
                
            finally :
                self.after(0,self.destroy_progress_bar)
                self.selected_addr = None
        
        threading.Thread(target=worker, daemon=True).start()
 




#---------Map and map tools---------
    def map_layout(self) :
        self.map_frame = CTkFrame(master=self,
                            border_color=("#BABABA","#363636"),
                            border_width=3,
                            fg_color=("gray93","gray15")
                            )
        self.map_frame.grid(row=0,column=1,padx=(5),pady=5,sticky="nsew")
        
        self.map_frame.grid_rowconfigure(0, weight=1)
        self.map_frame.grid_columnconfigure(0, weight=1)
        
        
        self.map_widget = TkinterMapView(self.map_frame, corner_radius=5)
        self.map_widget.grid(padx=5, pady=5, sticky="nsew")
        
        plan_ign = (
            "https://data.geopf.fr/wmts?"
            "SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0"
            "&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2"
            "&STYLE=normal"
            "&TILEMATRIXSET=PM_0_19"
            "&FORMAT=image/png"
            "&TILEMATRIX={z}&TILECOL={x}&TILEROW={y}"
            )
        
        self.map_widget.set_tile_server(plan_ign, max_zoom=19)
        self.map_widget.set_position(47.077115, 2.406006)  # Paris, France
        self.map_widget.set_zoom(6)
        
        original_draw = self.map_widget.update_canvas_tile_images
        def draw_with_credit(*args, **kwargs):
            result = original_draw(*args, **kwargs)
            canvas =self.map_widget.winfo_children()[0]
            canvas.delete("map_credit")
            canvas.create_text(
                21,
                self.map_widget.winfo_children()[0].winfo_height()-34,
                text="© IGN – GéoPlateforme",
                fill="white",
                anchor="nw",
                font=INFO_FONT,
                tag="map_credit"
                )
            canvas.create_text(
                20,
                self.map_widget.winfo_children()[0].winfo_height()-35,
                text="© IGN – GéoPlateforme",
                fill="gray40",
                anchor="nw",
                font=INFO_FONT,
                tag="map_credit"
                )

            return result
        self.map_widget.update_canvas_tile_images = draw_with_credit
        
        self.map_widget.canvas.bind("<B1-Motion>", self.update_poly, add='+')
        self.map_widget.canvas.bind("<Double-Button-1>", self.double_click_map)
        self.map_widget.canvas.bind(
            "<Double-Button-1>", lambda  event : 
                self.lock_unlock_poly() if self.lock_status == "unlock" else None,
                add = "+"
            )
        
        self.marker_icon = PhotoImage(file=MARKER_ICON_PATH)
        
        self.lock_button = canvas_button.CanvasButton(
            self.map_widget,
            (20,140),
            text='🔓',
            command=self.lock_unlock_poly
            )

    def draw_poly(self, address) :
        self.map_widget.delete_all_polygon()
        self.poly = self.map_widget.set_polygon(
            bbox_meters_to_degree(
                self.lat,
                self.lon,
                self.distance_var_y.get(),
                self.distance_var_x.get(),
                address
                ),
            fill_color = "#EF6464",
            outline_color = "red",
            border_width = 5
            )

    def update_poly(self, event=None) :
        if self.lock_status == "unlock" :
            self.lat, self.lon = self.map_widget.get_position() 
        else :
            self.lat, self.lon = (
                (self.poly.position_list[0][0]+self.poly.position_list[2][0])/2,
                (self.poly.position_list[0][1]+self.poly.position_list[2][1])/2
                )
        if self.poly :
            if self.poly.canvas_polygon in self.map_widget.canvas.find_all() :
                self.draw_poly(self.selected_addr)

    def draw_marker(self) :
        self.map_widget.delete_all_marker()
        self.map_widget.set_marker(
            self.lat,
            self.lon,
            icon=self.marker_icon,
            icon_anchor = "s"
        )

    def lock_unlock_poly(self) :
        if self.lock_status == "unlock" :
            self.lock_status = "lock"
            self.lock_button.text = '🔒'
            self.lock_button.draw()
        else :
            self.lock_status = "unlock"
            self.lock_button.text = '🔓'
            self.lock_button.draw()

    def double_click_map(self, event=None) :
        self.lat, self.lon = self.map_widget.convert_canvas_coords_to_decimal_coords(
                    self.map_widget.mouse_click_position[0],
                    self.map_widget.mouse_click_position[1]
                    )
        self.draw_poly(self.selected_addr)

#---------Main run---------
    def run(self) :
        self.mainloop()