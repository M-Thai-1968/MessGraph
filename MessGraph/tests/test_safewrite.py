"""Ergebnisdateien sicher schreiben: Sperren, Analyse belegter Dateien, Wiederholung, Ersatzweg."""
import json
import os
import threading

import pytest

from messgraph import safewrite


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(safewrite, "_sleep", lambda s: None)


def test_replace_retried_while_busy(tmp_path, monkeypatch):
    target = tmp_path / "Time_counter.json"
    target.write_text("{}")
    real, calls, log = os.replace, [], []

    def busy_replace(a, b):
        calls.append(1)
        if len(calls) < 4:
            raise PermissionError(13, "Access is denied")
        real(a, b)
    monkeypatch.setattr(safewrite.os, "replace", busy_replace)
    safewrite.update_json(target, {"count_A_DUT1": {"actual": 5}}, log=log.append)
    assert json.loads(target.read_text()) == {"count_A_DUT1": {"actual": 5}}
    assert len(calls) == 4
    assert any("belegt" in line for line in log) and any("3 Wiederholung" in line for line in log)
    assert not (tmp_path / "Time_counter.json.tmp").exists() and not (tmp_path / "Time_counter.json.lock").exists()


def test_permanently_blocked_replace_writes_in_place(tmp_path, monkeypatch):
    target = tmp_path / "Time_counter.json"
    target.write_text(json.dumps({"old": 1, "long": "x" * 500}))
    monkeypatch.setattr(safewrite.os, "replace", lambda a, b: (_ for _ in ()).throw(PermissionError(13, "denied")))
    log = []
    safewrite.update_json(target, {"new": 2}, log=log.append)
    assert json.loads(target.read_text()) == {"old": 1, "long": "x" * 500, "new": 2}   # gekürzt, gültiges JSON
    assert any("direkt in die Datei" in line for line in log)
    assert not (tmp_path / "Time_counter.json.tmp").exists()


def test_stale_lock_of_dead_process_removed(tmp_path):
    target = tmp_path / "Time_counter.json"
    lock = tmp_path / "Time_counter.json.lock"
    import socket
    lock.write_text(json.dumps({"pid": 999999999, "host": socket.gethostname(), "time": 0}))
    log = []
    safewrite.update_json(target, {"a": 1}, log=log.append)
    assert json.loads(target.read_text()) == {"a": 1} and not lock.exists()
    assert any("Verwaiste Sperrdatei" in line for line in log)


def test_live_other_instance_lock_waits_then_reports(tmp_path, monkeypatch):
    target = tmp_path / "Time_counter.json"
    lock = tmp_path / "Time_counter.json.lock"
    import socket, time
    lock.write_text(json.dumps({"pid": os.getppid(), "host": socket.gethostname(), "time": time.time()}))
    monkeypatch.setattr(safewrite, "LOCK_WAIT", 0.0)
    log = []
    with pytest.raises(safewrite.FileBusyError) as info:
        safewrite.update_json(target, {"a": 1}, log=log.append)
    assert "andere MessGraph-Instanz" in str(info.value) and str(os.getppid()) in str(info.value)
    assert lock.exists() and not target.exists()                       # fremde Sperre bleibt, nichts geschrieben


def test_parallel_updates_lose_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(safewrite, "_sleep", lambda s: __import__("time").sleep(0.001))
    target = tmp_path / "Time_counter.json"
    threads = [threading.Thread(target=safewrite.update_json, args=(target, {f"k{i}": i})) for i in range(20)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert json.loads(target.read_text()) == {f"k{i}": i for i in range(20)}


@pytest.mark.skipif(not os.path.isdir("/proc"), reason="nur mit /proc")
def test_holders_finds_process_with_open_file(tmp_path):
    target = tmp_path / "Time_counter.json"
    target.write_text("{}")
    with open(target) as fh:
        found = safewrite.holders(target)
        assert any(pid == os.getpid() for pid, _ in found)
        assert "diese MessGraph-Instanz" in safewrite.describe(found)
    assert safewrite.holders(target) == []
    assert "Virenscanner" in safewrite.describe([])


def test_engine_writes_result_file_via_safewrite(tmp_path, monkeypatch):
    from messgraph.auto import AutoEngine, AutoSettings
    calls = []
    real = safewrite.update_json
    monkeypatch.setattr(safewrite, "update_json", lambda *a, **k: calls.append(a) or real(*a, **k))
    engine = AutoEngine(AutoSettings(source=str(tmp_path / "src"), target=str(tmp_path / "out")))
    path = engine.write_json({"count_X_G": {"actual": 1}})
    assert calls and json.loads(open(path).read()) == {"count_X_G": {"actual": 1}}
