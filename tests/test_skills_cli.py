from pathlib import Path

from earthground.cli import main

REPOSITORY_ROOT = Path(__file__).parents[1]
SOURCE_SKILLS = REPOSITORY_ROOT / "earthground" / "skills"


def _directory_files(root: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
        and path.name != "__init__.py"
        and "__pycache__" not in path.parts
    }


def test_skills_add_decline_makes_no_changes(tmp_path, monkeypatch, capsys):
    destination = tmp_path / ".claude" / "skills"

    def decline() -> str:
        assert not destination.exists()
        return "n"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", decline)

    assert main(["skills", "add"]) == 0

    output = capsys.readouterr()
    assert f"Destination: {destination}" in output.out
    assert "Continue? [y/N]" in output.out
    assert "Cancelled. No files were changed." in output.out
    assert output.err == ""
    assert not (tmp_path / ".claude").exists()


def test_skills_add_eof_makes_no_changes(tmp_path, monkeypatch, capsys):
    def end_of_input() -> str:
        raise EOFError

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", end_of_input)

    assert main(["skills", "add"]) == 0
    assert "Cancelled. No files were changed." in capsys.readouterr().out
    assert not (tmp_path / ".claude").exists()


def test_skills_add_confirmation_copies_every_packaged_skill(
    tmp_path, monkeypatch, capsys
):
    destination = tmp_path / ".claude" / "skills"

    def accept() -> str:
        assert not destination.exists()
        return "yes"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", accept)

    assert main(["skills", "add"]) == 0

    output = capsys.readouterr()
    assert output.err == ""
    assert "Added 5 Earthground skills" in output.out
    assert _directory_files(destination) == _directory_files(SOURCE_SKILLS)


def test_skills_add_updates_matching_files_and_preserves_other_files(
    tmp_path, monkeypatch, capsys
):
    destination = tmp_path / ".claude" / "skills"
    existing_skill = destination / "earthground-cli"
    existing_skill.mkdir(parents=True)
    existing_skill.joinpath("SKILL.md").write_text(
        "outdated",
        encoding="utf-8",
    )
    custom_file = existing_skill / "custom-notes.md"
    custom_file.write_text("keep me", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda: "y")

    assert main(["skills", "add"]) == 0

    output = capsys.readouterr()
    assert "Existing skill directories will be updated: earthground-cli" in output.out
    assert (
        existing_skill.joinpath("SKILL.md").read_bytes()
        == SOURCE_SKILLS.joinpath("earthground-cli", "SKILL.md").read_bytes()
    )
    assert custom_file.read_text(encoding="utf-8") == "keep me"


def test_skills_add_copy_error_is_reported_after_confirmation(
    tmp_path, monkeypatch, capsys
):
    tmp_path.joinpath(".claude").write_text("not a directory", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda: "yes")

    assert main(["skills", "add"]) == 1

    output = capsys.readouterr()
    assert "Continue? [y/N]" in output.out
    assert "earthground skills add: error:" in output.err
