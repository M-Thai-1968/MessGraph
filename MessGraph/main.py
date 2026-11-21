#!/usr/bin/env python3
"""MessGraph starten: python main.py [Datei ...]"""
import os
import sys


def _portable() -> bool:
    """Läuft das mitgelieferte Python aus dem Ordner runtime (portable Version)?"""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(sys.executable).startswith(os.path.join(here, "runtime") + os.sep)


def main() -> int:
    try:
        from messgraph.gui import App
    except ImportError as exc:
        if _portable():
            script = "tools\\build_portable_windows.bat" if os.name == "nt" else "sh tools/build_portable_linux.sh"
            print(f"Fehlendes Paket: {exc.name}\nDie portable Version ist unvollständig (Python "
                  f"{sys.version.split()[0]}). Bitte auf einem Rechner mit Internet {script} erneut ausführen.")
        else:
            print(f"Fehlendes Paket: {exc.name}\nBitte installieren: pip install -r requirements.txt")
        return 1
    App(sys.argv[1:]).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
