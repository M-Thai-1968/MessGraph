#!/bin/sh
# MessGraph als portable Version für Linux bauen (einmalig auf einem Rechner MIT Internet ausführen).
#
# Ergebnis:
#   runtime/python/                          Python 3.12.0 (python-build-standalone) samt allen Paketen
#   dist/MessGraph_portable_linux.tar.gz     kompletter Ordner zum Weitergeben
# Auf dem Zielrechner (gleiche Prozessorart, x86_64 oder aarch64) wird kein Python benötigt:
# entpacken, sh start_linux.sh starten. Nötig bleibt nur OpenGL (auf Desktop-Systemen vorhanden).
set -eu

PY_VERSION=3.12.0
PBS_DATE=20231002          # Release von python-build-standalone mit Python 3.12.0
ARCH=$(uname -m)           # x86_64 oder aarch64
case "$ARCH" in            # offizielle SHA-256-Prüfsummen des Releases
    x86_64)  SHA256=e51a5293f214053ddb4645b2c9f84542e2ef86870b8655704367bd4b29d39fe9 ;;
    aarch64) SHA256=bccfe67cf5465a3dfb0336f053966e2613a9bc85a6588c2fcf1366ef930c4f88 ;;
    *) echo "Prozessorart $ARCH wird nicht unterstützt (nur x86_64 und aarch64)."; exit 1 ;;
esac

ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUNTIME="$ROOT/runtime"
PYTHON="$RUNTIME/python/bin/python3"
FILE="cpython-${PY_VERSION}+${PBS_DATE}-${ARCH}-unknown-linux-gnu-install_only.tar.gz"
URL="https://github.com/indygreg/python-build-standalone/releases/download/${PBS_DATE}/${FILE}"
ARCHIVE="${TMPDIR:-/tmp}/messgraph-${FILE}"

echo "1/5 Python $PY_VERSION ($ARCH) herunterladen ..."
if command -v curl >/dev/null 2>&1; then
    curl -L --fail -o "$ARCHIVE" "$URL"
else
    wget -O "$ARCHIVE" "$URL"
fi
if command -v sha256sum >/dev/null 2>&1; then
    echo "$SHA256  $ARCHIVE" | sha256sum -c - || { echo "Prüfsumme stimmt nicht: Download beschädigt oder verändert."; exit 1; }
else
    echo "$SHA256  $ARCHIVE" | shasum -a 256 -c - || { echo "Prüfsumme stimmt nicht: Download beschädigt oder verändert."; exit 1; }
fi
rm -rf "$RUNTIME"
mkdir -p "$RUNTIME"
tar -xzf "$ARCHIVE" -C "$RUNTIME"          # erzeugt runtime/python

echo "2/5 Version prüfen ..."
"$PYTHON" -c "import sys; v = sys.version_info[:3]; print('Python', '.'.join(map(str, v))); assert v == (3, 12, 0), 'Python 3.12.0 erwartet'"

echo "3/5 Pakete installieren (dearpygui, numpy, pandas, pyarrow, asammdf, canmatrix, pyyaml, pillow) ..."
"$PYTHON" -m pip install --disable-pip-version-check -r "$ROOT/requirements.txt"

echo "4/5 MessGraph prüfen ..."
cd "$ROOT"
"$PYTHON" -c "import dearpygui, numpy, pandas, pyarrow, asammdf, messgraph; print('Pakete ok, MessGraph', messgraph.__version__)"

echo "5/5 Archiv erstellen ..."
mkdir -p "$ROOT/dist"
NAME=$(basename "$ROOT")
TARGET="$ROOT/dist/MessGraph_portable_linux_${ARCH}.tar.gz"
tar -czf "$TARGET" -C "$(dirname "$ROOT")" \
    --exclude="$NAME/.venv" --exclude="$NAME/dist" --exclude="$NAME/tests" --exclude="__pycache__" \
    --exclude="$NAME/.pytest_cache" "$NAME"
echo
echo "Fertig: $TARGET  (Python $PY_VERSION)"
echo "Auf dem Zielrechner entpacken und 'sh start_linux.sh' starten (kein Python nötig)."
