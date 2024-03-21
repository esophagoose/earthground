import json
import os
import pathlib
from typing import Dict

import digikey
import openai
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
    744: "motor_drivers",
    739: "voltage_regulators/switching",
    399: "fpc",
}


def get_credentials(service: str):
    path = pathlib.Path.home() / ".credentials" / f"{service}.json"
    with open(path, "r") as f:
        data = json.load(f)
        return data.get("client_id"), data.get("client_secret")


def get_component_from_digikey(part_number: str):
    cache = str(pathlib.Path.home() / ".credentials/")
    cid, password = get_credentials("digikey")
    os.environ["DIGIKEY_CLIENT_ID"] = cid
    os.environ["DIGIKEY_CLIENT_SECRET"] = password
    os.environ["DIGIKEY_CLIENT_SANDBOX"] = "False"
    os.environ["DIGIKEY_STORAGE_PATH"] = cache

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


def generate_pins(datasheet):
    client = openai.OpenAI()

    print(f"Open the datasheet in your browser: {datasheet}")
    text_prompt = inquirer.text("Copy the pin table here:").execute()
    system_prompt = """You create json objects of pin indexes to names for various
    footprints from text from a datasheet. There should be columns for
    pin names, pin indexes, and maybe pin descriptions. The input will be text
    and you output a json object that looks like this:
    {
        "pins": [
            {
                "name": parsed_pin_name,
                "index": parsed_pin_index,
                "comment": parsed_pin_comment
            }
        ]
    }"""

    user_prompt = f"""{text_prompt} \nOutput a json object from the text below 
    where every object in the json list has three keys: "name", "index", 
    "comment" for the pin name, pin index, and pin description (if present)\n"""
    print()

    column_prompt = (
        "If there's multiple columns of pin indices for",
        "for different footprints, escribe which column to use. Else leave blank",
    )
    column = inquirer.text(column_prompt).execute()
    if column:
        user_prompt += f"To find the pin indexes, {column}"

    response = client.chat.completions.create(
        model="gpt-4-turbo-preview",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    content = response.choices[0].message.content
    pins = json.loads(content).get("pins")
    for pin in pins:
        print(f"  {pin['index']}: {pin['name']},  # {pin['comment'][:10]}")
    inquirer.confirm("Is this correct?").execute()
    return pins


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


if __name__ == "__main__":
    dpn = inquirer.text("Enter the DigiKey part number:").execute()
    folder, attr = get_component_from_digikey(dpn)
    use_ai_prompt = "Would you like to use AI to generate the pins?"
    ai = inquirer.confirm(use_ai_prompt).execute()
    part_pins = None
    if ai:
        part_pins = generate_pins(attr["datasheet"])
    write_component(folder, attr, part_pins)
