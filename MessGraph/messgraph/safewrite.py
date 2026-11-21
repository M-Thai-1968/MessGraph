"""Ergebnisdateien sicher schreiben (Time_counter.json, statistics.json, PNG, Report).

Unter Windows schlägt os.replace(tmp, ziel) mit "[WinError 5] Access is denied" fehl, solange irgendein Prozess
eine der beiden Dateien ohne Lösch-Freigabe offen hat. Typisch und meist nur für Millisekunden: der Virenscanner
(Windows Defender prüft jede neu geschriebene Datei), die Windows-Suche, OneDrive-Synchronisation (Desktop und
Dokumente liegen oft in OneDrive), ein Editor oder Bildbetrachter mit der Datei - oder eine zweite laufende
MessGraph-Instanz mit derselben Ergebnisdatei.

Ablauf beim Schreiben:
1. Sperre im Programm (threading.Lock je Datei): Threads dieser Instanz schreiben nie gleichzeitig.
2. Sperrdatei <ziel>.lock mit PID: zwei MessGraph-Instanzen warten aufeinander statt zu kollidieren. Gehört die
   Sperrdatei einem beendeten Prozess (Absturz), wird sie entfernt.
3. Lesen-Ändern-Schreiben (update_json) geschieht innerhalb beider Sperren, es geht kein Eintrag verloren.
4. Temporäre Datei schreiben und schließen, dann ersetzen. Ist eine Datei belegt: Zugriff analysieren (welcher
   Prozess hält die Datei, unter Windows über den Restart Manager), protokollieren und mit wachsender Pause erneut
   versuchen (insgesamt etwa 10 s).
5. Bleibt das Ersetzen gesperrt, wird der Inhalt direkt in die Zieldatei geschrieben (überschreiben statt
   ersetzen; das braucht keine Lösch-Freigabe und gelingt, wenn der andere Prozess nur liest). Erst wenn auch das
   scheitert, kommt ein Fehler mit den belegenden Prozessen.

Fremde Prozesse werden nicht beendet: Virenscanner, Suche oder OneDrive geben die Datei von selbst frei, und eine
andere MessGraph-Instanz könnte gerade eine Auswertung schreiben. Beendet wird nur der eigene Zugriff (Sperren und
Dateien werden immer freigegeben) und eine verwaiste Sperrdatei.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Callable

from .i18n import t

RETRY_DELAYS = (0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 2.0, 2.0)   # zusammen etwa 10 s
LOCK_WAIT = 30.0          # so lange auf eine andere MessGraph-Instanz warten
LOCK_STALE = 120.0        # Sperrdatei ohne lebenden Prozess oder älter als das: verwaist

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()
_sleep = time.sleep       # für Tests austauschbar


class FileBusyError(OSError):
    """Datei bleibt belegt; holders: [(pid, name)] der belegenden Prozesse (soweit ermittelbar)."""

    def __init__(self, message: str, holders: list[tuple[int, str]] | None = None):
        super().__init__(message)
        self.holders = holders or []


def _thread_lock(path: Path) -> threading.Lock:
    key = os.path.normcase(os.path.abspath(str(path)))
    with _locks_guard:
        return _locks.setdefault(key, threading.Lock())


# ---------------------------------------------------------------- belegende Prozesse ermitteln
def _holders_windows(paths: list[str]) -> list[tuple[int, str]]:
    import ctypes
    from ctypes import wintypes

    class RM_UNIQUE_PROCESS(ctypes.Structure):
        _fields_ = [("dwProcessId", wintypes.DWORD), ("ProcessStartTime", wintypes.FILETIME)]

    class RM_PROCESS_INFO(ctypes.Structure):
        _fields_ = [("Process", RM_UNIQUE_PROCESS), ("strAppName", wintypes.WCHAR * 256),
                    ("strServiceShortName", wintypes.WCHAR * 64), ("ApplicationType", ctypes.c_int),
                    ("AppStatus", wintypes.ULONG), ("TSSessionId", wintypes.DWORD), ("bRestartable", wintypes.BOOL)]

    rm = ctypes.WinDLL("rstrtmgr")
    session = wintypes.DWORD()
    key = ctypes.create_unicode_buffer(33)
    if rm.RmStartSession(ctypes.byref(session), 0, key) != 0:
        return []
    try:
        files = (wintypes.LPCWSTR * len(paths))(*paths)
        if rm.RmRegisterResources(session, len(paths), files, 0, None, 0, None) != 0:
            return []
        needed, count, reasons = wintypes.UINT(0), wintypes.UINT(0), wintypes.DWORD(0)
        res = rm.RmGetList(session, ctypes.byref(needed), ctypes.byref(count), None, ctypes.byref(reasons))
        if res not in (0, 234) or needed.value == 0:                     # 234 = ERROR_MORE_DATA
            return []
        info = (RM_PROCESS_INFO * needed.value)()
        count = wintypes.UINT(needed.value)
        if rm.RmGetList(session, ctypes.byref(needed), ctypes.byref(count), info, ctypes.byref(reasons)) != 0:
            return []
        result = []
        for i in range(count.value):
            pid = int(info[i].Process.dwProcessId)
            name = info[i].strAppName or info[i].strServiceShortName or "?"
            exe = _exe_windows(pid)
            result.append((pid, f"{name} ({exe})" if exe and exe.lower() not in name.lower() else name))
        return result
    finally:
        rm.RmEndSession(session)


def _exe_windows(pid: int) -> str:
    try:
        import ctypes
        from ctypes import wintypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)    # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            if ctypes.windll.kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return buf.value
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        pass
    return ""


def _holders_proc(paths: list[str]) -> list[tuple[int, str]]:
    wanted = {os.path.realpath(p) for p in paths}
    result = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            fds = os.listdir(f"/proc/{entry}/fd")
        except OSError:
            continue
        for fd in fds:
            try:
                if os.readlink(f"/proc/{entry}/fd/{fd}") in wanted:
                    try:
                        name = Path(f"/proc/{entry}/comm").read_text().strip()
                    except OSError:
                        name = "?"
                    result.append((int(entry), name))
                    break
            except OSError:
                continue
    return result


def holders(*paths) -> list[tuple[int, str]]:
    """Prozesse, die eine der Dateien geöffnet haben: [(PID, Name)]; leer, wenn keiner oder nicht ermittelbar."""
    existing = [os.path.abspath(str(p)) for p in paths if p and os.path.exists(str(p))]
    if not existing:
        return []
    try:
        if sys.platform == "win32":
            return _holders_windows(existing)
        if os.path.isdir("/proc"):
            return _holders_proc(existing)
    except Exception:
        pass
    return []


def describe(found: list[tuple[int, str]]) -> str:
    if not found:
        return t("kein Prozess ermittelbar (vermutlich Virenscanner, Windows-Suche oder OneDrive, nur kurzzeitig)")
    own = os.getpid()
    return ", ".join(f"{name} PID {pid}" + (t(" = diese MessGraph-Instanz") if pid == own else "") for pid, name in found)


# ---------------------------------------------------------------- Sperrdatei zwischen Instanzen
def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if sys.platform == "win32":
        try:
            import ctypes
            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if not handle:
                return False
            code = ctypes.c_ulong()
            ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            ctypes.windll.kernel32.CloseHandle(handle)
            return code.value == 259                                     # STILL_ACTIVE
        except Exception:
            return True
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except OSError:
        return True


def _read_lock(lock: Path) -> dict:
    try:
        return json.loads(lock.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


class _InstanceLock:
    def __init__(self, target: Path, log: Callable[[str], None] | None):
        self.lock = target.with_name(target.name + ".lock")
        self.log = log
        self.owned = False

    def __enter__(self):
        deadline = time.monotonic() + LOCK_WAIT
        reported = False
        while True:
            try:
                fd = os.open(str(self.lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump({"pid": os.getpid(), "host": socket.gethostname(), "time": time.time()}, fh)
                self.owned = True
                return self
            except FileExistsError:
                info = _read_lock(self.lock)
                pid = int(info.get("pid") or 0)
                same_host = info.get("host", socket.gethostname()) == socket.gethostname()
                age = time.time() - float(info.get("time") or 0)
                if pid == os.getpid() or (same_host and not _pid_alive(pid)) or age > LOCK_STALE:
                    if self.log:
                        self.log(t("Verwaiste Sperrdatei {name} (PID {pid}) entfernt.", name=self.lock.name, pid=pid))
                    try:
                        self.lock.unlink()
                    except OSError:
                        pass
                    continue
                if not reported and self.log:
                    self.log(t("{name} wird gerade von einer anderen MessGraph-Instanz geschrieben (PID {pid}, {host}) "
                               "- warte.", name=self.lock.with_suffix("").name, pid=pid, host=info.get("host", "?")))
                    reported = True
                if time.monotonic() > deadline:
                    raise FileBusyError(t("{path} ist seit {seconds} s durch eine andere MessGraph-Instanz gesperrt "
                                          "(PID {pid}). Bitte nur eine Instanz mit dieser Ergebnisdatei laufen lassen.",
                                          path=self.lock.with_suffix(""), seconds=f"{LOCK_WAIT:.0f}", pid=pid),
                                        [(pid, "MessGraph")])
                _sleep(0.1)
            except OSError:
                return self                                              # Ordner ohne Schreibrecht für .lock: ohne Sperre weiter

    def __exit__(self, *exc):
        if self.owned:
            try:
                self.lock.unlink()
            except OSError:
                pass
        return False


# ---------------------------------------------------------------- Schreiben
def _replace(tmp: Path, path: Path, data: bytes, log: Callable[[str], None] | None) -> None:
    analysed = False
    for attempt, delay in enumerate((0.0,) + RETRY_DELAYS):
        if delay:
            _sleep(delay)
        try:
            os.replace(tmp, path)
            if attempt and log:
                log(t("{name}: nach {count} Wiederholung(en) ersetzt.", name=path.name, count=attempt))
            return
        except PermissionError as exc:
            if not analysed:
                analysed = True
                if log:
                    log(t("{name} belegt ({error}): {holders} - neuer Versuch.", name=path.name,
                          error=exc.strerror or exc, holders=describe(holders(path, tmp))))
    found = holders(path, tmp)
    try:                                                                 # überschreiben braucht keine Lösch-Freigabe
        with open(path, "r+b" if path.exists() else "wb") as fh:
            fh.seek(0)
            fh.write(data)
            fh.truncate()
        if log:
            log(t("{name}: Ersetzen blieb gesperrt ({holders}); Inhalt direkt in die Datei geschrieben.",
                  name=path.name, holders=describe(found)))
    except OSError as exc:
        raise FileBusyError(t("{path} ist belegt und kann nicht geschrieben werden: {holders} ({error})", path=path,
                              holders=describe(found), error=exc), found) from exc
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


def write_bytes(path, data: bytes, log: Callable[[str], None] | None = None, tmp_suffix: str = ".tmp") -> str:
    """Atomar schreiben (temporäre Datei, dann ersetzen) mit Sperren, Analyse und Wiederholung."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _thread_lock(path), _InstanceLock(path, log):
        _write_unlocked(path, data, log, tmp_suffix)
    return str(path)


def _write_unlocked(path: Path, data: bytes, log, tmp_suffix: str) -> None:
    tmp = path.with_name(path.name + tmp_suffix)
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    _replace(tmp, path, data, log)


def write_text(path, text: str, log: Callable[[str], None] | None = None) -> str:
    return write_bytes(path, text.encode("utf-8"), log)


def update_json(path, changes: dict, log: Callable[[str], None] | None = None, indent: int = 2) -> str:
    """Lesen, um changes ergänzen, schreiben - alles unter beiden Sperren (keine verlorenen Einträge)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _thread_lock(path), _InstanceLock(path, log):
        data = {}
        if path.is_file():
            for delay in (0.0,) + RETRY_DELAYS[:5]:
                if delay:
                    _sleep(delay)
                try:
                    with open(path, encoding="utf-8") as fh:                # Datei sofort wieder schließen
                        old = json.load(fh)
                    data = old if isinstance(old, dict) else {}
                    break
                except PermissionError:
                    continue
                except (OSError, ValueError):
                    data = {}
                    break
        data.update(changes)
        _write_unlocked(path, json.dumps(data, indent=indent, ensure_ascii=False).encode("utf-8"), log, ".tmp")
    return str(path)
