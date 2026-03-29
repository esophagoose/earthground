import base64
import io
import json

import openai
import PIL.ImageGrab
from InquirerPy import inquirer


def generate_pins():
    client = openai.OpenAI()

    inquirer.text("Take a screenshot of the pin mapping:").execute()
    image = PIL.ImageGrab.grabclipboard()
    if not image:
        raise RuntimeError("No image found in clipboard.")
    image_bytes = io.BytesIO()
    image.save(image_bytes, format="PNG")
    base64_image = base64.b64encode(image_bytes.getvalue()).decode("utf-8")

    system_prompt = """You create json objects of pin indexes to names from 
    an image from a electrical datasheet. You output a json object that
    looks like this:
    {
        "pins": [
            {
                "name": parsed_pin_name,
                "index": parsed_pin_index,
            }
        ]
    }"""

    user_prompt = """Output a json object from the text below 
    where every object in the json list has two keys: "name", "index" for the
    pin name and pin index\n"""
    print()

    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    },
                ],
            },
        ],
    )

    import code

    code.interact(local=locals())
    content = response.choices[0].message.content
    pins = json.loads(content).get("pins")
    for pin in pins:
        print(f"  {pin['index']}: {pin['name']},  # {pin['comment'][:10]}")
    inquirer.confirm("Is this correct?").execute()
    return pins


if __name__ == "__main__":
    generate_pins()
