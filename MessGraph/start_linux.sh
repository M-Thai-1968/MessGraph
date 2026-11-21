#!/bin/sh
cd "$(dirname "$0")" || exit 1
# 1. Portable Version: mitgeliefertes Python im Ordner runtime (kein installiertes Python nötig)
if [ -x runtime/python/bin/python3 ]; then
    exec runtime/python/bin/python3 main.py "$@"
fi
# 2. Sonst: eigene Umgebung .venv mit installiertem Python (wird beim ersten Start angelegt)
if [ ! -x .venv/bin/python ]; then
    echo "Richte Python-Umgebung ein..."
    if ! python3 -m venv .venv || ! .venv/bin/python -m pip install -r requirements.txt; then
        echo "Einrichtung fehlgeschlagen. Ist Python 3.10+ mit venv installiert (python3-venv)?"
        echo "Für Rechner ohne Python die portable Version verwenden:"
        echo "  auf einem Rechner mit Internet 'sh tools/build_portable_linux.sh' ausführen"
        echo "  und dist/MessGraph_portable_linux_<arch>.tar.gz weitergeben (Python 3.12.0)."
        rm -rf .venv
        exit 1
    fi
fi
exec .venv/bin/python main.py "$@"
