from tkinter import END, Label, StringVar, IntVar, filedialog, BooleanVar, Checkbutton, Canvas, PhotoImage, Listbox

from customtkinter import CTk, CTkLabel, CTkEntry, CTkFrame, CTkSlider, CTkButton, CTkCheckBox
import customtkinter
from CTkListbox import * 

from tkintermapview import TkinterMapView, canvas_button

from pyproj import Transformer

from .config import TEXT_FONT, HEADER_FONT, BUTTON_FONT, ENTRY_FONT, DEFAULT_CRS, DEFAULT_STEP, EMPTY_ALTI, INFO_FONT, MARKER_ICON_PATH
from .geocode import geocode, autocomplete, Address
from .crsmap import epsg_from_postcode


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
        t1 = Transformer.from_crs("EPSG:4326", epsg_from_postcode(address.postcode), always_xy=True)
        t2 = Transformer.from_crs(epsg_from_postcode(address.postcode), "EPSG:4326", always_xy=True)
        print(address.label)
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

customtkinter.set_default_color_theme("blue")
customtkinter.set_appearance_mode("system")

class App(CTk) :
    def __init__(self) :
        super().__init__()
        
        #window config
        self.geometry(f'1400x900+{int(self.winfo_screenwidth()/2-700)}+{int(self.winfo_screenheight()/2-450)}')
        self.title("Import parcelle et bati3D")
        self.minsize(750,500)
        
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
        self.distance_step = IntVar(value=5)
        self.calculated_pts = StringVar(value= f"({((self.distance_var_x.get()*self.distance_var_y.get())//self.distance_step.get()+2)**2} points à créer)")
        
        #Selected layer values
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
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=3)
        
        
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
        self.menu.grid_columnconfigure(0, weight=1)

#Search bar, button and candidates dropdown
    def build_search_block(self):
        self.search_frame = CTkFrame(self.menu, fg_color="transparent")
        self.search_frame.grid(row=1, sticky="nsew", padx=35, pady=(60, 0))
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
    def add_layer_box(self, text, variable) :
        self.check_topo = CTkCheckBox(
            self.layer_frame,
            text=text,
            font=TEXT_FONT,
            checkbox_height=18,
            checkbox_width=18,
            corner_radius=5,
            border_width=2,
            variable=variable
            )
        self.check_topo.pack(side="top", fill='x',padx=(3,0))

    def build_layer_block(self):
        self.layer_frame = CTkFrame(self.menu, fg_color="transparent")
        self.layer_frame.grid(row=4, sticky="nswe", padx=35, pady=(30,0))
        
        self.layer_header = CTkLabel(
            master=self.layer_frame,
            text="Informations à intégrer",
            font=HEADER_FONT,
            anchor="w"
            )
        self.layer_header.pack(side="top", fill="x", pady=(0,10))
        
        self.add_layer_box("Parcelles",None)
        self.add_layer_box("Bâtiments",None)
        self.add_layer_box("Points altimétriques", self.points_alti)

#Downloading process
    def build_download_block(self):
        self.download_button = CTkButton(
            master=self.menu,
            text="Télécharger DXF",
            font=BUTTON_FONT,
            height=40,
            command=self.download
            )
        self.download_button.grid(row=5, sticky="nsew", padx=50, pady=30)

    def download(self):
        pass



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