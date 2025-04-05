import logging
import pathlib
from typing import List

import colorlog

import earthground.tools.helper.ai as ai_lib
import earthground.tools.helper.python_writer as pw_lib
import earthground.tools.helper.digikey as digikey_lib
import earthground.tools.helper.markdown as markdown_lib

handler = colorlog.StreamHandler()
handler.setFormatter(
    colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s - %(levelname)s: [%(name)s] %(message)s",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
    )
)

logging.basicConfig(level=logging.INFO, handlers=[handler])
LOG = logging.getLogger("ComponentCreator")
BASE_LIBRARY_PATH = pathlib.Path("earthground/library")
RATINGS = [
    ("abs_max", "Absolute Maximum Ratings"),
    ("recommended", "Recommended Operating Conditions"),
]


def normalize_dict_list(dict_list):
    """
    Normalizes a list of dictionaries by:
    1. Removing keys that have the same value across all dictionaries
    2. Removing keys that are not present in all dictionaries

    :param dict_list: A list of dictionaries to normalize
    :type dict_list: List[Dict]
    :return: A list of normalized dictionaries
    :rtype: List[Dict]
    """
    LOG.info(f"Normalizing list of {len(dict_list) if dict_list else 0} dictionaries")
    if not dict_list or not isinstance(dict_list, list):
        LOG.warning("Input is not a valid list of dictionaries")
        return dict_list

    # Find all unique keys across all dictionaries
    all_keys = set()
    for d in dict_list:
        all_keys.update(d.keys())
    LOG.debug(f"Found {len(all_keys)} unique keys across all dictionaries")

    # Find keys present in all dictionaries
    common_keys = set(all_keys)
    for d in dict_list:
        common_keys &= set(d.keys())
    LOG.debug(f"Found {len(common_keys)} common keys across all dictionaries")

    # Check if all dictionaries have the same value for each common key
    keys_with_same_value = set()
    for key in common_keys:
        values = [d[key] for d in dict_list]
        if all(value == values[0] for value in values):
            keys_with_same_value.add(key)

    # Remove keys that are not common or have the same value across all dictionaries
    keys_to_keep = common_keys - keys_with_same_value
    LOG.debug(f"Keeping {len(keys_to_keep)} keys after normalization")

    # Create new dictionaries with only the keys to keep
    normalized_dict_list = []
    for d in dict_list:
        normalized_dict = {k: d[k] for k in keys_to_keep}
        normalized_dict_list.append(normalized_dict)

    return normalized_dict_list


class ComponentCreator:
    def __init__(self, mpn: str, markdown_path: str):
        self.md = markdown_lib.SimpleMarkdown.parse(markdown_path)
        self.ai = ai_lib.ComponentAI()
        self.cw = pw_lib.PythonWriter(BASE_LIBRARY_PATH)
        self.digikey = digikey_lib.DigikeyComponentCreator()
        self.params = self.digikey.get_component_details(mpn)
        self._ratings = {}
        self._component = pw_lib.ClassInstance(self.params.mpn, base_class="cmp.Component")

    def _generate_electrical_ratings(self, section_name: str) -> List[pw_lib.Variable]:
        text = self.md.get_all_text_from_search([section_name])
        ratings = self.ai.generate_ratings(text)
        variables = []
        for rating in ratings.get("ratings", []):
            if not rating.get("symbol").strip():
                continue
            params = []
            for key in ["min", "typ", "max", "units"]:
                value = rating.get(key)
                if not value:
                    continue
                value = f"'{value}'" if key == "units" else value
                params.append(f"{key}={value}")
            cv = pw_lib.Variable(
                name=pw_lib.clean_variable_name(rating.get("symbol")).lower(),
                value=f"sv.ValueBounds({', '.join(params)})",
                comment=rating["description"],
            )
            variables.append(cv)
        return variables

    def process_electrical_ratings(self) -> List[pw_lib.Variable]:
        LOG.info("Processing electrical ratings")
        self.cw.add_import("collections", function="namedtuple")
        self.cw.add_import("earthground.standard_values", as_name="sv")
        for variable_name, section_name in RATINGS:
            variables = self._generate_electrical_ratings(section_name)
            self._ratings[variable_name] = variables
            class_name = variable_name.title().replace("_", "")
            ntuple = f"namedtuple('{class_name}', {[r.name for r in variables]})"
            self.cw.add_module_variable(class_name, ntuple)
            self._component.class_vars.extend(variables)

    def process_summary(self):
        LOG.info("Generating component summary")
        first_pages = self.md.get_lines(0, 100)
        self._component.docstring = self.ai.generate_summary(first_pages)

    def process_params(self):
        LOG.info("Processing component parameters")
        self._component.instance_vars.extend([
            pw_lib.Variable(name="manufacturer", value=self.params.manufacturer),
            pw_lib.Variable(name="description", value=self.params.description),
            pw_lib.Variable(name="datasheet", value=self.params.datasheet),
        ])
        self._component.instance_vars.extend(pw_lib.Variable.from_dict(self.params.attributes))

    def process_ordering_info(self):
        LOG.info("Processing ordering information")
        sections = ["Order", "PACKAGING INFORMATION"]
        ordering_section = self.md.get_all_text_from_search(sections)
        ordering_info = self.ai.generate_ordering_info(ordering_section)
        package_types = self.ai.get_unique_packages(ordering_section)
        LOG.info(f"Retrieved package types: {package_types}")
        values = normalize_dict_list(list(ordering_info.values()))
        part_numbers = dict(zip(ordering_info.keys(), values))
        first_part_number = part_numbers[list(part_numbers.keys())[0]]
        parameters = [f"{k}: {type(v).__name__}" for k, v in first_part_number.items()]
        packages = {k: list(v.values()) for k, v in part_numbers.items()}   
        self._component.constructor_args = parameters     
        self.cw.add_import("enum")
        enum_class = pw_lib.ClassInstance(
            class_name="LSF0102Packages",
            base_class="enum.Enum",
            docstring="LSF0102 Packages\n\nValues are: "
            + ", ".join(first_part_number.keys()).replace("_", " "),
            class_vars=pw_lib.Variable.from_dict(packages),
            has_init=False,
        )
        self.cw.add_class(enum_class)
        return package_types

    def run(self):
        # Find component and datasheet and parse into python
        LOG.info("Starting component creator")
        self.cw.add_import("earthground.components", as_name="cmp")
        self.process_summary()
        self.process_params()
        packages = self.process_ordering_info()
        self.process_electrical_ratings()
        pin_section = self.md.get_all_text_from_search("Pin")
        pins = self.ai.generate_pins(pin_section, packages)
        
        # Write component to file       
        self.cw.add_class(self._component)
        LOG.info("Writing Python class to file")
        self.cw.write(self.params.path / f"{self.params.mpn.lower()}.py")
        return self


if __name__ == "__main__":
    path = "/Users/andrewmmello/Development/earthground/examples/lsf0102.md"
    creator = ComponentCreator("296-39070-6-ND", path).run()


    # import code
    # code.interact(local=dict(globals(), **locals()))

    # pprint.pprint(pins)
    # content = [
    #     summary,
    #     md.get_all_text_from_search("Application"),
    #     md.get_text_from_chapter(7),
    # ]
    # # print("\n".join(content))
    # reference_design = ai.generate_reference_design(content)
    # print(reference_design)
    # print("\n".join(md._raw))
    # digikey_login             ()
    # dpn = inquirer.text("Enter the DigiKey part number:").execute()
    # use_ai_prompt = inquirer.confirm(
    #     "Would you like to use AI to generate the pins?"
    # ).execute()
    # create(dpn, use_ai_prompt)
