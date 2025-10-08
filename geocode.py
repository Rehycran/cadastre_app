from dataclasses import dataclass
from typing import List, Union, Optional
import requests
from .config import USER_AGENT, TIMEOUT

ADDOK_URL = 'https://data.geopf.fr/geocodage/search'

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
    params = {'q': address, 'limit': limit}
    r = session.get(ADDOK_URL, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    feats = data.get("features", [])
    if not feats:
        return None
    feats.sort(key=lambda f: (-f["properties"]["score"], -float(f["properties"].get("importance", 0))))
    results = []
    for f in feats:
        lon, lat = f["geometry"]["coordinates"]
        props = f["properties"]
        results.append(Address(
            label=props["label"],
            lon=float(lon), lat=float(lat),
            postcode=props.get("postcode",""),
            citycode=props.get("citycode",""),
        ))
    return results[0] if len(results) == 1 else results
