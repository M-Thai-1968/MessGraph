# MessGraph als portable Version für Windows bauen (einmalig auf einem Rechner MIT Internet ausführen).
#
# Ergebnis:
#   runtime\python\                         Python 3.12.0 samt allen Paketen (dearpygui, numpy, pandas, ...)
#   dist\MessGraph_portable_windows.zip     kompletter Ordner zum Weitergeben
# Auf dem Zielrechner wird kein Python benötigt: ZIP entpacken, start_windows.bat doppelklicken.
#
# Quelle für Python 3.12.0 (64 Bit):
#   github     (Vorgabe) python-build-standalone 20231002, Prüfsumme SHA-256 wird kontrolliert
#   python.org            "Windows embeddable package" von python.org (Ausweichquelle)
# Aufruf mit anderer Quelle:  powershell -ExecutionPolicy Bypass -File build_portable_windows.ps1 -Source python.org
# Nur noch packen (runtime\python ist schon fertig):  build_portable_windows.bat -PackOnly
param([ValidateSet("github", "python.org")][string]$Source = "github", [switch]$PackOnly)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"         # Invoke-WebRequest ist mit Fortschrittsbalken sehr langsam
$PyVersion = "3.12.0"
$PbsDate = "20231002"
$PbsFile = "cpython-$PyVersion+$PbsDate-x86_64-pc-windows-msvc-shared-install_only.tar.gz"
$PbsUrl = "https://github.com/indygreg/python-build-standalone/releases/download/$PbsDate/$PbsFile"
$PbsSha256 = "facfaa1fbc8653f95057f3c4a0f8aa833dab0e0b316e24ee8686bc761d4b4f8d"
$EmbedUrl = "https://www.python.org/ftp/python/$PyVersion/python-$PyVersion-embed-amd64.zip"

$Root = Split-Path -Parent $PSScriptRoot
$Runtime = Join-Path $Root "runtime"
$PyDir = Join-Path $Runtime "python"
$Python = Join-Path $PyDir "python.exe"

function Invoke-Checked([string]$exe, [string[]]$arguments) {
    & $exe @arguments
    if ($LASTEXITCODE -ne 0) { throw "Fehlgeschlagen ($LASTEXITCODE): $exe $($arguments -join ' ')" }
}

function Install-FromGithub {
    $archive = Join-Path $env:TEMP $PbsFile
    Invoke-WebRequest $PbsUrl -OutFile $archive
    $hash = (Get-FileHash $archive -Algorithm SHA256).Hash.ToLower()
    if ($hash -ne $PbsSha256) { throw "Prüfsumme stimmt nicht ($hash). Download beschädigt oder verändert." }
    New-Item -ItemType Directory -Force $Runtime | Out-Null
    Invoke-Checked "tar" @("-xzf", $archive, "-C", $Runtime)       # erzeugt runtime\python (tar.exe ab Windows 10)
}

function Install-FromPythonOrg {
    New-Item -ItemType Directory -Force $PyDir | Out-Null
    $zip = Join-Path $env:TEMP "python-$PyVersion-embed-amd64.zip"
    Invoke-WebRequest $EmbedUrl -OutFile $zip
    Expand-Archive $zip -DestinationPath $PyDir -Force
    # Das eingebettete Python liest nur die ._pth-Datei: Standardbibliothek, Paketordner und Projektordner (..\..)
    $pth = Get-ChildItem $PyDir -Filter "python*._pth" | Select-Object -First 1
    Set-Content $pth.FullName -Encoding ASCII -Value @("$($pth.BaseName).zip", ".", "Lib\site-packages", "..\..", "import site")
    $getPip = Join-Path $env:TEMP "get-pip.py"
    Invoke-WebRequest "https://bootstrap.pypa.io/get-pip.py" -OutFile $getPip
    Invoke-Checked $Python @($getPip, "--no-warn-script-location")
}

