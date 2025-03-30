import re
from dataclasses import dataclass
from typing import Dict

import requests

USER_AGENT = "Mozilla/5.0 (Linux; Android 13; SM-S901U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36"
LCSC_MPN_TO_PRODUCT_CODE_URL = (
    "https://wmsc.lcsc.com/wmsc/search/pre/link?type=MPN&keyword={}"
)
LCSC_PART_DETAILS_URL = "https://wmsc.lcsc.com/wmsc/product/detail?productCode={}"
HEADERS = {"User-Agent": USER_AGENT}


@dataclass
class LCSCProduct:
    product_id: int
    code: str
    mpn: str
    category: str
    folder: str
    manufacturer: str
    package: str
    quantity: int
    ship_immediately: int
    datasheet: str
    title: str
    description: str
    price_list: Dict[int, float]

    @classmethod
    def from_json(cls, response: dict):
        price_list = {
            price_info["ladder"]: price_info["usdPrice"]
            for price_info in response.get("productPriceList", [])
        }
        return cls(
            product_id=response.get("productId"),
            code=response.get("productCode"),
            mpn=response.get("productModel"),
            category=response.get("parentCatalogName"),
            folder=response.get("catalogName"),
            manufacturer=response.get("brandNameEn"),
            package=response.get("encapStandard"),
            quantity=response.get("stockNumber"),
            ship_immediately=response.get("shipImmediately"),
            datasheet=response.get("pdfUrl"),
            title=response.get("title"),
            description=response.get("productIntroEn"),
            price_list=price_list,
        )


def _validate(response):
    if response.status_code != 200 or response.json().get("code") != 200:
        raise ValueError(f"Failed to fetch data, status code: {response.status_code}")
    return response


def get_lcsc_product_code(mpn: str) -> str:
    response = requests.get(
        LCSC_MPN_TO_PRODUCT_CODE_URL.format(mpn), headers=HEADERS, timeout=2
    )
    _validate(response)
    part_url = response.json().get("result")
    if part_url is None:
        raise ValueError(f"No results found for MPN: {mpn}")
    product_code = re.findall(r"_(C\d+)\.html", part_url)
    if not product_code:
        raise ValueError(f"No product code found in result: {part_url}")
    return product_code[0]


def get_lcsc_product_details(product_code: str) -> LCSCProduct:
    response = requests.get(
        LCSC_PART_DETAILS_URL.format(product_code), headers=HEADERS, timeout=2
    )
    _validate(response)
    return LCSCProduct.from_json(response.json().get("result"))


def get_product_from_mpn(mpn: str) -> LCSCProduct:
    product_code = get_lcsc_product_code(mpn)
    return get_lcsc_product_details(product_code)
