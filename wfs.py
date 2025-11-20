import geopandas as gpd
import pandas as pd
import requests
from .config import WFS_URL, USER_AGENT, TIMEOUT, ALTI_URL
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

def fetch_layer(layer_name: str, bbox: tuple[float,float,float,float], max_per_page=5000, cancel_event=None):
    start = 0; 
    pages=[]
    while True:
        
        if cancel_event is not None and cancel_event.is_set():
            return
        
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
            gdf = gpd.GeoDataFrame().from_features(feats, crs="EPSG:4326")
            pages.append(gdf)
            if len(feats) < max_per_page: break
            start += max_per_page
        else :
            return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    return gpd.pd.concat(pages, ignore_index=True) if pages else gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

#------Il faut essayer d'appeler ign_lidar_hd_mnt_mono_wld avant la rge alti mais d'abord voir si la zone est couverte ! 
def fetch_alti(bbox, pas_metre = 5, cancel_event=None) :
    last_request_time = 0
    min_interval = 5
    
    minlat, minlon, maxlat, maxlon = bbox
    
    point_wgs84 = ((minlon+maxlon)/2, (minlat+maxlat)/2)
    
    pas_kilometre = pas_metre/1000
    
    pas_lat =pas_kilometre / 111.32
    pas_lon =pas_kilometre/ (111.32 * math.cos(math.radians(point_wgs84[1])))
    
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

    lidar_available = True
    i = 0
    while i < len(pt_lon_chunks) :
        pt_lon_chunk = pt_lon_chunks[i]
        pt_lat_chunk = pt_lat_chunks[i]
    
        if cancel_event is not None and cancel_event.is_set():
            return
    
        elapsed = time.time() - last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)

        if lidar_available :
            params = {
                "lon": ";".join([str(a) for a in pt_lon_chunk]),
                "lat": ";".join([str(b) for b in pt_lat_chunk]),
                "resource": "ign_lidar_hd_mnt_mono_wld",
                "delimiter": ";",
                "indent": "true",
                "measure" : "false",
                "zonly" : "false"
            }
        else :
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
        
        if lidar_available :
            lidar_available = not(all([x.get("z",-99999.0)==-99999.0 for x in response.json().get("elevations",[])]))
            if not lidar_available :
                continue
        
        json_responses.append(response.json())
        last_request_time = time.time()
        
        i+=1
    
    merged={"elevations":[]}
    for r in json_responses :
        merged["elevations"].extend(r.get("elevations",[]))
    
    df = pd.DataFrame(merged["elevations"])
    
    if df.empty :
        return None
    
    gdf =gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["lon"],df["lat"]),crs="EPSG:4326")
    
    
    return gdf[["geometry","z"]]