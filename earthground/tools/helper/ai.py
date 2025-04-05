import hashlib
import json
import logging
import os
import pathlib
from typing import Any, Dict, List

import digikey
import openai

LOG = logging.getLogger("OPENAI")


class ComponentAI:
    def __init__(self, cache_dir: str = ".cache/ai_responses"):
        self.client = openai.OpenAI()
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def get_credentials(self, service: str):
        path = pathlib.Path.home() / ".credentials" / f"{service}.json"
        with open(path, "r") as f:
            data = json.load(f)
            return data.get("api_key"), data.get("organization")

    def _get_cache_path(self, prompt_hash: str, response_type: str) -> str:
        return os.path.join(self.cache_dir, f"{prompt_hash}_{response_type}.json")

    def _hash_prompt(self, *args) -> str:
        """Create a hash from the prompt arguments to use as a cache key."""
        combined = json.dumps(args, sort_keys=True)
        return hashlib.md5(combined.encode()).hexdigest()

    def _check_cache(self, prompt_hash: str, response_type: str) -> Any:
        """Check if response is cached and return it if found."""
        cache_path = self._get_cache_path(prompt_hash, response_type)
        if os.path.exists(cache_path):
            with open(cache_path, "r") as f:
                return json.load(f)
        return None

    def _save_to_cache(
        self, prompt_hash: str, response_type: str, response: Any
    ) -> None:
        """Save response to cache."""
        cache_path = self._get_cache_path(prompt_hash, response_type)
        with open(cache_path, "w") as f:
            json.dump(response, f)

    def _query_json(self, system_prompt: str, user_prompt: str):
        prompt_hash = self._hash_prompt(system_prompt, user_prompt)
        cached_response = self._check_cache(prompt_hash, "json")

        if cached_response:
            LOG.info("Cached JSON response found")
            return cached_response

        LOG.warning("Using AI - Querying for JSON response")
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        result = json.loads(response.choices[0].message.content)

        self._save_to_cache(prompt_hash, "json", result)
        return result

    def _query_text(self, prompt: str):
        """
        Query OpenAI for a text response.

        Args:
            prompt: The prompt to send to the OpenAI API.

        Returns:
            The text response from the OpenAI API.
        """
        prompt_hash = self._hash_prompt(prompt)
        cached_response = self._check_cache(prompt_hash, "text")

        if cached_response:
            LOG.info("Cached text response found")
            return cached_response

        LOG.warning("Using AI - Querying for text response")
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        result = response.choices[0].message.content

        self._save_to_cache(prompt_hash, "text", result)
        return result

    def generate_pins(self, pin_section: str, package_types: List[str]):
        LOG.info("Generating pins from datasheet section")
        system_prompt = """You create json objects of pin indexes to names for various
        footprints from text from a datasheet. There should be columns for
        pin names, pin indexes, and pin descriptions. Keep pins description comments
        concise and a maximum of 10 words. If there are multiple columns of pin indices
        for different footprints available, include an entry for each unique footprint. 
        The pin names should mostly match for all footprints. If the index is comma separated, 
        make unique entries for each pin index with the same pin name.

        The input will be text and you output a json object that looks like this:
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
                    ],
                    "package_type": parsed_package_type
                }
            ]
        }
        ```
        """

        user_prompt = f"""```{pin_section}``` \nOutput a json object from the markdown above 
        where every object in the json list has three keys: "name" for the pin name, "index" for the pin index, 
        and "comment" for the pin description (if present) for each footprint. The package type should be one or more
        of the following: {", ".join(package_types)}
        """
        result = self._query_json(system_prompt, user_prompt)
        LOG.debug(
            f"Generated pin data with {len(result.get('footprints', []))} footprints"
        )
        return result

    def generate_ordering_info(
        self, ordering_section: str
    ) -> Dict[str, Dict[str, str]]:
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
                "status": "ACTIVE",
                "pins": 24,
                "package_type": "SSOP",
                "package_drawing": "DB",
                "temperature_range": "-20 to 65"
            },
            "TCA9535MRGER": {
                "status": "ACTIVE",
                "pins": 36,
                "package_type": "VQFN",
                "package_drawing": "RGE",
                "temperature_range": "-40 to 85"
            }
        }
        ```
        """

        user_prompt = f"""Ordering information: ```{ordering_section}```
        
        Output a JSON object that defines the parameters per part number
        """

        result = self._query_json(system_prompt, user_prompt)
        LOG.debug(f"Generated ordering info with {len(result)} part numbers")
        return result

    def generate_summary(self, summary: str) -> str:
        prompt = f"""Included is a markdown overview of a electrical component.
        Extract the summary of the component from the overview and only return a
        maximum of two sentences.

        Overview:
        ```
        {summary}
        ```
        """

        result = self._query_text(prompt)
        LOG.debug(f'Generated summary: "{result}"')
        return result

    def generate_reference_design(self, content: str) -> str:
        prompt = f"""Included is a datasheet section on the application of a electrical component.
        Please describe the reference design for the component using equations to represent component
        values.

        Overview:
        ```
        {content}
        ```
        """

        result = self._query_text(prompt)
        LOG.debug(f'Generated reference design: "{result}"')

        prompt = f"""Given the following reference design, please generate python code to
        create a reference design for the component.

        Reference design:
        ```
        {result}
        ```
        """

        design = self._query_text(prompt)
        return design

    def generate_ratings(self, ratings: str) -> Dict[str, List[Dict[str, str]]]:
        system_prompt = """You are an expert in electrical components. Your task is to extract ratings from datasheet sections and format them as JSON objects. The input will be a markdown section on the ratings of a electrical component.
        The output should be a json object that lists the variable notation, description, minimum, typical, and maximum values for each rating. If one isn't provided, use "" for the value
        Example input:
        ```
        | Name | Description | Min | Typ | Max | Units |
        |--------|-------------|-----|-----|-----|-----|
        | V_CC | Supply Voltage | 2.7 | 3.3 | 5.5 | V |
        | I_CC | Supply Current | | 2.0 | 2.2 | mA |
        ```
        Example output:
        ```
        {
            "ratings": [
                {
                    "symbol": "V_CC",
                    "description": "Supply Voltage",
                    "min": "2.7",
                    "typ": "3.3",
                    "max": "5.5",
                    "units": "V"
                },
                {
                    "symbol": "I_CC",
                    "description": "Supply Current",
                    "min": "",
                    "typ": "2.0",
                    "max": "2.2",
                    "units": "mA"
                }
        """

        user_prompt = f"""Extract the ratings from the section and return them as a json object.

        Ratings:
        ```
        {ratings}
        ```
        """

        result = self._query_json(system_prompt, user_prompt)
        LOG.debug(f"Generated ratings: {result}")
        return result

    def get_unique_packages(self, ordering_section: str) -> List[str]:
        system_prompt = """You are an expert in electrical components. 
        Extract unique footprints, also known as package drawings or package 
        types, from the ordering section of a datasheet. The output should be a JSON 
        object where the key is "footprints" and the value is a list of footprints or
        package types.
        
        Example output:
        ```
        {
            "footprints": ["TSSOP", "SSOP", "QFN", "DFN"]
        }
        ```
            
        """

        user_prompt = f"""Extract the package information from the ordering section and return as a JSON object.
        
        Ordering Section:
        ```
        {ordering_section}
        ```
        """

        result = self._query_json(system_prompt, user_prompt)
        LOG.debug(f"Generated package information: {result}")
        return result.get("footprints", [])
