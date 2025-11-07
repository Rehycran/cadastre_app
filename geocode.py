from dataclasses import dataclass
from typing import List, Union, Optional
import requests
from .config import USER_AGENT, TIMEOUT

ADDOK_URL = 'https://data.geopf.fr/geocodage/search'
AUTOCOM_URL = "https://data.geopf.fr/geocodage/completion/"

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})

@dataclass
class Address:
    label: str
    lon: float
    lat: float
    postcode: str
    citycode: str

def geocode(address: str, limit: int = 20) -> Optional[Union[Address, List[str]]]:
    params = {'q': address, 'limit': limit, 'index': "poi,address"}
    r = session.get(ADDOK_URL, params=params, timeout=TIMEOUT)
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
    