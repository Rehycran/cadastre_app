import geopandas as gpd
import pandas as pd
import requests
from .config import WFS_URL, USER_AGENT, TIMEOUT, WFS_LAYERS, ALTI_URL
import math
import time

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})

def _wfs_get_json(params: dict):
    r = session.get(WFS_URL, params=params, timeout=TIMEOUT)
    try :
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e :
        return None

def fetch_layer(layer_name: str, bbox: tuple[float,float,float,float], max_per_page=5000):
    start = 0; 
    pages=[]
    while True:
        params = {
            "service":"WFS",
            "version":"2.0.0",
            "request":"GetFeature",
            "typenames":layer_name,
            "count":max_per_page,
            "startIndex":start,
            "outputFormat":"application/json",
            "bbox":",".join(f"{v:.3f}" for v in bbox)
        }
        data = _wfs_get_json(params)
        if data is not None :
            feats = data.get("features", [])
            if not feats: break
            gdf = gpd.GeoDataFrame.from_features(feats)
            pages.append(gdf)
            if len(feats) < max_per_page: break
            start += max_per_page
        else :
            return gpd.GeoDataFrame(geometry=[])
    return gpd.pd.concat(pages, ignore_index=True) if pages else gpd.GeoDataFrame(geometry=[])

def fetch_buildings(bbox, max_per_page=5000):
    gdf = fetch_layer(LAYER_BUILDINGS, bbox, max_per_page)
    
    if gdf.empty:
        return gpd.GeoDataFrame(columns=["geometry","hauteur"], geometry="geometry")
    
    cols_hauteur = [c for c in gdf.columns if c.lower() in ("hauteur","height","hauteur_val","hauteur_value","heightaboveground_value")]
    if not cols_hauteur: gdf["hauteur"]=gpd.pd.NA
    else:
        hc = cols_hauteur[0]
        if hc!="hauteur": gdf=gdf.rename(columns={hc:"hauteur"})
    
    cols_altitude_max = [c for c in gdf.columns if c.lower() in ("altitude_maximale_toit")]
    if not cols_altitude_max: gdf["altitude_maximale_toit"]=gpd.pd.NA
    else:
        hc = cols_altitude_max[0]
        if hc!="altitude_maximale_toit": gdf=gdf.rename(columns={hc:"altitude_maximale_toit"})
    
    cols_altitude_min = [c for c in gdf.columns if c.lower() in ("altitude_minimale_toit")]
    if not cols_altitude_min: gdf["altitude_minimale_toit"]=gpd.pd.NA
    else:
        hc = cols_altitude_min[0]
        if hc!="altitude_minimale_toit": gdf=gdf.rename(columns={hc:"altitude_minimale_toit"})
    
    return gdf[["geometry","hauteur", "altitude_maximale_toit", "altitude_minimale_toit"]]

def fetch_parcelles(bbox, max_per_page=5000):
    gdf = fetch_layer(LAYER_PARCELLES, bbox, max_per_page)
    return gdf[["geometry"]] if not gdf.empty else gpd.GeoDataFrame(columns=["geometry"], geometry="geometry")

#------Il faut essayer d'appeler ign_lidar_hd_mnt_mono_wld avant la rge alti mais d'abord voir si la zone est couverte ! 
def fetch_alti(lat, lon, distance_x = 200, distance_y=200, pas_metre = 5) :
    last_request_time = 0
    min_interval = 5
    
    point_wgs84 = (lon, lat)
    
    pas_kilometre = pas_metre/1000
    
    pas_lat =pas_kilometre / 111.32
    pas_lon =pas_kilometre/ (111.32 * math.cos(math.radians(point_wgs84[1])))
    
    delta_lat = (distance_x/1000) / 111.32
    delta_lon = (distance_y/1000) / (111.32 * math.cos(math.radians(point_wgs84[1])))
    
    minlat = point_wgs84[1] - delta_lat
    maxlat = point_wgs84[1] + delta_lat
    minlon = point_wgs84[0] - delta_lon
    maxlon = point_wgs84[0] + delta_lon
    
    eps = 1e-7
    
    x = minlon
    list_lon = []
    while x < maxlon - eps:
        list_lon.append(x)
        x+=pas_lon
    list_lon.append(maxlon)
    
    
    
    y = minlat
    list_lat = []
    while y < maxlat - eps :
        list_lat.append(y)
        y+=pas_lat
    list_lat.append(maxlat)
    
    
    pt_lon =[]
    pt_lat =[]
    
    for longitude in list_lon :
        for latitude in list_lat :
            pt_lon.append(longitude)
            pt_lat.append(latitude)
    
    div_lon = len(pt_lon)//4000
    div_lat = len(pt_lat)//4000
    
    pt_lon_chunks = [pt_lon[i*4000:(i+1)*4000] for i in range(div_lon+1)]
    pt_lat_chunks = [pt_lat[i*4000:(i+1)*4000] for i in range(div_lat+1)]
    
    
    json_responses = []
    
    headers = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Connection": "close"
    }

    
    for pt_lon_chunk, pt_lat_chunk in zip(pt_lon_chunks, pt_lat_chunks) :
    
        elapsed = time.time() - last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
    
        params = {
            "lon": ";".join([str(a) for a in pt_lon_chunk]),
            "lat": ";".join([str(b) for b in pt_lat_chunk]),
            "resource": "ign_lidar_hd_mnt_mono_wld",
            "delimiter": ";",
            "indent": "true",
            "measure" : "false",
            "zonly" : "false"
        }
        response = session.post(ALTI_URL, json=params, headers=headers, timeout=(10, 120))

        response.raise_for_status()
        json_responses.append(response.json())
        
        last_request_time = time.time()
    
    merged={"elevations":[]}
    for r in json_responses :
        merged["elevations"].extend(r.get("elevations",[]))
    
    df = pd.DataFrame(merged["elevations"])
    gdf =gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["lon"],df["lat"]),crs="EPSG:4326")
    
    return gdf[["geometry","z"]]