import re
import requests
from .config import USER_AGENT, TIMEOUT, CC_TO_EPSG, DEPT_TO_CC, DEFAULT_CRS_2154


def epsg_from_postcode(postcode: str, fallback: str = DEFAULT_CRS_2154) -> str:

    if not postcode or len(postcode) < 2:
        return fallback
    dept = postcode[:2]
    # Handle Corsica postcodes (20***)
    if dept == "20":
        return CC_TO_EPSG["CC42"]
    cc = DEPT_TO_CC.get(dept)
    return CC_TO_EPSG.get(cc, fallback) if cc else fallback
