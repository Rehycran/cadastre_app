import re
import requests
from .config import USER_AGENT, TIMEOUT, CC_TO_EPSG, DEPT_TO_CC, DEFAULT_CRS

from .geocode import Address


def epsg_from_postcode(address: Address, fallback: str = DEFAULT_CRS) -> str:

    if not hasattr(address, "postcode") or len(address.postcode) < 2:
        return fallback
    dept = address.postcode[:2]
    # Handle Corsica postcodes (20***)
    if dept == "20":
        return CC_TO_EPSG["CC42"]
    cc = DEPT_TO_CC.get(dept)
    return CC_TO_EPSG.get(cc, fallback) if cc else fallback
