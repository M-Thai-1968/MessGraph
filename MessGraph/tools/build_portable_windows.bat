@echo off
rem Portable Version bauen: ruft das PowerShell-Skript daneben auf (Internet nötig).
rem Optionen werden durchgereicht, z. B.  build_portable_windows.bat -PackOnly   (nur noch packen)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_portable_windows.ps1" %*
if errorlevel 1 (
    echo.
    echo Bau fehlgeschlagen. Meldung oben beachten.
)
pause
