import enum
import json

import openai
from InquirerPy import inquirer

import earthground.tools.component_creator as component_creator

RESPONSES = {
    "USB-C power delivery controller": [
        {
            "mpn": "STUSB4500",
            "description": "Stand-alone USB PD Sink controller for power sinking devices.",
        },
        {
            "mpn": "TPS25750",
            "description": "Integrated USB PD Sink and Source Power Path Management.",
        },
        {
            "mpn": "FUSB302",
            "description": "Fully-integrated Type-C PD PHY and protocol.",
        },
        {
            "mpn": "CYPD3120-40LQXI",
            "description": "USB Type-C and Power Delivery controller targeting power adapters and accessories.",
        },
        {
            "mpn": "BQ25792",
            "description": "USB-C and USB PD Source Controller with Power Path.",
        },
    ],
    "usb type-c port": [
        {
            "mpn": "ZX62D-B-5PA8",
            "description": "USB type-C receptacle connector, 5 positions, surface mount, 0.5A, 30V, with a metal shield for EMI protection",
        },
        {
            "mpn": "UTC16-G",
            "description": "USB type-C female port, 16-pin, supports USB 3.1 for fast data transfer and power delivery, suitable for PCB mount",
        },
        {
            "mpn": "UX60-MB-5ST",
            "description": "Micro USB type-B receptacle connector, 5 positions, surface mount, suitable for data and power applications",
        },
        {
            "mpn": "CUSB-C101-AJN-10",
            "description": "USB type-C, 24-pin, USB 3.1 Gen 2 compliant, supports power delivery (PD), for high-speed charging and data",
        },
    ],
    "current sense amplifier for a 0 - 5A range": [
        {
            "mpn": "INA219",
            "description": "High-Side Measurement, Bidirectional Current/Power Monitor With I2C Interface",
        },
        {
            "mpn": "INA260",
            "description": "Precision Digital Current and Power Monitor with Low-Side Measurement",
        },
        {
            "mpn": "INA226",
            "description": "Bi-Directional Current/Power Monitor with I2C Interface",
        },
        {
            "mpn": "INA210",
            "description": "Voltage Output, High or Low-Side Measurement, Bi-Directional Zero-Drift Series Current Shunt Monitor",
        },
    ],
    "buck converter rated for 20V input and 5A": [
        {
            "mpn": "LM25149-Q1",
            "description": "Automotive Grade, 6V-42V Wide Vin, Synchronous Buck Controller with 2.2MHz Switching Frequency",
        },
        {
            "mpn": "MPM3632C",
            "description": "6V-20V Input, 3A Ultra-Low Profile (1.6mm) Step-Down Power Module",
        },
        {
            "mpn": "TPS54360",
            "description": "4.5V to 60V Input, 3.5A, Step Down DC-DC Converter with Eco-mode",
        },
        {
            "mpn": "LT8614",
            "description": "42V, 4A Synchronous Step-Down Regulator with 2.5µA Quiescent Current",
        },
        {
            "mpn": "LTC7138",
            "description": "2A, 140V VIN, Low EMI Silent Switcher Buck Regulator",
        },
    ],
    "LDO low noise rated for 20V and 5A": [
        {
            "mpn": "LT1963AEQ#PBF",
            "description": "3.3V, 5A, Adjustable, Low Noise, Fast Transient Response LDO Regulator",
        },
        {
            "mpn": "ADP3338AKCZ-5.0-R7",
            "description": "5V, 1A, Low Dropout, Low Noise, BiCMOS LDO Regulator",
        },
        {
            "mpn": "TPS7A4700RGWR",
            "description": "Adjustable (1.4V to 20.5V), 1A, Ultra-Low-Noise, High-PSRR Low-Dropout Linear Regulator",
        },
        {
            "mpn": "LT3045EDD#PBF",
            "description": "500mA, Single Resistor, Low Noise, High PSRR Linear Regulator",
        },
        {
            "mpn": "LM2991S/NOPB",
            "description": "Adjustable, -20V, 1A, Low Dropout Negative Regulator",
        },
    ],
    "MCU 8-bit arduino compatible >20 GPIOs": [
        {
            "mpn": "ATMEGA328P-AU",
            "description": "8-bit AVR Microcontroller with 32K Bytes In-System Programmable Flash",
        },
        {
            "mpn": "ATMEGA2560-16AU",
            "description": "8-bit AVR Microcontroller with 256K Bytes In-System Programmable Flash",
        },
        {
            "mpn": "ATMEGA1284P-AU",
            "description": "8-bit AVR Microcontroller with 128K Bytes In-System Programmable Flash",
        },
    ],
}


