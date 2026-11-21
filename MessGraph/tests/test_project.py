"""Projektdateien (*.mgproj): speichern, öffnen, verschobener Projektordner."""
import json
import shutil
from pathlib import Path

import pytest

from messgraph import project
from messgraph.data_model import LoadError

DEMO = Path(__file__).resolve().parent.parent / "demo_data"


def sample_session(folder: Path) -> dict:
    return {"format": "MessGraph-Ansicht", "version": 1,
            "files": [{"path": str(folder / "log.blf"), "relpath": "log.blf",
                       "databases": {"dbc": [[str(folder / "db" / "motor.dbc"), 1]],
                                     "arxml": [[str(folder / "db" / "batt.arxml"), 0]],
                                     "a2l": [str(folder / "db" / "ecu.a2l")], "a2l_convert": False, "cdd": []},
                       "computed": [{"name": "P", "unit": "W", "formula": "{U} * {I}", "comment": ""}]}],
            "matrix": [2, 1], "graphs": [{"title": "G", "signals": [{"file": "x", "name": "U"}]}],
            "options": {"theme": "light"}}


def test_build_write_read_roundtrip(tmp_path):
    session = sample_session(tmp_path)
    settings = {"export": {"paper": "A3", "report_stats": ["max"]}, "language": "Thai", "last_dir": "/x",
                "compare_tolerance": 2.5, "databases_last": session["files"][0]["databases"]}
    data = project.build(session, settings, "Prüfstand 3", "Lauf nach Update", {"filter": "temp"}, str(tmp_path))
    assert data["settings"]["export"]["paper"] == "A3" and data["settings"]["compare_tolerance"] == 2.5
    assert "language" not in data["settings"] and "last_dir" not in data["settings"]     # persönliche Einstellungen nicht
    assert data["database_relpaths"][str(tmp_path / "db" / "motor.dbc")] == str(Path("db") / "motor.dbc")
    path = project.write(str(tmp_path / "p"), data)
    assert path.endswith(".mgproj") and not Path(path + ".tmp").exists()
    again = project.read(path)
    assert again["name"] == "Prüfstand 3" and again["session"]["matrix"] == [2, 1] and again["ui"]["filter"] == "temp"
    assert project.summary(again) == {"files": 1, "graphs": 1, "signals": 1, "computed": 1, "databases": 3}


def test_read_rejects_other_files(tmp_path):
    bad = tmp_path / "x.mgproj"
    bad.write_text(json.dumps({"format": "MessGraph-Ansicht", "files": []}))
    with pytest.raises(LoadError, match="kein MessGraph-Projekt"):
        project.read(str(bad))
    bad.write_text(json.dumps({"format": project.FORMAT, "version": 99, "session": {}}))
    with pytest.raises(LoadError, match="neueren"):
        project.read(str(bad))
    bad.write_text("{kaputt")
    with pytest.raises(LoadError, match="JSON"):
        project.read(str(bad))


def test_relocate_moved_project_folder(tmp_path):
    old = tmp_path / "alt"
    (old / "db").mkdir(parents=True)
    for name in ("motor.dbc", "batt.arxml", "ecu.a2l"):
        (old / "db" / name).write_text("x")
    session = sample_session(old)
    data = project.build(session, {"databases_last": json.loads(json.dumps(session["files"][0]["databases"]))},
                         "P", "", None, str(old))
    new = tmp_path / "neu"
    shutil.copytree(old, new)
    shutil.rmtree(old)                                         # alter Ort existiert nicht mehr
    missing = project.relocate(data, str(new))
    config = data["session"]["files"][0]["databases"]
    assert not missing
    assert config["dbc"] == [[str(new / "db" / "motor.dbc"), 1]] and config["a2l"] == [str(new / "db" / "ecu.a2l")]
    assert data["settings"]["databases_last"]["arxml"][0][0] == str(new / "db" / "batt.arxml")
    (new / "db" / "ecu.a2l").unlink()
    data = project.build(sample_session(new), {}, "P", "", None, str(new))
    assert project.relocate(data, str(new)) == [str(new / "db" / "ecu.a2l")]


def test_session_remap_moves_everything_to_target(tmp_path):
    from messgraph.session import remap
    a, b, c = str(tmp_path / "a.csv"), str(tmp_path / "b.csv"), str(tmp_path / "c.asc")
    data = {"files": [{"path": a, "relpath": "a.csv", "ascii": {"header_line": 7},
                       "databases": {"dbc": [["x.dbc", 1]]}, "computed": [{"name": "P", "formula": "{U}*{I}"}]},
                      {"path": c, "computed": [{"name": "P", "formula": "{U}"}, {"name": "Q", "formula": "{I}"}]}],
            "graphs": [{"title": "G", "legend": "se", "signals": [
                {"file": a, "name": "U", "color": [1, 2, 3], "limits": [0, 5], "axis": "right"},
                {"file": c, "name": "U"}, {"file": c, "name": "Q"}]}]}
    out = remap(data, {a: b})
    assert [f["path"] for f in out["files"]] == [b, c] and "relpath" not in out["files"][0]
    first = out["files"][0]
    assert first["ascii"] == {"header_line": 7} and first["databases"]["dbc"] == [["x.dbc", 1]]
    sig = out["graphs"][0]["signals"][0]
    assert sig == {"file": b, "name": "U", "color": [1, 2, 3], "limits": [0, 5], "axis": "right"}
    assert data["files"][0]["path"] == a                              # Original unverändert
    merged = remap(data, {a: b, c: b}, keep=[a])                      # zwei Quellen auf ein Ziel
    assert [f["path"] for f in merged["files"]] == [b, a]
    assert [x["name"] for x in merged["files"][0]["computed"]] == ["P", "Q"]       # erste Formel P gilt
    assert [(s["file"], s["name"]) for s in merged["graphs"][0]["signals"]] == [(b, "U"), (b, "Q")]
