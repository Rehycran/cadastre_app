# -*- coding: utf-8 -*-
from requests.adapters import HTTPAdapter, Retry
import geopandas as gpd

WFS_URL = "https://data.geopf.fr/wfs/ows"
LAYER_BUILDINGS = "BDTOPO_V3:batiment"
LAYER_PARCELLES = "BDPARCELLAIRE-VECTEUR_WLD_BDD_WGS84G:parcelle"
ALTI_URL = "https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json"

DEPT_TO_CC = {
    # CC42
    "2A": "CC42", "2B": "CC42",
    # CC43
    "09": "CC43", "11": "CC43", "31": "CC43", "34": "CC43",
    "64": "CC43", "65": "CC43", "66": "CC43", "83": "CC43",
    # CC44
    "04": "CC44", "06": "CC44", "12": "CC44", "13": "CC44",
    "30": "CC44", "32": "CC44", "40": "CC44", "47": "CC44",
    "48": "CC44", "81": "CC44", "82": "CC44", "84": "CC44",
    # CC45
    "05": "CC45", "07": "CC45", "15": "CC45", "19": "CC45",
    "24": "CC45", "26": "CC45", "33": "CC45", "38": "CC45",
    "43": "CC45", "46": "CC45", "73": "CC45",
    # CC46
    "01": "CC46", "03": "CC46", "16": "CC46", "17": "CC46",
    "23": "CC46", "42": "CC46", "63": "CC46", "69": "CC46",
    "74": "CC46", "87": "CC46",
    # CC47
    "18": "CC47", "21": "CC47", "25": "CC47", "36": "CC47",
    "37": "CC47", "39": "CC47", "44": "CC47", "49": "CC47",
    "58": "CC47", "71": "CC47", "79": "CC47", "85": "CC47",
    "86": "CC47",
    # CC48
    "10": "CC48", "22": "CC48", "28": "CC48", "29": "CC48",
    "35": "CC48", "41": "CC48", "45": "CC48", "52": "CC48",
    "53": "CC48", "56": "CC48", "68": "CC48", "70": "CC48",
    "72": "CC48", "88": "CC48", "89": "CC48", "90": "CC48",
    # CC49
    "02": "CC49", "14": "CC49", "27": "CC49", "50": "CC49",
    "51": "CC49", "54": "CC49", "55": "CC49", "57": "CC49",
    "60": "CC49", "61": "CC49", "67": "CC49", "75": "CC49",
    "77": "CC49", "78": "CC49", "91": "CC49", "92": "CC49",
    "93": "CC49", "94": "CC49", "95": "CC49",
    # CC50
    "08": "CC50", "59": "CC50", "62": "CC50", "76": "CC50",
    "80": "CC50",
}

CC_TO_EPSG = {
    "CC42": "EPSG:3942",
    "CC43": "EPSG:3943",
    "CC44": "EPSG:3944",
    "CC45": "EPSG:3945",
    "CC46": "EPSG:3946",
    "CC47": "EPSG:3947",
    "CC48": "EPSG:3948",
    "CC49": "EPSG:3949",
    "CC50": "EPSG:3950",
}

DEFAULT_CRS_2154 = "EPSG:2154"
DEFAULT_STEP = 50 #pas de la grille alti en mètres

USER_AGENT = "cadastre-app/1.0"
TIMEOUT = (5, 60)
RETRIES = Retry(total=3, backoff_factor=0.5, status_forcelist=(429, 500, 502, 503, 504))

EMPTY_ALTI = gpd.GeoDataFrame(columns=["geometry", "elevations"], geometry="geometry", crs=DEFAULT_CRS_2154)

TEXT_FONT = ("Futura PT Demi", 14)
BUTTON_FONT = ("Futura PT Bold", 14)
ENTRY_FONT = ("Futura PT Book", 12)