def get_parts(project_description, active_component):
    input(f"continue? {active_component}")
    client = openai.OpenAI()

    system_prompt = """You create a json array of components and their manufacturer part numbers that can be used for a given project.
    The result should look like this:
    {
        "components": [
            {
                "mpn": "TCA9535",
                "description": "Low-Voltage 16-Bit I2C and SMBus Low-Power I/O Expander with Interrupt Output and Configuration Registers"
            }
        ]
    }"""

    print(f" {active_component} ".center(40, "="))
    user_prompt = f"""For the project: {project_description} \nOutput a json
    array of several manufacturer part numbers of '{active_component}' that will work for this project"\n"""

    response = client.chat.completions.create(
        model="gpt-4-turbo-preview",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    content = response.choices[0].message.content
    components = json.loads(content).get("components")
    print(f"Found:  {components}")
    return components


class PartSource(enum.Enum):
    LCSC = "lcsc"
    DIGIKEY = "digikey"


class AutoSchematic:
    def __init__(self, project_name: str) -> None:
        self.name = project_name
        self.components = []
        self._description = None
        self._component_descriptions = None
        self._source = None

    @property
    def description(self):
        if not self._description:
            msg = "Describe your project: "
            self._description = inquirer.text(msg).execute()
        return self._description

    @description.setter
    def description(self, value):
        self._description = value

    @property
    def component_descriptions(self):
        if not self._component_descriptions:
            msg = "What ICs are needed (generally or part numbers): "
            responses = inquirer.text(msg).execute().split(",")
            self._component_descriptions = [r.strip() for r in responses]
        return self._component_descriptions

    @component_descriptions.setter
    def component_descriptions(self, value):
        self._component_descriptions = value

    @property
    def source(self):
        if not self._source:
            self._source = inquirer.select(
                message="Select where parts should be in stock:",
                choices=list(PartSource) + ["None"],
            ).execute()
        return self._source

    @source.setter
    def source(self, value):
        self._source = value

    def select_component(self, component_description):
        components = RESPONSES.get(component_description)
        if not components:
            components = get_parts(self.description, component_description)
        choices = {
            f"{c['mpn']}: {c['description']}": i for i, c in enumerate(components)
        }
        selected_part = inquirer.select(
            "Select which part to use:",
            choices=list(choices.keys()) + ["Try new prompt", "None"],
        ).execute()
        if selected_part == "Try new prompt":
            msg = f"Change description for '{component_description}'"
            response = inquirer.text(msg).execute()
            return self.select_component(response)
        elif selected_part == "None":
            return None
        return components[choices[selected_part]]["mpn"]

    def run(self):
        component_creator.digikey_login()
        for ic in self.component_descriptions:
            component = self.select_component(ic)
            self.components.append(component)
            dpn = component_creator.get_digikey_part_number_from_mpn(component)
            component_creator.create(dpn, True)


if __name__ == "__main__":
    auto = AutoSchematic("USB-C Lab Power Supply")
    auto.description = "Lab Bench Top Power Supply using USB-C power delivery. it will have current limiting and adjustable voltage between 0 - 20V"
    auto.component_descriptions = [
        "USB-C power delivery controller",
        "usb type-c port",
        "current sense amplifier for a 0 - 5A range",
        "buck converter rated for 20V input and 5A",
        "LDO low noise rated for 20V and 5A",
        "MCU 8-bit arduino compatible >20 GPIOs",
    ]
    auto.source = PartSource.LCSC
    auto.run()
    print(auto.components)
