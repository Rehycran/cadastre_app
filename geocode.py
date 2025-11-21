from dataclasses import dataclass
import requests
from cadastre_app.config import USER_AGENT, TIMEOUT, GEOCODE_URL, AUTOCOM_URL, INVERSE_ULR

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})

@dataclass
class Address:
    label: str
    lon: float
    lat: float
    postcode: str
    citycode: str

def geocode(address: str, limit: int = 20) -> Address | None:
    params = {'q': address, 'limit': limit, 'index': "poi,address"}
    r = session.get(GEOCODE_URL, params=params, timeout=TIMEOUT)
    try :
        r.raise_for_status()
    except requests.exceptions.HTTPError :
        return None
    data = r.json()
    feats = data.get("features", [])
    if not feats:
        return None
    feats.sort(key=lambda f: (-f["properties"]["score"], -float(f["properties"].get("importance", 0))))
    if feats[0]["properties"]["_type"] == "address" :
        return Address(
            label=feats[0]["properties"]["label"],
            lon=float(feats[0]["geometry"]["coordinates"][0]),
            lat=float(feats[0]["geometry"]["coordinates"][1]),
            postcode=feats[0]["properties"].get("postcode",""),
            citycode=feats[0]["properties"].get("citycode",""),
            )
    elif feats[0]["properties"]["_type"] == "poi" :
        return Address(
            label=" ".join([feats[0]["properties"]["name"][0],
                            feats[0]["properties"]["postcode"][0],
                            feats[0]["properties"]["city"][0]
                            ]),
            lon=float(feats[0]["geometry"]["coordinates"][0]),
            lat=float(feats[0]["geometry"]["coordinates"][1]),
            postcode=feats[0]["properties"].get("postcode",""),
            citycode=feats[0]["properties"].get("citycode",""),
            )
    else :
        return None

def inverse_geocode(lon: float, lat: float) -> Address | None:
    params = {"lon":lon, "lat":lat, "index": "poi,address", "limit": 20, "category" : "cimetière,réservoir,construction,hydrographie,élément topographique ou forestier,transport,poste de transformation,zone d'activité ou d'intérêt,zone d'habitation"}
    r = session.get(INVERSE_ULR, params=params, timeout=TIMEOUT)
    try :
        r.raise_for_status()
    except requests.exceptions.HTTPError :
        return None
    data = r.json()
    feats = data.get("features", [])
    if not feats:
        return None
    feats.sort(key=lambda f: (-f["properties"]["score"], -float(f["properties"].get("importance", 0))))
    if feats[0]["properties"]["_type"] == "address" :
        return Address(
            label=feats[0]["properties"]["label"],
            lon=float(feats[0]["geometry"]["coordinates"][0]),
            lat=float(feats[0]["geometry"]["coordinates"][1]),
            postcode=feats[0]["properties"].get("postcode",""),
            citycode=feats[0]["properties"].get("citycode",""),
            )
    elif feats[0]["properties"]["_type"] == "poi" :
        return Address(
            label=" ".join([feats[0]["properties"]["name"][0],
                            feats[0]["properties"]["postcode"][0],
                            feats[0]["properties"]["city"][0]
                            ]),
            lon=float(feats[0]["geometry"]["coordinates"][0]),
            lat=float(feats[0]["geometry"]["coordinates"][1]),
            postcode=feats[0]["properties"].get("postcode",""),
            citycode=feats[0]["properties"].get("citycode",""),
            )
    else :
        return None

def autocomplete(address : str, limit: int = 5) :
    params = {'text': address, 'maximumResponses': limit}
    r = session.get(AUTOCOM_URL, params=params, timeout=TIMEOUT)
    try :
        r.raise_for_status()
    except requests.exceptions.HTTPError as e :
        return None
    
    data = r.json()
    res = data.get("results", [])
    if not res :
        return None
    
    return [r["fulltext"] for r in res]
    