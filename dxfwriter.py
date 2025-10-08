import os, ezdxf
from datetime import datetime
from .geometry import polygon_to_3d_polylines, fix_geom
import math

def _is_finite3(p):
    x, y, z = p
    return all(map(math.isfinite, (x, y, z)))

def _clean_pts(pts):
    # drop NaN/inf and consecutive duplicates
    out = []
    last = None
    for p in pts:
        if not _is_finite3(p):
            continue
        if last is None or (p[0] != last[0] or p[1] != last[1] or p[2] != last[2]):
            out.append(p)
            last = p
    return out

def _safe_add_polyline3d(msp, pts, layer, close=False):
    pts = _clean_pts(pts)
    # need at least two vertices, three if you want to close
    if len(pts) < 2:
        return None
    pl = msp.add_polyline3d(pts, dxfattribs={"layer": layer})
    if close and len(pts) >= 3:
        pl.close(True)
    return pl

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
        note=f"Date: {datetime.now():%Y-%m-%d %H:%M}\\nEPSG: {target_epsg}\\nAdresse: {address}"
        mtext=ps.add_mtext(note,dxfattribs={"style":"Standard","char_height":10.0})
        mtext.set_location((10,145))
    except: pass

def write_dxf_two_layers(
    gdf_b, gdf_p, gdf_alti, out_path,
    layer_building="Batiment", layer_parcelle="Parcelle", layer_point_alti="Point_Altimetrique",
    close_polylines=True, address_for_note="", target_epsg_for_note="", point_alti=True
    ):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()

    # layers & header
    if layer_building not in doc.layers: doc.layers.add(name=layer_building, color=13)
    if layer_parcelle not in doc.layers: doc.layers.add(name=layer_parcelle, color=153)
    if layer_point_alti not in doc.layers and point_alti: doc.layers.add(name=layer_point_alti, color=106)
    doc.header["$INSUNITS"] = 6   # meters
    doc.header["$MEASUREMENT"] = 1
    if "BDTOPO" not in doc.appids: doc.appids.add("BDTOPO")

    n_build = n_parc = n_pt = 0

    # --- Buildings (Polygon/MultiPolygon expected) ---
    if gdf_b is not None and not gdf_b.empty:
        for _, row in gdf_b.iterrows():
            geom = fix_geom(row.geometry)
            if geom is None or geom.is_empty:
                continue
            if point_alti :
                z = first_finite(
                        row.get("altitude_maximale_toit"),
                        row.get("altitude_minimale_toit"),
                        row.get("hauteur"),
                        default=0.0
                    )
            else :
                z = first_finite(row.get("hauteur"), default=0.0)
            if not math.isfinite(z):
                z = 0.0
            for pts in polygon_to_3d_polylines(geom, z):
                pl = _safe_add_polyline3d(msp, pts, layer_building, close=(close_polylines and len(pts) >= 3))
                if pl is None:
                    continue
#                try:
#                    pl.set_xdata("BDTOPO", [(1000, "hauteur_m"), (1040, float(z))])
#                except ezdxf.DXFError:
#                    pass
                n_build += 1

    # --- Parcelles (Polygon/MultiPolygon expected) ---
    if gdf_p is not None and not gdf_p.empty:
        for _, row in gdf_p.iterrows():
            geom = fix_geom(row.geometry)
            if geom is None or geom.is_empty:
                continue
            for pts in polygon_to_3d_polylines(geom, 0.0):
                pl = _safe_add_polyline3d(msp, pts, layer_parcelle, close=(close_polylines and len(pts) >= 3))
                if pl is None:
                    continue
                n_parc += 1

    # --- Courbes de niveau (LineString/MultiLineString expected) ---
    if point_alti :
        if gdf_alti is not None and not getattr(gdf_alti, "empty", True):
            for _, row in gdf_alti.iterrows():
                geom = fix_geom(row.geometry)
                if geom is None or geom.is_empty:
                    continue
                z = first_finite(row.get("z"), default=0.0)
                if z == -99999.0 :
                    continue
                # polygon_to_3d_polylines must support LineString/MultiLineString
                if geom.geom_type == "Point" :
                    x,y = geom.x, geom.y
                    pl = msp.add_point((x,y,z), dxfattribs={"layer": layer_point_alti})  # never close contours
                else :
                    continue
#                    try:
#                        pl.set_xdata("BDTOPO", [(1000, "altitude_m"), (1040, float(z))])
#                    except ezdxf.DXFError:
#                        pass
                n_pt += 1

    if address_for_note or target_epsg_for_note:
        add_paperspace_note(doc, address_for_note, target_epsg_for_note)

    doc.saveas(out_path)
    return n_build, n_parc, n_pt
