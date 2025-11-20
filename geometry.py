from shapely.geometry import Polygon, LineString, Point, MultiPolygon, MultiLineString, MultiPoint
import shapely
from pyproj import Transformer

def fix_geom(geom) :
    if geom is None or geom.is_empty: return geom
    if not geom.is_valid:
        g2 = geom.buffer(0)
        if g2.is_valid: return g2
    return geom

def shapely_to_simple_geometry(geometry):
    coords = list(geometry.coords)
    if len(coords)>=2 and coords[0]==coords[-1]:
        coords=coords[:-1]
    try :
        return [(float(x),float(y),float(z)) for x,y,z in coords]
    except ValueError:
        return [(float(x),float(y),float(0)) for x,y, *rest in coords]

def from_crs_to_crs(lon:float, lat:float, target_crs: str, source_crs: str="EPSG:4326") -> tuple[float, float]:
    t = Transformer.from_crs(source_crs, target_crs, always_xy=True)
    return t.transform(lon, lat)


def geojson_to_simplegeometry(geom, bbox_polygon):
    
    geom =fix_geom(geom)
    
    simple_geometries=[]
    
    if isinstance(geom, (MultiPolygon, MultiLineString, MultiPoint)) :
        for g in geom.geoms :
            sg, c = geojson_to_simplegeometry(g, bbox_polygon)
            simple_geometries.extend(sg)
            close = c 
    
    elif isinstance(geom, (LineString, Point)) :
        if not geom.is_empty :
            if shapely.intersects(geom, bbox_polygon) :
                simple_geometries.append(shapely_to_simple_geometry(geom))

    elif isinstance(geom,Polygon):
        close = True
        if not geom.is_empty:
            print()
            if shapely.intersects(geom, bbox_polygon) :
                simple_geometries.append(shapely_to_simple_geometry(geom.exterior))
                for inter in geom.interiors:
                    simple_geometries.append(shapely_to_simple_geometry(inter))
    try :
        return (simple_geometries, close)
    except NameError :
        return(simple_geometries, False)