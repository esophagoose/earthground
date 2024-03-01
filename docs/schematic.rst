Schematic
=========================

The `common/schematic.py` module is a core component of the Earthground library, designed to facilitate the creation and manipulation of software-defined electronic schematics. This document outlines how to effectively utilize this module in your projects.

Installation
------------

Before using `common/schematic.py`, ensure you have installed Earthground and its dependencies:

.. code-block:: console

   pip install earthground

Basic Usage
-----------

To get started with `common/schematic.py`, import the module into your Python script:

.. code-block:: python

   from common import schematic

Creating a New Schematic
------------------------

You can create a new schematic by instantiating the `Schematic` class:

.. code-block:: python

   design = schematic.Design()

Adding Components
-----------------

To add components to your schematic, use the `add_component` method:

.. code-block:: python

   design.add_component('resistor', value='10k', footprint='0805')

Connecting Components
---------------------

Components can be interconnected using the `connect` method:

.. code-block:: python

   design.connect('resistor1', 'pin1', 'resistor2', 'pin2')

Exporting the Schematic
-----------------------

Once your schematic is complete, you can export it to various formats, such as JSON or XML, for further processing or visualization:


.. autofunction:: common.schematic.Design.connect

.. autoexception:: ValueError


.. code-block:: python

   design.export('design.json', format='json')

Advanced Features
-----------------

`common/schematic.py` also supports more advanced features, such as automatic component selection based on parameters, and integration with PCB layout tools. Refer to the Earthground documentation for more details on these advanced capabilities.

.. autosummary::
   :toctree: generated

   common.schematic

Support and Contribution
------------------------

For support, questions, or contributions to the `common/schematic.py` module, please visit the Earthground GitHub repository or contact the development team.
