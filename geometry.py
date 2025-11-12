from shapely.geometry import Polygon, LineString, Point, MultiPolygon, MultiLineString, MultiPoint

def fix_geom(geom) :
    if geom is None or geom.is_empty: return geom
    if not geom.is_valid:
        g2 = geom.buffer(0)
        if g2.is_valid: return g2
    return geom

def shapely_to_simple_geometry(geometry, z: float):
    coords = list(geometry.coords)
    if len(coords)>=2 and coords[0]==coords[-1]:
        coords=coords[:-1]
    return [(float(x),float(y),float(z)) for x,y,*rest in coords]

def geojson_to_simplegeometry(geom, z=0.0) -> list[tuple[float,float,float]]:
    
    try: z=float(str(z).replace(",","."))
    
    except: z=0.0
    
    simple_geometries=[]
    
    if isinstance(geom, (MultiPolygon, MultiLineString, MultiPoint)) :
        for g in geom.geoms :
            simple_geometries.extend(geojson_to_simplegeometry(g, z))
    
    elif isinstance(geom, (LineString, Point)) :
        if not geom.is_empty :
            simple_geometries.append(shapely_to_simple_geometry(geom, z))

    elif isinstance(geom,Polygon):
        if not geom.is_empty:
            simple_geometries.append(shapely_to_simple_geometry(geom.exterior,z))
            for inter in geom.interiors:
                simple_geometries.append(shapely_to_simple_geometry(inter,z))
    
    return simple_geometries
