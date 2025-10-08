import geopandas as gpd
import pandas as pd
import requests
from typing import Tuple, List
from .config import WFS_URL, DEFAULT_CRS_2154, USER_AGENT, TIMEOUT, LAYER_BUILDINGS, LAYER_PARCELLES, ALTI_URL
import math
import time

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})

def _wfs_get_json(params: dict):
    r = session.get(WFS_URL, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

def fetch_layer(layer_name: str, bbox: Tuple[float,float,float,float], crs=DEFAULT_CRS_2154, max_per_page=5000):
    start = 0; frames=[]
    while True:
        params = {
            "service":"WFS","version":"2.0.0","request":"GetFeature",
            "typenames":layer_name,"count":max_per_page,"startIndex":start,
            "srsName":crs,"outputFormat":"application/json",
            "bbox":",".join(f"{v:.3f}" for v in bbox)+f",{crs}"
        }
        data = _wfs_get_json(params)
        feats = data.get("features", [])
        if not feats: break
        gdf = gpd.GeoDataFrame.from_features(feats, crs=crs)
        frames.append(gdf)
        if len(feats) < max_per_page: break
        start += max_per_page
    return gpd.pd.concat(frames, ignore_index=True) if frames else gpd.GeoDataFrame(geometry=[], crs=crs)

def fetch_buildings(bbox, crs=DEFAULT_CRS_2154, max_per_page=5000):
    out = fetch_layer(LAYER_BUILDINGS, bbox, crs, max_per_page)
    
    if out.empty:
        return gpd.GeoDataFrame(columns=["geometry","hauteur"], geometry="geometry", crs=crs)
    
    cols_hauteur = [c for c in out.columns if c.lower() in ("hauteur","height","hauteur_val","hauteur_value","heightaboveground_value")]
    if not cols_hauteur: out["hauteur"]=gpd.pd.NA
    else:
        hc = cols_hauteur[0]
        if hc!="hauteur": out=out.rename(columns={hc:"hauteur"})
    
    cols_altitude_max = [c for c in out.columns if c.lower() in ("altitude_maximale_toit")]
    if not cols_altitude_max: out["altitude_maximale_toit"]=gpd.pd.NA
    else:
        hc = cols_altitude_max[0]
        if hc!="altitude_maximale_toit": out=out.rename(columns={hc:"altitude_maximale_toit"})
    
    cols_altitude_min = [c for c in out.columns if c.lower() in ("altitude_minimale_toit")]
    if not cols_altitude_min: out["altitude_minimale_toit"]=gpd.pd.NA
    else:
        hc = cols_altitude_min[0]
        if hc!="altitude_minimale_toit": out=out.rename(columns={hc:"altitude_minimale_toit"})
    
    return out[["geometry","hauteur", "altitude_maximale_toit", "altitude_minimale_toit"]]

def fetch_parcelles(bbox, crs=DEFAULT_CRS_2154, max_per_page=5000):
    out = fetch_layer(LAYER_PARCELLES, bbox, crs, max_per_page)
    return out[["geometry"]] if not out.empty else gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs=crs)

def fetch_alti(addr, distance_m = 200, pas_metre = 5) :
    last_request_time = 0
    min_interval = 5
    
    point_wgs84 = (addr.lon, addr.lat)
    
    pas_kilometre = pas_metre/1000
    distance_km = distance_m/1000
    
    pas_lat =pas_kilometre / 111.32
    pas_lon =pas_kilometre/ (111.32 * math.cos(math.radians(point_wgs84[1])))
    
    delta_lat = distance_km / 111.32
    delta_lon = distance_km / (111.32 * math.cos(math.radians(point_wgs84[1])))
    
    minlat = point_wgs84[1] - delta_lat
    maxlat = point_wgs84[1] + delta_lat
    minlon = point_wgs84[0] - delta_lon
    maxlon = point_wgs84[0] + delta_lon
    
    x = minlat
    list_lat = []
    while x < maxlat :
        list_lat.append(x)
        x+=pas_lat
    list_lat.append(maxlat)
    
    y = minlon
    list_lon = []
    while y < maxlon :
        list_lon.append(y)
        y+=pas_lon
    list_lon.append(maxlon)
    
    pt_lon =[]
    pt_lat =[]
    
    for x in list_lon :
        for y in list_lat :
            pt_lon.append(x)
            pt_lat.append(y)
    
    div_lon = len(pt_lon)//5000
    div_lat = len(pt_lat)//5000
    
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
            "resource": "ign_rge_alti_wld",
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
    
    """
    if out.empty:
        return gpd.GeoDataFrame(columns=["geometry","altitude"], geometry="geometry", crs=crs)
    cols = [c for c in out.columns if c.lower() in ("altitude")]
    if not cols: out["altitude"]=gpd.pd.NA
    else:
        hc = cols[0]
        if hc!="altitude": out=out.rename(columns={hc:"altitude"})
    return out[["geometry","altitude"]]
    """