function Invoke-Retry([scriptblock]$action, [string]$what, [int]$tries = 6) {
    # Virenscanner und Windows-Suche öffnen frisch kopierte Dateien kurz: dann einige Sekunden später erneut
    for ($i = 1; $i -le $tries; $i++) {
        try { & $action; return }
        catch {
            if ($i -eq $tries) { throw }
            Write-Host "  $what - Datei gerade in Benutzung, neuer Versuch in $(2 * $i) s ($i/$tries) ..."
            Start-Sleep -Seconds (2 * $i)
        }
    }
}

if ($PackOnly) {
    if (-not (Test-Path $Python)) { throw "runtime\python fehlt. Bitte zuerst ohne -PackOnly bauen." }
    Write-Host "Nur packen: vorhandenes runtime\python wird verwendet."
    Invoke-Checked $Python @("-c", "import sys; print('Python', sys.version.split()[0])")
} else {
    Write-Host "1/5 Python $PyVersion herunterladen (Quelle: $Source) ..."
    if (Test-Path $Runtime) { Remove-Item -Recurse -Force $Runtime }
    if ($Source -eq "github") {
        try { Install-FromGithub }
        catch {
            Write-Host "GitHub nicht erreichbar oder Prüfung fehlgeschlagen: $($_.Exception.Message)"
            Write-Host "Ausweichquelle python.org ..."
            if (Test-Path $Runtime) { Remove-Item -Recurse -Force $Runtime }
            Install-FromPythonOrg
        }
    } else {
        Install-FromPythonOrg
    }

    Write-Host "2/5 Version prüfen ..."
    Invoke-Checked $Python @("-c", "import sys; v = sys.version_info[:3]; print('Python', '.'.join(map(str, v))); assert v == (3, 12, 0), 'Python 3.12.0 erwartet'")
    Invoke-Checked $Python @("-m", "pip", "--version")

    Write-Host "3/5 Pakete installieren (dearpygui, numpy, pandas, pyarrow, asammdf, canmatrix, pyyaml, pillow) ..."
    Invoke-Checked $Python @("-m", "pip", "install", "--no-warn-script-location", "--disable-pip-version-check",
                             "-r", (Join-Path $Root "requirements.txt"))

    Write-Host "4/5 MessGraph prüfen ..."
    Push-Location $Root
    try {
        Invoke-Checked $Python @("-c", "import dearpygui, numpy, pandas, pyarrow, asammdf, messgraph; print('Pakete ok, MessGraph', messgraph.__version__)")
    } finally { Pop-Location }
}

Write-Host "5/5 ZIP erstellen ..."
$Dist = Join-Path $Root "dist"
$Stage = Join-Path $Dist "MessGraph"
$Target = Join-Path $Dist "MessGraph_portable_windows.zip"
if (Test-Path $Stage) { Invoke-Retry { Remove-Item -Recurse -Force $Stage } "Alten Zwischenordner löschen" }
New-Item -ItemType Directory -Force $Stage | Out-Null
foreach ($item in @("main.py", "messgraph", "demo_data", "runtime", "start_windows.bat", "requirements.txt", "README.md")) {
    Copy-Item -Recurse (Join-Path $Root $item) $Stage
}
Get-ChildItem $Stage -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
if (Test-Path $Target) { Remove-Item -Force $Target }
# .NET ZipFile statt Compress-Archive: liest Dateien mit Freigabe für andere Prozesse, schneller bei vielen Dateien
Add-Type -AssemblyName System.IO.Compression.FileSystem
Invoke-Retry {
    if (Test-Path $Target) { Remove-Item -Force $Target }
    [System.IO.Compression.ZipFile]::CreateFromDirectory($Stage, $Target,
        [System.IO.Compression.CompressionLevel]::Optimal, $true)
} "ZIP erstellen"
try { Invoke-Retry { Remove-Item -Recurse -Force $Stage } "Zwischenordner löschen" 3 }
catch { Write-Host "Hinweis: Zwischenordner $Stage bitte später von Hand löschen." }
Write-Host ""
Write-Host "Fertig: $Target  (Python $PyVersion)"
Write-Host "Auf dem Zielrechner entpacken und start_windows.bat starten (kein Python nötig)."
