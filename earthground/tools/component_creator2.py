import json
import os
import pathlib
from typing import Dict

# import digikey
import openai

# from digikey.v3.productinformation import KeywordSearchRequest
from InquirerPy import inquirer

FOLDER_IDS = {
    32: "integrated_circuits",
    15: "switches",
    33: "headers",
    20: "connectors",
}
FAMILY_IDS = {
    749: "io_expanders",
    685: "microcontrollers",
    754: "specialized",
    199: "",
    560: "interface_sensor",
    783: "",
    753: "controllers",
    744: "motor_drivers",
    739: "voltage_regulators/switching",
    399: "fpc",
}


def get_credentials(service: str):
    path = pathlib.Path.home() / ".credentials" / f"{service}.json"
    with open(path, "r") as f:
        data = json.load(f)
        return data.get("client_id"), data.get("client_secret")


def digikey_login():
    cache = str(pathlib.Path.home() / ".credentials/")
    cid, password = get_credentials("digikey")
    os.environ["DIGIKEY_CLIENT_ID"] = cid
    os.environ["DIGIKEY_CLIENT_SECRET"] = password
    os.environ["DIGIKEY_CLIENT_SANDBOX"] = "False"
    os.environ["DIGIKEY_STORAGE_PATH"] = cache


def get_component_from_digikey(part_number: str):
    part = digikey.product_details(part_number)
    data = part.to_dict()
    folder_id = int(data["category"]["value_id"])
    family_id = int(data["family"]["value_id"])
    if folder_id not in FOLDER_IDS:
        uid, category = (data["category"]["value_id"], data["category"]["value"])
        raise KeyError(f"Missing folder id {uid}: {category}")
    if family_id not in FAMILY_IDS:
        uid, family = (data["family"]["value_id"], data["family"]["value"])
        raise KeyError(f"Missing family id {uid}: {family}")
    parameters = {}
    for param in data["parameters"]:
        parameters[param["parameter"]] = param["value"]
    attributes = {
        "manufacturer": data["manufacturer"]["value"],
        "mpn": data["manufacturer_part_number"],
        "description": data["product_description"],
        "datasheet": data["primary_datasheet"],
        "parameters": parameters,
    }
    path = pathlib.Path(FOLDER_IDS[folder_id]) / pathlib.Path(FAMILY_IDS[family_id])
    return path, attributes


