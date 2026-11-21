"""Demo-Daten für die Fourier-Analyse (Signal berechnen > Art: Fourier-Analyse) in demo_data/ erzeugen.

    python tools/make_demo_fourier.py

1 demo_fourier_netz_oberschwingungen.csv   50 Hz Netz: Spannung mit wenig, Strom (Gleichrichterlast) mit vielen
                                           ungeraden Harmonischen -> Harmonische 0..15, THD
2 demo_fourier_rechteck_saegezahn.csv      20 Hz Rechteck, Sägezahn, Dreieck -> typische Harmonischen-Reihen
3 demo_fourier_frequenzrampe.csv           Hochlauf 40 -> 60 Hz: periodisch, Periodendauer ändert sich je Periode
4 demo_fourier_amplitude_wechselnd.csv     50 Hz, Laststufen von Periode zu Periode, 3. Oberschwingung ab 0,5 s
5 demo_fourier_nicht_periodisch.csv        Rauschen, Sprünge, Drift -> Prüfung meldet "nicht periodisch"
6 demo_fourier_ungleichmaessig.csv         Vibration 120 Hz mit Zeitstempel-Jitter und Lücken (wie MF4/CAN) ->
                                           wird vor der Analyse gleichmäßig abgetastet
7 demo_fourier.def                         Definition: Spektren und Harmonische zu den Dateien 1 bis 3
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent.parent / "demo_data"
rng = np.random.default_rng(2026)


def write(name: str, columns: dict, decimals: int = 4) -> None:
    keys = list(columns)
    data = np.column_stack([columns[k] for k in keys])
    lines = [",".join(keys)]
    fmt = ",".join(["{:.6f}"] + [f"{{:.{decimals}f}}"] * (len(keys) - 1))
    lines += [fmt.format(*row) for row in data]
    (OUT / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{name}: {data.shape[0]} Zeilen, {len(keys) - 1} Signale")


def netz() -> None:
    fs, f0 = 10000.0, 50.0
    t = np.arange(0, 0.5, 1 / fs)
    w = 2 * np.pi * f0 * t
    u = 325.0 * np.sin(w) + 6.5 * np.sin(3 * w + 0.3) + 9.8 * np.sin(5 * w + 1.1) + 3.2 * np.sin(7 * w) \
        + rng.normal(0, 0.8, t.size)
    amps = {1: 10.0, 3: 7.8, 5: 5.4, 7: 3.1, 9: 1.4, 11: 0.9, 13: 0.6, 15: 0.3}   # Gleichrichter-Eingangsstrom
    i = sum(a * np.sin(k * w - 0.2 * k) for k, a in amps.items()) + rng.normal(0, 0.05, t.size)
    write("demo_fourier_netz_oberschwingungen.csv", {"Zeit [s]": t, "U_L1 [V]": u, "I_L1 [A]": i})


def formen() -> None:
    fs, f0 = 5000.0, 20.0
    t = np.arange(0, 1.0, 1 / fs)
    phase = (t * f0) % 1.0
    square = np.where(phase < 0.5, 5.0, -5.0)
    saw = 10.0 * (phase - 0.5)
    tri = 10.0 * (2 * np.abs(2 * (phase - 0.5)) - 1) / 2
    write("demo_fourier_rechteck_saegezahn.csv", {"Zeit [s]": t, "Rechteck [V]": square, "Saegezahn [V]": saw,
                                                  "Dreieck [V]": tri})


def rampe() -> None:
    fs = 5000.0
    t = np.arange(0, 2.0, 1 / fs)
    freq = 40.0 + 10.0 * t                                  # 40 Hz -> 60 Hz
    phase = 2 * np.pi * np.cumsum(freq) / fs
    current = 80.0 * np.sin(phase) + 12.0 * np.sin(5 * phase) + 6.0 * np.sin(7 * phase) + rng.normal(0, 0.4, t.size)
    write("demo_fourier_frequenzrampe.csv", {"Zeit [s]": t, "Phasenstrom [A]": current, "Drehfrequenz [Hz]": freq})


def amplitude() -> None:
    fs, f0 = 10000.0, 50.0
    t = np.arange(0, 1.0, 1 / fs)
    period = np.floor(t * f0).astype(int)
    levels = np.repeat(rng.choice([4.0, 6.0, 8.0, 10.0, 12.0], size=period.max() // 5 + 1), 5)[period]
    w = 2 * np.pi * f0 * t
    third = np.where(t >= 0.5, 0.25, 0.0)                    # ab 0,5 s nichtlineare Last: 3. Oberschwingung
    i = levels * (np.sin(w) + third * np.sin(3 * w)) + rng.normal(0, 0.05, t.size)
    write("demo_fourier_amplitude_wechselnd.csv", {"Zeit [s]": t, "Laststrom [A]": i, "Laststufe [A]": levels})


def nicht_periodisch() -> None:
    fs = 2000.0
    t = np.arange(0, 2.0, 1 / fs)
    noise = rng.normal(0, 1.0, t.size)
    steps = np.cumsum(np.where(rng.random(t.size) < 0.002, rng.normal(0, 3, t.size), 0.0))
    drift = 20.0 + 1.5 * t + 0.4 * np.cumsum(rng.normal(0, 0.05, t.size))
    write("demo_fourier_nicht_periodisch.csv", {"Zeit [s]": t, "Rauschen [mV]": noise, "Spruenge [bar]": steps,
                                                "Temperaturdrift [°C]": drift})


def ungleichmaessig() -> None:
    fs, f0 = 4000.0, 120.0
    t = np.arange(0, 1.0, 1 / fs) + rng.normal(0, 0.08 / fs, int(fs))   # Zeitstempel-Jitter
    keep = np.ones(t.size, bool)
    for start in rng.integers(100, t.size - 100, size=6):                # Lücken (verlorene Botschaften)
        keep[start:start + rng.integers(3, 12)] = False
    t = np.sort(t[keep])
    w = 2 * np.pi * f0 * t
    acc = 2.0 * np.sin(w) + 0.6 * np.sin(2 * w + 0.5) + 0.3 * np.sin(4 * w) + rng.normal(0, 0.05, t.size)
    write("demo_fourier_ungleichmaessig.csv", {"Zeit [s]": t, "Vibration [g]": acc})


def definition() -> None:
    def entry(path, computed):
        return {"path": path, "relpath": path, "computed": [
            {"name": n, "unit": "", "formula": f, "comment": c} for n, f, c in computed]}
    data = {"format": "MessGraph-Definition", "version": 1, "title": "Beispiel: Fourier-Analyse",
            "comment": "Spektren und Harmonische zu den Fourier-Demodaten.", "author": "MessGraph",
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "files": [
                entry("demo_fourier_netz_oberschwingungen.csv", [
                    ("Harmonische I_L1", "FFT({I_L1}; h=1..15; f0=auto; win=auto)",
                     "Gleichrichterstrom: ungerade Harmonische 3, 5, 7 ..."),
                    ("Harmonische U_L1", "FFT({U_L1}; h=1..15; f0=50; win=auto)", "Netzspannung, f0 fest 50 Hz"),
                    ("Spektrum I_L1", "FFT({I_L1}; f=0..1000; win=auto)", "Frequenzbereich 0..1000 Hz")]),
                entry("demo_fourier_rechteck_saegezahn.csv", [
                    ("Harmonische Rechteck", "FFT({Rechteck}; h=1..15; f0=auto; win=auto)", "nur ungerade, 1/n"),
                    ("Harmonische Saegezahn", "FFT({Saegezahn}; h=1..15; f0=auto; win=auto)", "alle, 1/n")]),
                entry("demo_fourier_frequenzrampe.csv", [
                    ("Harmonische Phasenstrom", "FFT({Phasenstrom}; h=1..10; f0=auto; win=auto)",
                     "Periodendauer ändert sich - Tabelle je Periode im Tooltip")]),
            ]}
    (OUT / "demo_fourier.def").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("demo_fourier.def")


if __name__ == "__main__":
    netz()
    formen()
    rampe()
    amplitude()
    nicht_periodisch()
    ungleichmaessig()
    definition()
