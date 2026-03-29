import importlib
from pathlib import Path

import pytest


def _library_modules() -> list[str]:
    root = Path("earthground/library")
    modules = []
    for path in sorted(root.rglob("*.py")):
        if path.name == "__init__.py":
            modules.append(".".join(path.parent.parts))
        else:
            modules.append(".".join(path.with_suffix("").parts))
    return modules


@pytest.mark.parametrize("module_name", _library_modules())
def test_library_module_imports(module_name: str):
    importlib.import_module(module_name)
