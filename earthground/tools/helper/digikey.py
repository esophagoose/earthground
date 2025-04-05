import json
import logging
import os
import re
import pathlib
import dataclasses
from typing import Any, Dict

import digikey
from digikey.v3.productinformation import KeywordSearchRequest

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

def make_folder_name(category: str) -> str:
    # Remove any text within parentheses
    cleaned_category = re.sub(r'\([^)]*\)', '', category)
    cleaned_category = cleaned_category.split(", ")[-1]
    return cleaned_category.lower().strip().replace(" ", "_")

class DigikeyComponentCreator:

    def __init__(self, cache_dir: str = ".cache/digikey_responses"):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
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

    def _get_cache_path(self, part_number: str, response_type: str) -> str:
        """Create a path for caching responses."""
        return os.path.join(self.cache_dir, f"{part_number}_{response_type}.json")

    def _check_cache(self, part_number: str, response_type: str) -> Any:
        """Check if response is cached and return it if found."""
        cache_path = self._get_cache_path(part_number, response_type)
        if os.path.exists(cache_path):
            LOG.info(f"Cached {response_type} response found for {part_number}")
            with open(cache_path, "r") as f:
                return json.load(f)
        return None

    def _save_to_cache(
        self, part_number: str, response_type: str, response: Any
    ) -> None:
        """Save response to cache."""
        cache_path = self._get_cache_path(part_number, response_type)
        with open(cache_path, "w") as f:
            json.dump(response, f)
        LOG.debug(f"Saved {response_type} response to cache for {part_number}")

    def _query_digikey(self, part_number: str, response_type: str):
        # Check cache first
        data = self._check_cache(part_number, response_type)
        if data:
            return data

        # If not in cache, fetch from DigiKey API
        LOG.warning(f"Querying {response_type} for {part_number} from DigiKey")
        part = digikey.product_details(part_number)
        self._save_to_cache(part_number, "details", part.to_dict())
        return part.to_dict()

    def get_component_details(self, part_number: str):
        LOG.info(f"Fetching component details for {part_number} from DigiKey")
        product = self._query_digikey(part_number, "details").get("product")
        path = pathlib.Path(make_folder_name(product["category"]["name"]))
        child_category = product["category"]["child_categories"]
        while child_category:
            path = path / make_folder_name(child_category[0]["name"])
            child_category = child_category[0]["child_categories"]
        attributes = {
            "lead_time": product["manufacturer_lead_weeks"],
            "state": product["product_status"]["status"],
        }
        component = DigikeyComponent(
            manufacturer=product["manufacturer"]["name"],
            mpn=product["base_product_number"]["name"],
            description=product["description"]["detailed_description"],
            datasheet=product["datasheet_url"],
            digikey_part_number=part_number,
            path=path,
            attributes=attributes,
        )
        LOG.debug(f"Component: {component}")
        return component


    def get_digikey_part_number_from_mpn(self, mpn: str) -> str:
        LOG.info(f"Searching DigiKey for MPN: {mpn}")

        # Check cache first
        cached_data = self._check_cache(mpn, "search")
        if cached_data:
            LOG.info(f"Using cached search results for MPN: {mpn}")
            choices = cached_data["choices"]
            products = cached_data["products"]
        else:
            # If not in cache, fetch from DigiKey API
            request = KeywordSearchRequest(keywords=mpn, record_count=10)
            response = digikey.keyword_search(body=request)

            choices = {}
            products = []
            for i, part in enumerate(response.products):
                key = f"{part.manufacturer_part_number}: {part.product_description}"
                key += f" - {part.detailed_description}"
                choices[key] = i
                products.append(
                    {
                        "digi_key_part_number": part.digi_key_part_number,
                        "manufacturer_part_number": part.manufacturer_part_number,
                        "product_description": part.product_description,
                        "detailed_description": part.detailed_description,
                    }
                )

            # Save to cache
            cache_data = {"choices": choices, "products": products}
            self._save_to_cache(mpn, "search", cache_data)

        LOG.debug(f"Found {len(choices)} matching products")
        description = inquirer.select(
            "Select the right part:",
            choices=list(choices.keys()),
        ).execute()
        return products[choices[description]]["digi_key_part_number"]