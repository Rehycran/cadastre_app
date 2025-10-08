from shapely.geometry import Polygon, MultiPolygon, LinearRing, LineString, MultiLineString 

def fix_geom(geom):
    if geom is None or geom.is_empty: return geom
    if not geom.is_valid:
        g2 = geom.buffer(0)
        if g2.is_valid: return g2
    return geom

def _ring_points_3d(ring: LinearRing, z: float):
    coords = list(ring.coords)
    if len(coords)>=2 and coords[0]==coords[-1]:
        coords=coords[:-1]
    return [(float(x),float(y),float(z)) for x,y,*rest in coords]

def _line_points_3d(line: LineString, z: float):
    coords = list(line.coords)
    return [(float(x), float(y), float(z)) for x, y, *rest in coords]

def polygon_to_3d_polylines(geom, z):
    try: z=float(str(z).replace(",","."))
    except: z=0.0
    polys=[]
    if isinstance(geom,Polygon):
        if not geom.is_empty:
            polys.append(_ring_points_3d(geom.exterior,z))
            for inter in geom.interiors:
                polys.append(_ring_points_3d(inter,z))
    elif isinstance(geom,MultiPolygon):
        for g in geom.geoms:
            polys.extend(polygon_to_3d_polylines(g,z))
    elif isinstance(geom, LineString):
        if not geom.is_empty:
            polys.append(_line_points_3d(geom, z))
    elif isinstance(geom, MultiLineString):
        for g in geom.geoms:
            polys.extend(polygon_to_3d_polylines(g, z))
    polys = [p for p in polys if len(p) >= 2]
    return polys
