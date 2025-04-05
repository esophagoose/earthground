import dataclasses
import json
import logging
import os
import pathlib
import re
from typing import Dict

import digikey
import digikey.v4.productinformation as Pro

import earthground.tools.helper.response_cache as api_cache

LOG = logging.getLogger("Digikey")


@dataclasses.dataclass
class DigikeyComponent:
    mpn: str
    manufacturer: str
    description: str
    datasheet: str
    digikey_part_number: str
    path: str
    attributes: Dict[str, str]


FOLDER_REPLACEMENTS = {"DC DC Switching Regulators": "switching"}


def make_folder_name(category: str) -> str:
    # Remove any text within parentheses
    cleaned_category = re.sub(r"\([^)]*\)", "", category)
    cleaned_category = cleaned_category.split(", ")[-1].strip()
    if cleaned_category in FOLDER_REPLACEMENTS:
        cleaned_category = FOLDER_REPLACEMENTS[cleaned_category]
    return cleaned_category.lower().strip().replace(" ", "_")


class DigikeyComponentCreator:
    """
    A class for creating component objects from DigiKey part information.

    This class handles the interaction with the DigiKey API, including authentication,
    caching of responses, and conversion of API data into structured component objects.
    It provides methods to search for components by part number and keyword, and
    creates DigikeyComponent objects with standardized attributes.

    The class implements caching to reduce API calls and improve performance for
    repeated queries. All API responses are stored in a local cache directory.
    """

    def __init__(self):
        self.cache = api_cache.ApiResponseCache("digikey")
        self.login()

    def get_credentials(self, service: str):
        path = pathlib.Path.home() / ".credentials" / f"{service}.json"
        with open(path, "r") as f:
            data = json.load(f)
            return data.get("client_id"), data.get("client_secret")

    def login(self):
        cache = str(pathlib.Path.home() / ".credentials/")
        cid, password = self.get_credentials("digikey")
        os.environ["DIGIKEY_CLIENT_ID"] = cid
        os.environ["DIGIKEY_CLIENT_SECRET"] = password
        os.environ["DIGIKEY_CLIENT_SANDBOX"] = "False"
        os.environ["DIGIKEY_STORAGE_PATH"] = cache
        LOG.info("DigiKey credentials loaded")

    def get_component_details(self, part_number: str):
        LOG.info(f"Fetching component details for {part_number} from DigiKey")
        part = self.cache.fetch_if_not_cached(digikey.product_details, [part_number])
        product = part.to_dict().get("product")
        path = pathlib.Path(make_folder_name(product["category"]["name"]))
        child_category = product["category"]["child_categories"]
        while child_category:
            split = child_category[0]["name"].split("-", 2)
            if len(split) > 1:
                path = path / make_folder_name(split[0])
                child_category[0]["name"] = split[1]
            path = path / make_folder_name(child_category[0]["name"])
            child_category = child_category[0]["child_categories"]
        attributes = {
            "lead_time": product["manufacturer_lead_weeks"],
            "state": product["product_status"]["status"],
        }
        description = product["description"]["detailed_description"]
        description = " ".join(description.split(" ")[:-1])
        component = DigikeyComponent(
            manufacturer=product["manufacturer"]["name"],
            mpn=product["base_product_number"]["name"],
            description=description,
            datasheet=product["datasheet_url"],
            digikey_part_number=part_number,
            path=path,
            attributes=attributes,
        )
        LOG.debug(f"Component: {component}")
        return component
