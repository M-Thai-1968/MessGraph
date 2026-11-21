import json
import os

import numpy as np
import pytest

from messgraph import definitions, formula
from messgraph.data_model import LoadError
from messgraph.loaders import load_file


def make(tmp_path, name="m.csv", factor=1):
    path = tmp_path / name
    path.write_text("t;Strom [A];Spannung [V]\n" + "".join(f"{i};{i * factor};{2 * i}\n" for i in range(10)))
    return str(path)


def test_build_write_read_roundtrip(tmp_path):
    ds = load_file(make(tmp_path))
    p = formula.add_or_replace(ds, formula.compute(ds, "P", "", "{Strom} * {Spannung}"))
    p.note = "Leistung DC"
    formula.add_or_replace(ds, formula.compute(ds, "E", "kW", "{P} / 1000"))
    target = definitions.write(str(tmp_path / "defs" / "berechnung"), definitions.build(
        [ds], "Prüfstand A", "Version 2", "M. F.", str(tmp_path / "defs")))
    assert target.endswith("berechnung.def")
    data = json.loads(open(target, encoding="utf-8").read())
    assert data["format"] == "MessGraph-Definition" and data["title"] == "Prüfstand A" and data["author"] == "M. F."
    entry = data["files"][0]
    assert entry["path"] == os.path.abspath(ds.path) and entry["relpath"] == os.path.join("..", "m.csv")
    assert entry["computed"] == [{"name": "P", "unit": "W", "formula": "{Strom} * {Spannung}", "comment": "Leistung DC"},
                                 {"name": "E", "unit": "kW", "formula": "{P} / 1000", "comment": ""}]
    assert definitions.read(target)["comment"] == "Version 2"
    (tmp_path / "x.def").write_text('{"format": "anders"}')
    with pytest.raises(LoadError):
        definitions.read(str(tmp_path / "x.def"))


def test_apply_opens_missing_file_and_chains_formulas(tmp_path):
    ds = load_file(make(tmp_path))
    formula.add_or_replace(ds, formula.compute(ds, "P", "", "{Strom} * {Spannung}"))
    formula.add_or_replace(ds, formula.compute(ds, "E", "kW", "{P} / 1000"))
    target = definitions.write(str(tmp_path / "a.def"), definitions.build([ds], "T", base_dir=str(tmp_path)))
    result = definitions.apply(target, [], load_file)          # nach Neustart: nichts geöffnet
    assert len(result.new_datasets) == 1 and not result.problems and result.title == "T"
    new = result.new_datasets[0]
    assert [c.name for c in new.channels] == ["Strom", "Spannung"]   # Datasets unverändert bis install
    assert definitions.install(result) == 2
    e = next(c for c in new.channels if c.name == "E")
    assert e.y[3] == pytest.approx(3 * 6 / 1000) and e.unit == "kW"


def test_apply_to_loaded_file_replaces_same_name_and_protects_measured(tmp_path):
    ds = load_file(make(tmp_path))
    old = formula.add_or_replace(ds, formula.compute(ds, "P", "", "{Strom} * 2"))
    data = {"format": "MessGraph-Definition", "version": 1, "files": [{"path": ds.path, "computed": [
        {"name": "P", "unit": "W", "formula": "{Strom} * {Spannung}"},
        {"name": "Strom", "unit": "", "formula": "{Spannung} * 2"}]}]}
    target = str(tmp_path / "b.def")
    open(target, "w", encoding="utf-8").write(json.dumps(data))
    result = definitions.apply(target, [ds], load_file)
    assert not result.new_datasets and any("Messsignal" in p for p in result.problems)
    definitions.install(result)
    assert old in ds.channels and old.y[3] == 18 and len(formula.computed(ds)) == 1   # an Ort und Stelle ersetzt


def test_moved_file_found_relative_or_by_signals(tmp_path):
    (tmp_path / "neu").mkdir()
    ds = load_file(make(tmp_path / "neu"))
    formula.add_or_replace(ds, formula.compute(ds, "P", "", "{Strom} * {Spannung}"))
    data = definitions.build([ds], base_dir=str(tmp_path / "neu"))
    data["files"][0]["path"] = "/gibt/es/nicht/m.csv"            # absoluter Pfad veraltet, relativer passt
    target = str(tmp_path / "neu" / "c.def")
    open(target, "w", encoding="utf-8").write(json.dumps(data))
    assert len(definitions.apply(target, [], load_file).new_datasets) == 1
    data["files"][0].pop("relpath")                             # Datei ganz weg: geöffnete Datei mit den Signalen
    data["files"][0]["path"] = "/gibt/es/nicht/weg.csv"
    open(target, "w", encoding="utf-8").write(json.dumps(data))
    other = load_file(make(tmp_path, "anders.csv", factor=3))
    _data, targets = definitions.plan(target, [other])
    assert targets[0].stored_path is None and targets[0].use == [other] and not targets[0].use_stored
    result = definitions.apply(target, [other], load_file)
    assert result.assignments[0][0] is other and not result.new_datasets


def test_plan_prefers_open_run_of_same_structure_and_allows_both(tmp_path):
    a = load_file(make(tmp_path, "lauf1.csv"))
    formula.add_or_replace(a, formula.compute(a, "P", "", "{Strom} * {Spannung}"))
    target = definitions.write(str(tmp_path / "p.def"), definitions.build([a], base_dir=str(tmp_path)))
    b = load_file(make(tmp_path, "lauf2.csv", factor=2))          # nach Neustart nur Lauf 2 geöffnet
    _data, targets = definitions.plan(target, [b])
    assert targets[0].stored_path and targets[0].stored_open is None
    assert targets[0].use == [b] and not targets[0].use_stored    # Vorschlag: die geöffnete Datei
    targets[0].use_stored = True                                   # Nutzer wählt zusätzlich die gespeicherte
    result = definitions.apply(target, [b], load_file, targets)
    assert len(result.new_datasets) == 1 and {d.name for d, _c, _p in result.assignments} == {"lauf1.csv", "lauf2.csv"}
    _data, targets = definitions.plan(target, [a, b])              # gespeicherte offen: die gilt
    assert targets[0].stored_open is a and targets[0].use_stored and targets[0].use == []
    assert definitions.same_path(a.path, a.path.upper()) == (os.path.normcase("A") == "a")


def test_databases_stored_in_definition(tmp_path):
    from messgraph.databases import DatabaseConfig
    a = load_file(make(tmp_path))
    a.extra["config"] = DatabaseConfig.from_dict({"dbc": [[str(tmp_path / "x.dbc"), 0]]})
    formula.add_or_replace(a, formula.compute(a, "P", "", "{Strom} * {Spannung}"))
    data = definitions.build([a])
    assert "databases" in data["files"][0] and data["files"][0]["databases"]["dbc"]
