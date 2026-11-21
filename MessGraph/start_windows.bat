@echo off
cd /d "%~dp0"
rem 1. Portable Version: mitgeliefertes Python im Ordner runtime (kein installiertes Python nötig)
if exist runtime\python\python.exe (
    runtime\python\python.exe main.py %*
    if errorlevel 1 pause
    exit /b
)
rem 2. Sonst: eigene Umgebung .venv mit installiertem Python (wird beim ersten Start angelegt)
if not exist .venv\Scripts\python.exe (
    echo Richte Python-Umgebung ein...
    py -3 -m venv .venv || python -m venv .venv || goto fehler
    .venv\Scripts\python.exe -m pip install -r requirements.txt || goto fehler
)
.venv\Scripts\python.exe main.py %*
if errorlevel 1 pause
exit /b

:fehler
echo.
echo Einrichtung fehlgeschlagen: kein Python 3.10 oder neuer gefunden.
echo Fuer Rechner ohne Python die portable Version verwenden:
echo   auf einem Rechner mit Internet tools\build_portable_windows.bat ausfuehren
echo   und dist\MessGraph_portable_windows.zip weitergeben.
if exist .venv rmdir /s /q .venv
pause
