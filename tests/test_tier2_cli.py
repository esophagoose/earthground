import earthground.components as cmp
import earthground.standard_values as sv
from earthground.cli import main
from earthground.schematic import Design
from earthground.straps import StrapLevel, StrapPin


class CliStrap(cmp.Component):
    strap_pins = (
        StrapPin(
            id="mode",
            pin="MODE",
            reference="VCC",
            levels=(
                StrapLevel(name="LOW", ratio=sv.ratio(0, max=0.2), meaning="low"),
                StrapLevel(name="MID", ratio=sv.ratio(0.4, max=0.6), meaning="middle"),
                StrapLevel(name="HIGH", ratio=sv.ratio(0.8, max=1), meaning="high"),
            ),
            internal_pull_up=sv.ohms(100_000, typ=100_000, max=100_000),
            internal_pull_down=sv.ohms(100_000, typ=100_000, max=100_000),
        ),
    )

    def __init__(self):
        super().__init__()
        self.pins = cmp.PinContainer.from_dict({1: "VCC", 2: "MODE"}, self)


def strap_design():
    design = Design("CLI straps")
    device = design.add_component(CliStrap())
    design.join_net(device.pins.by_name("VCC"), "P1V8")
    design.join_net(device.pins.by_name("MODE"), "MODE")
    design.expect_strap(device, "mode", "MID", "floating default")
    return design


def test_straps_cli_prints_resolved_report(monkeypatch, capsys):
    monkeypatch.setattr(
        "earthground.cli.analysis_reports.compile_design",
        lambda project: strap_design(),
    )

    assert main(["straps", "."]) == 0
    output = capsys.readouterr()
    assert output.err == ""
    assert "U1.MODE" in output.out
    assert "MID" in output.out


def test_thermal_cli_writes_csv_and_reports_unknowns(monkeypatch, tmp_path, capsys):
    design = Design("CLI thermal")
    design.add_component(cmp.Capacitor("100n", 10))
    monkeypatch.setattr(
        "earthground.cli.analysis_reports.compile_design", lambda project: design
    )
    output_path = tmp_path / "thermal.csv"

    assert main(["thermal", ".", "--output", str(output_path)]) == 1
    output = capsys.readouterr()
    assert output.err == ""
    assert "1 unresolved" in output.out
    assert output_path.is_file()
    assert "power dissipation" in output_path.read_text()