def generate_pins(pin_section: str):
    client = openai.OpenAI()

    system_prompt = """You create json objects of pin indexes to names for various
    footprints from text from a datasheet. There should be columns for
    pin names, pin indexes, and maybe pin descriptions. The input will be text
    and you output a json object that looks like this:
    ```
    {
        "pins": [
            {
                "name": parsed_pin_name,
                "index": parsed_pin_index,
                "comment": parsed_pin_comment
            }
        ]
    }
    ```
    
    if there are multiple columns of pin indices for different footprints, 
    available, include an entry for each footprint like this example:
    ```
    {
        "footprints": [
            {
                "name": parsed_footprint_name,
                "pins": [
                    {
                        "name": parsed_pin_name,
                        "index": parsed_pin_index,
                        "comment": parsed_pin_comment
                    }
                ]
            }
        ]
    }
    ```
    """

    user_prompt = f"""```{pin_section}``` \nOutput a json object from the markdown above 
    where every object in the json list has three keys: "name", "index", 
    "comment" for the pin name, pin index, and pin description (if present)\n
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return json.loads(response.choices[0].message.content)


def write_component(path: str, attributes: Dict[str, str], pins=None):
    name = attributes["mpn"].lower()
    filepath = "earthground/library" / path / (name + ".py")
    out = "import earthground.components as cmp"
    out += "\n\n\n"
    out += f"class {name.upper()}(cmp.Component):\n"
    out += "    def __init__(self):\n"
    out += "        super().__init__()\n"
    for name, value in attributes.items():
        if isinstance(value, str):
            value = f'"{value}"'
        out += f"        self.{name} = {value}\n"
    if pins:
        out += "        self.pins = cmp.PinContainer.from_dict({\n"
        for pin in pins:
            out += " " * 12
            out += f"\"{pin['index']}\": \"{pin['name']}\""
            out += f"  # {pin['comment']},\n"
        out += "        }, self)"
    if not os.path.exists(os.path.dirname(filepath)):
        os.makedirs(os.path.dirname(filepath))
    with open(filepath, "w") as f:
        f.write(out)
        print(f"Successfully wrote {filepath}")


def get_digikey_part_number_from_mpn(mpn: str) -> str:
    request = KeywordSearchRequest(keywords=mpn, record_count=10)
    response = digikey.keyword_search(body=request)

    choices = {}
    for i, part in enumerate(response.products):
        key = f"{part.manufacturer_part_number}: {part.product_description}"
        key += f" - {part.detailed_description}"
        choices[key] = i
    description = inquirer.select(
        "Select the right part:",
        choices=list(choices.keys()),
    ).execute()
    return response.products[choices[description]].digi_key_part_number


def create(digikey_part_number: str, use_ai_for_pins: bool):
    folder, attr = get_component_from_digikey(digikey_part_number)
    part_pins = None
    if use_ai_for_pins:
        part_pins = generate_pins(attr["datasheet"])
    write_component(folder, attr, part_pins)


import re


class SimpleMarkdown:
    def __init__(self, data: Dict[str, str]):
        self._data = data

    @staticmethod
    def image_strip(line: str) -> str:
        return re.sub(r"\!\[Image\]\(data:image(.*?)\)", "", line)

    @classmethod
    def parse(cls, path: str) -> "SimpleMarkdown":
        """
        Parse the markdown content into a dictionary of headings and their corresponding sections.

        Returns:
            A dictionary where keys are heading titles and values are the section content.
        """
        data = {}
        with open(path, "r") as f:
            last_heading = None
            for line in f.readlines():
                if line.startswith("#"):
                    last_heading = line.strip("#").strip()
                elif last_heading:
                    if last_heading not in data:
                        data[last_heading] = ""
                    data[last_heading] += SimpleMarkdown.image_strip(line)
            return cls(data)

    def get_all_text_from_search(self, search: str) -> str:
        result = ""
        for heading, section in self._data.items():
            if search.lower() in heading.lower():
                result += section
                print(heading)
        return result


def process_ordering_section(ordering_section: str) -> Dict[str, Dict[str, str]]:
    client = openai.OpenAI()

    system_prompt = """You extract ordering information from a provided markdown data on
    the electrical component and structure it as a JSON object. The object have part number 
    as key and a dictionary of parameters as value. An example is, for this prompt:
    ```
    | Orderable Device   | Status (1)   | Package Type   | Package Drawing   |   Pins | Temperature Range |
    |--------------------|--------------|----------------|-------------------|--------|------------|
    | TCA9535DBR         | ACTIVE       | SSOP           | DB                |     24 | -20 to 65 |
    | TCA9535MRGER       | ACTIVE       | VQFN           | RGE               |     36 | -40 to 85 |
    ```
    the output should be:
    ```
    {
        "TCA9535DBR": {
            "pins": 24,
            "package_type": "SSOP",
            "package_drawing": "DB",
            "temperature_range": "Normal"
        },
        "TCA9535MRGER": {
            "pins": 36,
            "package_type": "VQFN",
            "package_drawing": "RGE",
            "temperature_range": "Extended"
        }
    }
    ```
    """

    user_prompt = f"""Ordering information: ```{ordering_section}```
    
    Output a JSON object that defines the parameters per part number
    """

    # response = client.chat.completions.create(
    #     model="gpt-4o-mini",
    #     response_format={"type": "json_object"},
    #     messages=[
    #         {"role": "system", "content": system_prompt},
    #         {"role": "user", "content": user_prompt},
    #     ],
    # )
    return {
        "RN4870-V/RMXXX": {
            "pins": 33,
            "antenna": "On-Board",
            "shielding": "Yes",
            "operating_temperature_range": "Normal",
        },
        "RN4870U-V/RMXXX": {
            "pins": 30,
            "antenna": "External",
            "shielding": "No",
            "operating_temperature_range": "Normal",
        },
        "RN4871-V/RMXXX": {
            "pins": 16,
            "antenna": "On-Board",
            "shielding": "Yes",
            "operating_temperature_range": "Normal",
        },
        "RN4871U-V/RMXXX": {
            "pins": 17,
            "antenna": "External",
            "shielding": "No",
            "operating_temperature_range": "Normal",
        },
        "RN4870-I/RMXXX": {
            "pins": 33,
            "antenna": "On-Board",
            "shielding": "Yes",
            "operating_temperature_range": "Extended",
        },
        "RN4871-I/RMXXX": {
            "pins": 16,
            "antenna": "On-Board",
            "shielding": "Yes",
            "operating_temperature_range": "Extended",
        },
    }


if __name__ == "__main__":
    # Read in markdown file and extract pin section
    path = "/Users/andrewmello/Development/SmartCaliper/macos/RN4870-71-Bluetooth-Low-Energy-Module-DS50002489.md"
    md = SimpleMarkdown.parse(path)
    pin_section = md.get_all_text_from_search("Pin")
    ordering_section = md.get_all_text_from_search("Order")
    ordering_info = process_ordering_section(ordering_section)
    pins = generate_pins(pin_section)
    print(pins)

    # digikey_login()
    # dpn = inquirer.text("Enter the DigiKey part number:").execute()
    # use_ai_prompt = inquirer.confirm(
    #     "Would you like to use AI to generate the pins?"
    # ).execute()
    # create(dpn, use_ai_prompt)
