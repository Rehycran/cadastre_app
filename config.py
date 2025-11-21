# -*- coding: utf-8 -*-
from requests.adapters import Retry
import geopandas as gpd

WFS_URL = "https://data.geopf.fr/wfs/ows"
GEOCODE_URL = 'https://data.geopf.fr/geocodage/search'
AUTOCOM_URL = "https://data.geopf.fr/geocodage/completion/"
INVERSE_ULR = 'https://data.geopf.fr/geocodage/reverse'

WFS_LAYERS = {"Batiment" : ("BDTOPO_V3:batiment", True),
              "Parcelle" : ("CADASTRALPARCELS.PARCELLAIRE_EXPRESS:parcelle", True),
              "Commune" : ("CADASTRALPARCELS.PARCELLAIRE_EXPRESS:commune", False),
              "Arrondissement" : ("CADASTRALPARCELS.PARCELLAIRE_EXPRESS:arrondissement", False),
              "Subdivision fiscale" : ("CADASTRALPARCELS.PARCELLAIRE_EXPRESS:subdivision_fiscale", False),
              "ERP" : ("BDTOPO_V3:erp", False),
              "Route" : ("BDTOPO_V3:troncon_de_route", False),
              "Voie ferree" : ("BDTOPO_V3:troncon_de_voie_ferree", False),
              "Equipement de transport" : ("BDTOPO_V3:equipement_de_transport", False),
              "Ligne electrique" : ("BDTOPO_V3:ligne_electrique", False),
              "Cimetiere" : ("BDTOPO_V3:cimetiere", False),
              "Reservoir" : ("BDTOPO_V3:reservoir", False),
              "Plan d'eau" : ("BDTOPO_V3:plan_d_eau", False),
              "Cours d'eau" : ("BDTOPO_V3:cours_d_eau", False),
              "Parc-Reserve" : ("BDTOPO_V3:parc_ou_reserve", False),
              "Foret" : ("BDTOPO_V3:foret_publique", False),
              "Haie" : ("BDTOPO_V3:haie", False),
              "Zone de végétation" : ("BDTOPO_V3:zone_de_vegetation", False),
              "Terrain de sport" : ("BDTOPO_V3:terrain_de_sport", False),
              "Aerodrome" : ("BDTOPO_V3:aerodrome", False),
              "Piste d'aerodrome" : ("BDTOPO_V3:piste_d_aerodrome", False)
            }
WFS_ATTRIB = {"Batiment" : {"hauteur", "altitude_maximale_toit", "altitude_minimale_toit", "altitude_minimale_sol"},
              "Parcelle" : {"idu", "numero", "feuille", "section" },
              "Commune" : {"nom_com"},
              "Arrondissement" : {"nom_arr"},
              "Subdivision fiscale" : {"lettre"},
              "ERP" : {"categorie", "type_principal", "libelle"},
              "Route" : {"largeur_de_chaussee"},
              "Voie ferree" : {"largeur"},
              "Equipement de transport" : {"nature"},
              "Ligne electrique" : {},
              "Cimetiere" : {},
              "Reservoir" : {"hauteur", "altitude_maximale_toit", "altitude_minimale_toit", "altitude_minimale_sol"},
              "Plan d'eau" : {"altitude_moyenne"},
              "Cours d'eau" : {},
              "Parc-Reserve" : {"nature"},
              "Foret" : {"nature"},
              "Haie" : {"largeur", "hauteur"},
              "Zone de végétation" : {},
              "Terrain de sport" : {"nature"},
              "Aerodrome" : {"altitude"},
              "Piste d'aerodrome" : {}
            }
ALTI_URL = "https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json"

KELLY_COLOR = {"vivid_yellow":(255, 179, 0),
               "strong_purple":(128, 62, 117),
               "vivid_orange":(255, 104, 0),
               "very_light_blue":(166, 189, 215),
               "vivid_red":(193, 0, 32),
               "grayish_yellow":(206, 162, 98),
               "medium_gray":(129, 112, 102),
               "vivid_green":(0, 125, 52),
               "strong_purplish_pink":(246, 118, 142),
               "strong_blue":(0, 83, 138),
               "strong_yellowish_pink":(255, 122, 92),
               "strong_violet":(83, 55, 122),
               "vivid_orange_yellow":(255, 142, 0),
               "strong_purplish_red":(179, 40, 81),
               "vivid_greenish_yellow":(244, 200, 0),
               "strong_reddish_brown":(127, 24, 13),
               "vivid_yellowish_green":(147, 170, 0),
               "deep_yellowish_brown":(89, 51, 21),
               "vivid_reddish_orange":(241, 58, 19),
               "dark_olive_green":(35, 44, 22)
               }

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

DEFAULT_CRS = "EPSG:2154" #Lambert 93 v1 France metropolitaine
DEFAULT_STEP = 5 #pas de la grille alti en mètres

USER_AGENT = "cadastre-app"
TIMEOUT = (5, 60)
RETRIES = Retry(total=3, backoff_factor=0.5, status_forcelist=(429, 500, 502, 503, 504))

HEADER_FONT = ("Futura PT Demi", 23)
TEXT_FONT = ("Futura PT Book", 20)
BUTTON_FONT = ("Futura PT Bold", 18)
ENTRY_FONT = ("Futura PT Book", 16)
INFO_FONT = ("Futura PT Light",12)