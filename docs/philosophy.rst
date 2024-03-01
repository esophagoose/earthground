Philosophy of Software-Defined Circuits
=======================================

How Should I Go About Using Earthground?
----------------------------------------
Coming from traditional ECAD tools, Earthground should feel intuitive but there's a few shifts in thinking to make this tool effective.

Create Good Components
----------------------

Components are the cornerstone of Earthground. Most the modularity and time-saving comes from reading the datasheet once and implementing it into a component.

- All component be their own class and must inherit `Component`
- If the pins are different between packages, make new classes for each
- Reuse existing footprints when possible, and if creating a new footprint. Make sure to parameterize it.
- Create a reference design using a component with all available options from the datasheet
- Use enums to switch between options
- Writing component functions and enums from the viewpoint of using the part not the IC
Bad:

.. code-block:: python

   class CfgPin1(enum.Enum):
       LOW = "GND"
       HIGH = "VCC

Good:

.. code-block:: python

   class BootConfig(enum.Enum):
       BOOTLOADER_MODE = "GND"
       APPLICATION_MODE = "VCC
