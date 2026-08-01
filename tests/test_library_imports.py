import ast
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


def test_library_sourcing_metadata_uses_canonical_types():
    assignments = {"lead_time": [], "lifecycle": []}
    for path in Path("earthground/library").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if not isinstance(target, ast.Attribute) or target.attr not in assignments:
                continue
            assignments[target.attr].append((path, node.value))

    assert assignments["lead_time"]
    assert assignments["lifecycle"]
    for path, value in assignments["lead_time"]:
        assert isinstance(value, ast.Call), path
        assert isinstance(value.func, ast.Attribute), path
        assert value.func.attr == "weeks", path
    for path, value in assignments["lifecycle"]:
        assert isinstance(value, ast.Attribute), path
        assert isinstance(value.value, ast.Attribute), path
        assert value.value.attr == "Lifecycle", path
