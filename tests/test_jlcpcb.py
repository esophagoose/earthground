import difflib
import pathlib

import pytest

from earthground.exporters.jlcpcb import JlcPcb
from earthground.library.integrated_circuits.voltage_regulators.linear import \
    lm317


def test_jlcpcb_bom_export_no_module(tmp_path: pathlib.Path):
    """Export no module BOM positions and compare to golden CSV.

    Uses pytest's tmp_path fixture for temporary file output and compares
    against the golden reference file in testdata/.
    """
    design = lm317.LM317AMDTX.generate_design(3.3)
    out_path = JlcPcb(design).generate_bom(
        output_folder=str(tmp_path),
        filename="test_bom.csv",
    )

    # Golden reference file (relative to project root)
    project_root = pathlib.Path(__file__).parent.parent
    golden_path = project_root / "testdata" / "bom.csv"

    # Compare contents (text), not just metadata, and show a helpful diff on failure
    assert golden_path.is_file(), f"Missing golden BOM file: {golden_path}"
    export_text = out_path.read_text().splitlines(keepends=True)
    golden_text = golden_path.read_text().splitlines(keepends=True)

    if export_text != golden_text:
        diff = "".join(
            difflib.unified_diff(
                golden_text,
                export_text,
                fromfile=str(golden_path),
                tofile=str(out_path),
            )
        )
        pytest.fail(
            f"Exported BOM {out_path} does not match golden {golden_path}:\n{diff}"
        )


def test_jlcpcb_bom_export_one_module(tmp_path: pathlib.Path):
    """Export one module BOM positions and compare to golden CSV.

    Uses pytest's tmp_path fixture for temporary file output and compares
    against the golden reference file in testdata/.
    """
    design = lm317.LM317AMDTX.generate_design(3.3)
    design.add_module(lm317.LM317AMDTX.generate_design(3.3))
    out_path = JlcPcb(design).generate_bom(
        output_folder=str(tmp_path),
        filename="test_bom.csv",
    )

    # Golden reference file (relative to project root)
    project_root = pathlib.Path(__file__).parent.parent
    golden_path = project_root / "testdata" / "bom_modules.csv"

    # Compare contents (text), not just metadata, and show a helpful diff on failure
    assert golden_path.is_file(), f"Missing golden BOM file: {golden_path}"
    export_text = out_path.read_text().splitlines(keepends=True)
    golden_text = golden_path.read_text().splitlines(keepends=True)

    if export_text != golden_text:
        diff = "".join(
            difflib.unified_diff(
                golden_text,
                export_text,
                fromfile=str(golden_path),
                tofile=str(out_path),
            )
        )
        pytest.fail(
            f"Exported BOM {out_path} does not match golden {golden_path}:\n{diff}"
        )
