import os, ezdxf, math
from ezdxf.lldxf.const import DXFTableEntryError, DXFTypeError
from ezdxf.entities.xdata import XDataUserDict
from datetime import datetime
from shapely.geometry import Polygon, LineString, Point, MultiPolygon, MultiLineString, MultiPoint
import shapely

from cadastre_app.geometry import fix_geom, geojson_to_simplegeometry, from_crs_to_crs
from cadastre_app.crsmap import epsg_from_postcode
from cadastre_app.config import KELLY_COLOR, WFS_ATTRIB


def first_finite(*vals, default=0.0):
    for v in vals:
        # treat None / '' as missing
        if v is None or v == '':
            continue
        try:
            x = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(x):
            return x
    return default

def add_paperspace_note(doc, address, target_epsg):
    try:
        try:
            ps=doc.layouts.get("Layout1")
            doc.layouts.rename("Layout1","NoteEspacePapier")
        except KeyError:
            ps=doc.layouts.new("NoteEspacePapier")
        note=f"Date: {datetime.now():%Y-%m-%d %H:%M}\nProjection: {target_epsg}\nAdresse: {address}"
        mtext=ps.add_mtext(note,dxfattribs={"style":"Standard","char_height":10.0})
        mtext.set_location((10,145))
    except: pass

def add_attribute_xdata(row, entity,layer_name) :
    with XDataUserDict.entity(entity, name="properties", appid="cadastre_app") as ud :
        for attribute in WFS_ATTRIB[layer_name] :
            try :
                if isinstance(row[attribute], (str, int, float)) :
                    if isinstance(row[attribute], float) and math.isnan(row[attribute]) :
                        continue
                    ud[attribute] = row[attribute]
                else: 
                    continue
            except DXFTypeError :
                continue

def create_dxf(
    out_path,
    bbox_polygon,
    gdf_dict, gdf_alti=None,
    address=None, address_alti=None,
    point_alti=True,
    cancel_event=None
    ):

    bbox_polygon = shapely.Polygon(bbox_polygon)
    
    target_epsg_for_note = epsg_from_postcode(address)
    address_for_note = ""
    if hasattr(address, "label") :
        address_for_note = address.label
    
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    doc = ezdxf.new(dxfversion="R2018")
    msp = doc.modelspace()

    doc.header["$INSUNITS"] = 6 #meters
    doc.header["$MEASUREMENT"] = 1 #metric system
    if address_alti is not None :
        doc.header["$USERR1"] = address_alti
    
    if "cadastre_app" not in doc.appids: doc.appids.add("cadastre_app")

    
    for (layer_name, gdf_geom) ,kelly_rgb in zip(gdf_dict.items(), KELLY_COLOR.values()):
        try :
            layer = doc.layers.get(layer_name)
        except DXFTableEntryError :
            layer = doc.layers.add(name=layer_name)
            layer.rgb = kelly_rgb

        for index, row in gdf_geom.iterrows() :
            points_list, close = geojson_to_simplegeometry(row.geometry, bbox_polygon)
            for points in points_list :
                
                #Cancellation check
                if cancel_event is not None and cancel_event.is_set():
                    return
                
                if isinstance(row.geometry, (MultiPoint, Point)) :
                    for pt in points :
                        pt = from_crs_to_crs(pt[0], pt[1], target_crs=target_epsg_for_note)
                        entity = msp.add_point(pt, dxfattribs={"layer": layer_name})
                        add_attribute_xdata(row, entity, layer_name)
                        
                elif isinstance(row.geometry, (MultiPolygon, Polygon, MultiLineString, LineString)) :
                    pts = [from_crs_to_crs(x,y,target_crs=target_epsg_for_note)+(z,) for x,y,z in points]
                    entity = msp.add_polyline3d(pts, dxfattribs={"layer": layer_name}, close=close)
                    add_attribute_xdata(row, entity, layer_name)
                    

    # --- Points altimetriques ---
    if point_alti :
        if "Point alti" not in doc.layers: 
            doc.layers.add(name="Point alti", color=102)
        if gdf_alti is not None and not getattr(gdf_alti, "empty", True):
            for index, row in gdf_alti.iterrows():
                
                #Cancellation check
                if cancel_event is not None and cancel_event.is_set():
                    return
                
                geom = fix_geom(row.geometry)
                if geom is None or geom.is_empty:
                    continue
                z = first_finite(row.get("z"), default=0.0)
                if z == -99999.0 :
                    continue
                if geom.geom_type == "Point" :
                    x,y = geom.x, geom.y
                    x,y = from_crs_to_crs(x,y,target_crs=target_epsg_for_note)
                    msp.add_point((x,y,z), dxfattribs={"layer": "Point alti"})
                else :
                    continue
                
    add_paperspace_note(doc, address_for_note, target_epsg_for_note)

    return doc.saveas(out_path)
