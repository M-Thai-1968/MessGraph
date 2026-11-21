"""Startdateien: portables Python im Ordner runtime hat Vorrang, sonst .venv."""
import shutil
import sys
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_windows_start_prefers_runtime():
    text = (ROOT / "start_windows.bat").read_text(encoding="utf-8")
    assert text.index(r"runtime\python\python.exe") < text.index(r".venv\Scripts\python.exe")
    assert b"\r\n" in (ROOT / "start_windows.bat").read_bytes()


def test_windows_pth_contains_project_root():
    text = (ROOT / "tools" / "build_portable_windows.ps1").read_text(encoding="utf-8")
    assert r'"..\.."' in text and '"import site"' in text and "requirements.txt" in text


def test_linux_scripts_syntax_and_order():
    text = (ROOT / "start_linux.sh").read_text(encoding="utf-8")
    assert text.index("runtime/python/bin/python3") < text.index(".venv/bin/python")
    for name in ("start_linux.sh", "tools/build_portable_linux.sh"):
        assert subprocess.run(["sh", "-n", str(ROOT / name)]).returncode == 0


@pytest.mark.skipif(shutil.which("sh") is None, reason="sh fehlt")
def test_linux_start_uses_runtime(tmp_path):
    for name in ("start_linux.sh",):
        shutil.copy(ROOT / name, tmp_path / name)
    fake = tmp_path / "runtime" / "python" / "bin" / "python3"
    fake.parent.mkdir(parents=True)
    fake.write_text('#!/bin/sh\necho "portable $*"\n')
    fake.chmod(0o755)
    out = subprocess.run(["sh", str(tmp_path / "start_linux.sh"), "a.csv"], capture_output=True, text=True)
    assert out.stdout.strip() == "portable main.py a.csv"


def test_build_scripts_pin_python_3_12_0_with_checksums():
    ps1 = (ROOT / "tools" / "build_portable_windows.ps1").read_bytes()
    assert ps1.startswith(b"\xef\xbb\xbf") and b"\r\n" in ps1          # BOM für Windows PowerShell 5, CRLF
    ps1 = ps1.decode("utf-8-sig")
    sh = (ROOT / "tools" / "build_portable_linux.sh").read_text(encoding="utf-8")
    assert '$PyVersion = "3.12.0"' in ps1 and "PY_VERSION=3.12.0" in sh
    assert "facfaa1fbc8653f95057f3c4a0f8aa833dab0e0b316e24ee8686bc761d4b4f8d" in ps1     # Windows x64
    assert "e51a5293f214053ddb4645b2c9f84542e2ef86870b8655704367bd4b29d39fe9" in sh      # Linux x86_64
    assert "bccfe67cf5465a3dfb0336f053966e2613a9bc85a6588c2fcf1366ef930c4f88" in sh      # Linux aarch64
    assert "(3, 12, 0)" in ps1 and "(3, 12, 0)" in sh                                     # Versionsprüfung
    assert "python-3.12.0-embed-amd64.zip" in ps1.replace("$PyVersion", "3.12.0")         # Ausweichquelle


def test_main_reports_incomplete_portable_runtime(tmp_path):
    runtime = tmp_path / "runtime" / "python" / "bin"
    runtime.mkdir(parents=True)
    shutil.copy(ROOT / "main.py", tmp_path / "main.py")
    (tmp_path / "messgraph").mkdir()
    (tmp_path / "messgraph" / "__init__.py").write_text("")
    (tmp_path / "messgraph" / "gui.py").write_text("import dearpygui_fehlt_absichtlich\n")
    python = runtime / "python3"
    python.symlink_to(sys.executable)
    out = subprocess.run([str(python), "-I", str(tmp_path / "main.py")], capture_output=True, text=True,
                         cwd=tmp_path)
    assert out.returncode == 1 and "portable Version ist unvollständig" in out.stdout


def test_windows_packing_is_robust_against_locked_files():
    ps1 = (ROOT / "tools" / "build_portable_windows.ps1").read_text(encoding="utf-8-sig")
    assert "Compress-Archive -Path" not in ps1                             # brach bei kurz gesperrten Dateien ab
    assert "ZipFile]::CreateFromDirectory" in ps1 and "function Invoke-Retry" in ps1
    assert "[switch]$PackOnly" in ps1 and "if ($PackOnly)" in ps1
    assert ps1.count("{") == ps1.count("}")                                # Blöcke geschlossen
    bat = (ROOT / "tools" / "build_portable_windows.bat").read_text(encoding="utf-8")
    assert 'build_portable_windows.ps1" %*' in bat
