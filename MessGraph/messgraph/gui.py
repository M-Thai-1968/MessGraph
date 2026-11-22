"""Oberfläche mit Dear PyGui.

Alle Callbacks laufen über die manuelle Callback-Verarbeitung im Render-Thread.
Die Hintergrund-Threads lesen nur Dateien und liefern ihr Ergebnis über eine Queue.
"""
from __future__ import annotations

import json
import math
import os
import re
import queue
import tempfile
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import dearpygui.dearpygui as dpg
import numpy as np

from . import __version__, browser, themes
from .data_model import Channel, Dataset, LoadError
from . import i18n
from .i18n import t
from .databases import CAN_CHOICES, DatabaseConfig, apply_databases, install_databases
from . import session as sessions
from . import downsample
from . import progress
from . import compare
from . import formula
from . import fourier
from . import definitions
from . import plotexport
from . import report
from . import project
from . import arrange
from . import report_html
from . import help_content
from .help_pdf import build_help_pdf
from .fonts import find_cjk_font, find_thai_font
from .layout import GraphSlot, PlotLayout, format_layout, format_row, parse_layout, parse_matrix, parse_row
from .loaders import BUS_FRAME_PREFIXES, SUPPORTED, _mf4_entries, is_ascii, load_file
from . import csv_reader
from . import limitconfig
from . import limiter
from . import auto
from . import autoreport
from . import dirrules
from .measure import (NAN, REG_METHODS, TIME_FACTORS, decimate, drift_unit, fmt, format_target, measure, parse_duration, predict,
                      regression, value_at, view_points)
from .timeparse import format_duration, format_wallclock

SETTINGS_FILE = Path.home() / ".messgraph.json"
LOG_FILE = Path.home() / "messgraph_fehler.log"
LAST_SESSION = Path.home() / f".messgraph_letzte_ansicht.mgraph"
HELP_IMAGES = Path.home() / ".messgraph_hilfe_bilder"
DEMO_DIR = Path(__file__).resolve().parent.parent / "demo_data"
AUTO_BASE = Path(__file__).resolve().parent.parent / "Test"     # Basisordner der Auto-Auswertungen (Programmordner\Test)
SHOT_SCENES = ["uebersicht", "dateiliste", "allefiles", "ascii", "browser", "matrix", "zeilen", "vorschlag", "kontextmenue", "crosslines", "datumsachse",
               "konfigurator", "datenbasen", "ansicht", "berechnen", "vergleich", "drucken", "hilfe"]
MARK_RGB = (232, 89, 12)
SHOT_SETTLE_FRAMES = 12   # Bilder warten, bis Layout und Graphen stehen
MIN_PLOT_HEIGHT = 220
TABLE_HEIGHT = 190
LEFT_WIDTH = 350
MAX_LISTED = 400
LOD_POINTS = 10_000
LOD_INTERVAL = 0.08
PAYLOAD = "messgraph_signal"
CLICK_TOLERANCE = 5      # Pixel: mehr Bewegung mit rechter Taste ist Bereichszoom, kein Klick
MENU_LIST_MAX = 200
MENU_WIDTH = 440
SPLIT = 7                # Breite/Höhe der Trenner zwischen den Fensterbereichen
MIN_LEFT, MIN_PLOTS, MIN_TABLE = 200, 300, 80
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/liberation-sans/LiberationSans-Regular.ttf",
]


def log_exception(context: str, exc: BaseException) -> None:
    """Vollständige Fehlerursache für die Fehlersuche festhalten (Datei wird klein gehalten)."""
    try:
        old = LOG_FILE.read_text(encoding="utf-8")[-200_000:] if LOG_FILE.exists() else ""
        entry = (f"===== {time.strftime('%Y-%m-%d %H:%M:%S')}  MessGraph {__version__}  {context}\n"
                 + "".join(traceback.format_exception(exc)) + "\n")
        LOG_FILE.write_text(old + entry, encoding="utf-8")
    except OSError:
        pass


def _scalar(value) -> float:
    """Drag-Lines liefern je nach Version eine Zahl oder eine Liste."""
    return float(value[0] if isinstance(value, (list, tuple)) else value)


@dataclass(eq=False)
class SlotUI:
    slot: GraphSlot
    plot: int
    x_axis: int
    y_axis: int
    series: dict = field(default_factory=dict)      # Channel -> Item
    colors: dict = field(default_factory=dict)      # Channel -> Farbindex
    v_lines: list = field(default_factory=list)
    v_read: list = field(default_factory=lambda: [None, None])
    m3_line: int | None = None  # Marker 3 (unabhängig von M1/M2, Wertetabelle als Tooltip)
    fourier: bool = False       # Graph mit Ergebnissen der Fourier-Analyse: ohne Marker, ohne X-Kopplung
    m3_read: float | None = None
    limits: tuple | None = None
    time_axis: bool = False
    y2_axis: int | None = None
    limit_series: dict = field(default_factory=dict)  # Channel -> Linien für Y min / Y max
    reg_series: dict = field(default_factory=dict)    # Channel -> gestrichelte Regressionsgerade
    curve: dict = field(default_factory=dict)         # Channel -> (x, y) der Kurve, wie gezeichnet (mit Versatz)
    reg_points: dict = field(default_factory=dict)    # Channel -> Striche der Regressionsgeraden (x, y)
    reg_view: tuple | None = None                     # X-Ausschnitt, für den die Striche berechnet sind
    view: tuple | None = None   # zuletzt gesehener X-Sichtbereich (für das Nachführen der Marker)
    legend: int | None = None   # Legende des Graphen (Lage über Rechtsklick wählbar)
    labels: dict = field(default_factory=dict)   # Channel -> Beschriftung in der Legende
    settle: int = 5             # erste Frames nach dem Aufbau: Einpassen der Achsen ist kein Zoom
    comment_items: list = field(default_factory=list)   # Anmerkungen der Kommentarfelder im Plot


# Werte der Signaltabelle im Report: (Schlüssel, Spaltenkopf, Beschriftung im Dialog)
REPORT_STATS = [("min", "Minimum (min)", "Minimum"), ("max", "Maximum (max)", "Maximum"),
                ("avg", "Mittelwert (avg)", "Mittelwert (avg)"), ("drift", "Drift (Regression)", "Drift (Regression)")]
REPORT_FORMATS = ["both", "pdf", "html"]
REPORT_FORMAT_NAMES = {"both": "PDF und dynamisch (HTML)", "pdf": "PDF (fest)", "html": "Dynamisch (HTML)"}
TARGET_NAMES = {"printer": "Drucker", "pdf": "PDF-Datei", "svg": "SVG-Vektorgrafik"}
ORIENT_NAMES = {"auto": "Automatisch", "portrait": "Hochformat", "landscape": "Querformat"}
LEGEND_ORDER = ["nw", "n", "ne", "sw", "s", "se"]
LEGEND_LOCATIONS = {"nw": "mvPlot_Location_NorthWest", "n": "mvPlot_Location_North", "ne": "mvPlot_Location_NorthEast",
                    "sw": "mvPlot_Location_SouthWest", "s": "mvPlot_Location_South", "se": "mvPlot_Location_SouthEast"}
LEGEND_NAMES = {"nw": "oben links", "n": "oben Mitte", "ne": "oben rechts",
                "sw": "unten links", "s": "unten Mitte", "se": "unten rechts"}
LEGEND_DEFAULT = "nw"
FONT_MIN, FONT_MAX, FONT_DEFAULT = 10, 32, 17   # Schriftgröße der Graphen und der Wertanzeige (px)
CANCELLED = "\x00abgebrochen"  # Ergebnis eines abgebrochenen Ladejobs
LIMITER = object()               # Ladeziel: Führungssignal des Limiters (nur laden, nicht anzeigen)
FILE_SWITCH = object()           # Ladeziel: Kanal für den Wechsel aller Graphen auf eine andere Datei

def layout_text(proposal) -> str:
    return format_layout(proposal.matrix, proposal.spans)


class App:
    def __init__(self, files=()):
        self.settings = self._load_settings()
        self.mode = self.settings.get("theme", themes.DARK)
        if self.mode not in themes.PALETTE:
            self.mode = themes.DARK
        self.datasets: list[Dataset] = []
        self.zoom_ui, self.zoom_slot = None, None   # Graph im Detailfenster (Doppelklick)
        self.ctx_from_zoom, self.exp_zoom = False, False
        self.file_switch = None           # (Datei, noch ladende Kanäle, fehlgeschlagene) beim Dateiwechsel; Datei None = alle
        self.all_files_snapshot = None    # Graphen über mehrere Dateien vor dem Wechsel auf eine Datei (für "Alle Dateien")
        self.layout = PlotLayout()
        self.slot_ui: list[SlotUI] = []
        self.pool = ThreadPoolExecutor(max_workers=2)
        self.results: queue.Queue = queue.Queue()
        self.pending = 0
        self.report_comment = ""   # allgemeine Bemerkung des Reports (gehört zur Ansicht)
        self.project_path: str | None = None      # geöffnetes bzw. zuletzt gespeichertes Projekt
        self.project_name = ""
        self.project_comment = ""
        self.project_created: str | None = None
        self.cmp_files: set[str] | None = None     # Vergleich: gewählte Dateien (Pfade), None = Vorschlag
        self.cmp_signals: set[str] = set()
        self.cmp_stats = [s for s in self.settings.get("compare_stats", compare.STATS) if s in compare.STATS] or ["avg"]
        self.cmp_result: compare.CompareResult | None = None
        self.cmp_pct: dict[str, str] = {str(k): str(v) for k, v in (self.settings.get("compare_tolerance") or {}).items()}
        self.cmp_table = None
        self.jobs: list[progress.Job] = []
        self.deferred: list = []   # [verbleibende Bilder, Funktion]   # laufende und fertige Ladejobs der aktuellen Fortschrittsanzeige
        self.cross_on = False
        self.cross_sync = True
        self.m3_on = False             # Marker 3 mit Wertetabelle
        self.m3_range = self.settings.get("m3_range", "markers")   # Min/Max/Average/Drift: M1..M2 oder gesamt
        if self.m3_range not in ("markers", "all"):
            self.m3_range = "markers"
        self.link_x = True
        self.date_axis = bool(self.settings.get("date_axis", False))
        self.reg_on = bool(self.settings.get("regression_lines", False))   # Regressionsgeraden einblenden
        self.reg_method = self.settings.get("regression_method", "ols")      # Art der Drift-Regression
        if self.reg_method not in REG_METHODS:
            self.reg_method = "ols"
        self.limit_cfg = None             # Grenzwert-Konfiguration (YAML); None = nur manuelle Werte
        self.limiter = None               # Limiter (Daten je Datei auf Grenzen von Führungssignalen kürzen); None = aus
        self.limiter_state = {}           # Dateipfad -> (Anteil im Limit, fehlende Signale, ladende Signale)
        self.auto_settings = auto.AutoSettings.from_dict(self.settings.get("auto"))
        self.auto_engine = None           # Auto-Auswertung: Engine der gewählten Auswertung
        self.auto_engines = {}            # je Auswertung (id des Eintrags) eine Engine
        self.auto_jobs, self.auto_sel = [], 0
        self.report_future = None         # Report über mehrere Auswertungen (läuft im Hintergrund)
        self.report_pool = None
        self.report_progress = (0, 0, "")
        self.report_cancel = False
        self.auto_running = False
        self.auto_future = None
        self.auto_pool = None
        self.auto_next = 0.0
        self.auto_last = None             # letztes Zyklusergebnis
        self.auto_stats = {}              # Signale des Quellordners (Analyse): Name -> Einheit, Dateien, min, max
        self.auto_mode_stats = {}         # Analyse je Mode: Mode -> {Name: (Einheit, Dateien, min, max)}
        self.auto_analysis = None         # laufende Analyse des Quellordners
        self.lim_extra = {}               # manuell für den Limiter gewählte Dateien: Name -> Signalnamen
        self.le_edit_mode = None          # im Grenzwert-Konfigurator bearbeiteter Mode
        self.cfg_mode = None              # gewählter Mode der Konfiguration
        self.graph_font_size = max(FONT_MIN, min(FONT_MAX, int(self.settings.get("graph_font_size", FONT_DEFAULT))))
        downsample.set_config(downsample.DownsampleConfig.from_dict(self.settings.get("downsampling")))
        self.left_width = int(self.settings.get("left_width", LEFT_WIDTH))
        self.table_h = int(self.settings.get("table_height", TABLE_HEIGHT))
        self.split_drag = None   # (welcher Trenner, Mausposition beim Start, Größe beim Start)
        self.plot_note = ""
        language = self.settings.get("language") or self.settings.get("help_language") or i18n.DEFAULT
        self.lang = self.help_lang = language if language in i18n.LANGUAGES else i18n.DEFAULT
        i18n.set_language(self.lang)
        self.spacer_width = None
        self.help_textures = []
        self.shots = None
        self.global_themes = {}
        self.alarm_themes = {}            # schwach roter Plothintergrund (Zielzeit verletzt) je Farbschema
        self.alarm_plots = set()          # Plots, denen das gerade gebunden ist
        self.target_boxes = {}            # (Graph oder "zoom", Signal) -> Eingabefeld der Zielzeit
        self.table_row_pos = []           # je Tabellenzeile (Tabelle, Zeilennummer) zum Hinterlegen
        self.series_themes = {}
        self.splitter_themes = {}
        self.coloured_text: list[tuple[int, str]] = []
        self.table_rows: list[tuple] = []
        self.table_preds: list = []   # je Tabellenzeile das Textfeld der Prognose (nur mit Datumsachse)
        self.checkboxes: dict[Channel, int] = {}
        self.file_headers: list[int] = []
        self.shot_marks: list = []
        self.shot_overlay = None
        self.subplots = None
        self.last_height = None
        self.last_lod = 0.0
        self.initial_files = list(files)
        self.loading: dict[Channel, object] = {}   # MF4-Kanal -> Zielgraph, solange er geladen wird
        self.drop_targets: dict[int, GraphSlot] = {}
        self.right_down = None
        self.ctx_slot: GraphSlot | None = None
        self.ctx_filter = None
        self.ctx_list = None
        self.fb_dir = self._start_dir()
        self.fb_selected: dict[str, None] = {}     # gewählte Dateien (Reihenfolge der Auswahl)
        self.fb_boxes: dict[str, int] = {}
        self.fb_filters = browser.FILTERS
        self.fb_on_open = None        # None: Messdateien laden; sonst Funktion für die gewählten Pfade
        self.fb_mode = "data"
        self.db_dataset: Dataset | None = None
        self.db_config = DatabaseConfig()

    # ---------------------------------------------------------------- Einstellungen
    @staticmethod
    def _load_settings() -> dict:
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save_settings(self) -> None:
        try:
            SETTINGS_FILE.write_text(json.dumps(self.settings, indent=2), encoding="utf-8")
        except OSError:
            pass  # Einstellungen sind Komfort; das Programm läuft auch ohne

    # ---------------------------------------------------------------- Aufbau
    def build(self) -> None:
        dpg.create_context()
        dpg.configure_app(manual_callback_management=True)
        dpg.create_viewport(title=f"MessGraph {__version__}", width=1500, height=950)
        self._load_font()
        self.texture_registry = dpg.add_texture_registry()
        for mode in themes.PALETTE:
            self.global_themes[mode] = themes.create_global_theme(mode)
            for index, col in enumerate(themes.PALETTE[mode]["series"]):
                self.series_themes[mode, index] = themes.create_series_theme(col)
            self.splitter_themes[mode] = themes.create_splitter_theme(mode)
            self.alarm_themes[mode] = themes.create_alarm_plot_theme(mode)
        self._build_windows()

    def _build_windows(self) -> None:
        """Alle Fenster in der eingestellten Sprache aufbauen (auch beim Sprachwechsel)."""
        self.coloured_text = []
        self._build_file_dialog()
        self._build_context_menu()
        self._build_db_window()
        self._build_save_dialog()
        self._build_ds_window()
        self._build_cmp_window()
        self._build_export_window()
        self._build_calc_window()
        self._build_def_window()
        self._build_def_load_window()
        self._build_ascii_window()
        self._build_project_window()
        self._build_transfer_window()
        self._build_rows_window()
        self._build_arrange_window()
        self._build_zoom_window()
        self._build_limit_editor()
        self._build_limiter_window()
        self._build_auto_window()
        self._build_report_window()
        self._build_dir_window()
        self._build_marker_tip()
        self._build_m3_tip()
        # Hilfe in einem eigenen Fenster (Menü Hilfe > Hilfe anzeigen), nicht mehr als Reiter neben Graph
        with dpg.window(tag="help_window", label=t("Hilfe"), show=False, width=1100, height=760, no_collapse=True) \
                as self.help_tab:
            self._build_help_tab()
        with dpg.window(tag="main"):
            self._build_menu_bar()
            with dpg.tab_bar() as self.tab_bar:
                with dpg.tab(label=t("Graph")) as self.graph_tab:
                    self._build_graph_tab()
            with dpg.group(horizontal=True, show=False) as self.progress_row:
                self.progress_bar = dpg.add_progress_bar(default_value=0.0, width=320, overlay="")
                dpg.add_button(label=t("Abbrechen"), callback=self._cancel_jobs)
                self.progress_text = dpg.add_text("")
            self.status = dpg.add_text(t("Bereit. Dateien über \"Dateien öffnen...\" laden. Rechtsklick auf einen "
                                         "Graphen: Signale hinzufügen oder entfernen."))
        dpg.set_primary_window("main", True)
        self._apply_font()
        self._apply_mode()
        self._rebuild_plots()
        self._refresh_channel_list()

    # ---------------------------------------------------------------- Sprache
    def _lang_font(self, language: str):
        """Schrift einer Sprache: Thai und Chinesisch brauchen eigene Schriften (mit lateinischen Zeichen)."""
        if language == "Thai" and self.thai_font:
            return self.thai_font
        if language == "Chinese" and getattr(self, "cjk_font", None):
            return self.cjk_font
        return self.ui_font

    def _lang_font_path(self, language: str) -> str | None:
        if language == "Thai":                          # keine Ersatzschrift: ohne Thai-Zeichen kein PDF
            return self.thai_font_path if self.thai_font else None
        if language == "Chinese":
            return getattr(self, "cjk_font_path", None) if getattr(self, "cjk_font", None) else None
        return self.ui_font_path

    def _apply_font(self) -> None:
        """Thai und Chinesisch brauchen eine eigene Schrift für die ganze Oberfläche; sie enthält auch lateinische
        Zeichen."""
        font = self._lang_font(self.lang)
        if font is not None:
            dpg.bind_font(font)
        for language in i18n.SCRIPT_LANGUAGES:            # Einträge im Sprachmenü in ihrer eigenen Schrift
            item = getattr(self, "lang_items", {}).get(language)
            own = self._lang_font(language)
            if item is not None and own is not None and own is not self.ui_font:
                dpg.bind_item_font(item, own)

    def _on_language_item(self, sender, _value, language: str) -> None:
        self.set_language(language)
        if self.lang != language and dpg.does_item_exist(sender):
            dpg.set_value(sender, False)  # abgelehnt (keine Thai-Schrift)

    def set_language(self, language: str) -> None:
        """Sprache der Oberfläche und der Hilfe umschalten; geladene Daten und Graphen bleiben erhalten."""
        if language not in i18n.LANGUAGES or language == self.lang:
            return
        if language == "Thai" and self.thai_font is None:
            self._message(t("Keine Schrift mit thailändischen und lateinischen Zeichen gefunden (z. B. fonts-tlwg-loma installieren): Thai ist nicht verfügbar."), error=True)
            return
        if language == "Chinese" and getattr(self, "cjk_font", None) is None:
            self._message(t("Keine Schrift mit chinesischen und lateinischen Zeichen gefunden (z. B. Microsoft YaHei, "
                            "fonts-wqy-microhei installieren): Chinesisch ist nicht verfügbar."), error=True)
            return
        self.lang = self.help_lang = language
        i18n.set_language(language)
        self.settings["language"] = language
        self._save_settings()
        self._rebuild_ui()

    # Alle Fenster und Popups mit festem Tag: beim Neuaufbau (Sprachwechsel) zuerst löschen, sonst "Alias already
    # exists". Popups hängen nicht am Fenster, in dem sie angelegt werden, und müssen eigens gelöscht werden.
    REBUILD_TAGS = ("main", "file_browser", "db_window", "save_dialog", "ctx_menu", "ds_window", "cmp_window",
                    "export_window", "calc_window", "def_window", "def_load_window", "ascii_window", "project_window",
                    "transfer_window", "rows_window", "arrange_window", "zoom_window", "limit_editor", "help_window",
                    "view_popup", "limiter_window", "lim_xfer_popup", "auto_window", "auto_run_window", "auto_edges_window",
                    "report_window", "dir_window", "dir_error", "auto_modes_window", "marker_tip", "m3_tip",
                    "fourier_window")

    def _rebuild_ui(self) -> None:
        filter_text = dpg.get_value(self.filter_input)
        matrix_text = dpg.get_value(self.matrix_input)
        on_help = self._help_shown()
        for texture in self.help_textures:
            if dpg.does_item_exist(texture):
                dpg.delete_item(texture)
        for tag in self.REBUILD_TAGS:
            if dpg.does_item_exist(tag):
                dpg.delete_item(tag)
        self.zoom_ui = None            # Detailfenster wird mit dem Plotbereich neu aufgebaut (zoom_slot bleibt)
        if dpg.does_item_exist(self.handlers):
            dpg.delete_item(self.handlers)
        self.slot_ui = []
        self._build_windows()
        dpg.set_value(self.filter_input, filter_text)
        dpg.set_value(self.matrix_input, matrix_text)
        self._apply_options(self.session_options())
        self._layout_changed()
        self._refresh_channel_list()
        if on_help:
            self.show_help()
        self.spacer_width = None
        self._message(t("Sprache: {name}", name=i18n.NAMES[self.lang]))

    def _poll_menu_spacer(self) -> None:
        """Abstände der Menüleiste: Datei -> Graph-Optionen normal, Graph-Optionen -> Hilfe doppelt so groß,
        Sprache am rechten Rand. Gemessen wird der tatsächlich gezeichnete Abstand (unabhängig von Schrift und
        Farbschema); die Platzhalter werden so lange nachgestellt, bis es passt."""
        now = time.monotonic()
        if now - getattr(self, "spacer_checked", 0.0) < 0.25:
            return
        self.spacer_checked = now
        try:
            file_right = dpg.get_item_rect_max(self.file_menu)[0]
            graph_left = dpg.get_item_rect_min(self.graph_menu)[0]
            graph_right = dpg.get_item_rect_max(self.auto_menu)[0]             # letztes Menü vor Hilfe
            help_left = dpg.get_item_rect_min(self.help_menu)[0]
            lang_right, lang_width = dpg.get_item_rect_max(self.lang_menu)[0], dpg.get_item_rect_size(self.lang_menu)[0]
        except Exception:
            return
        if lang_width <= 0:
            return
        normal = graph_left - file_right
        if normal > 0:
            gap_width = float(dpg.get_item_configuration(self.help_gap).get("width") or 0)
            wanted = max(0.0, gap_width + 2 * normal - (help_left - graph_right))
            if abs(wanted - gap_width) >= 1:
                dpg.configure_item(self.help_gap, width=int(round(wanted)))
        current = self.spacer_width or float(dpg.get_item_configuration(self.menu_spacer).get("width") or 0)
        target_right = dpg.get_viewport_client_width() - self.MENU_RIGHT_MARGIN
        width = int(max(8, current + (target_right - lang_right)))
        if width != getattr(self, "spacer_width", None):
            self.spacer_width = width
            dpg.configure_item(self.menu_spacer, width=width)

    FILE_COMBO_RANGE = (140, 320)        # Breite der Dateiauswahl: passt sich dem Platz über den Graphen an

    def _poll_toolbar_width(self) -> None:
        """Dateiauswahl in der Werkzeugleiste so breit wie möglich, ohne dass die erste Zeile über den
        Plotbereich hinausragt (schmale Fenster, breite Dateiliste, größere Schrift)."""
        now = time.monotonic()
        if now - getattr(self, "toolbar_checked", 0.0) < 0.3:
            return
        self.toolbar_checked = now
        try:
            row_right = dpg.get_item_rect_max(self.toolbar_row1)[0]
            area_right = dpg.get_item_rect_max(self.plot_area)[0]
            area_width = dpg.get_item_rect_size(self.plot_area)[0]
        except Exception:
            return
        if area_width <= 0:
            return
        current = int(dpg.get_item_configuration(self.file_combo).get("width") or self.FILE_COMBO_RANGE[1])
        low, high = self.FILE_COMBO_RANGE
        wanted = int(max(low, min(high, current + (area_right - 6) - row_right)))
        if abs(wanted - current) >= 2:
            dpg.configure_item(self.file_combo, width=wanted)

    MENU_RIGHT_MARGIN = 10               # Abstand der Sprachauswahl zum rechten Fensterrand

    def _load_font(self) -> None:
        self.ui_font = self.thai_font = self.cjk_font = None
        self.ui_font_path = self.thai_font_path = self.cjk_font_path = None
        self.size_fonts = {}   # (Schriftdatei, Größe) -> Schrift für Graphen und Wertanzeige
        for path in FONT_CANDIDATES:
            if not os.path.exists(path):
                continue
            with dpg.font_registry():
                with dpg.font(path, 17) as font:
                    dpg.add_font_range_hint(dpg.mvFontRangeHint_Default)
                    dpg.add_font_range(0x0370, 0x03FF)  # griechisch, z. B. Einheit Ohm
            dpg.bind_font(font)
            self.ui_font, self.ui_font_path = font, path
            break
        thai = find_thai_font()
        if thai:  # nur für die Hilfe in Thai; enthält auch lateinische Zeichen
            try:
                with dpg.font_registry():
                    with dpg.font(thai, 19) as font:
                        dpg.add_font_range_hint(dpg.mvFontRangeHint_Default)
                        dpg.add_font_range_hint(dpg.mvFontRangeHint_Thai)
                self.thai_font, self.thai_font_path = font, thai
            except Exception as exc:
                log_exception(f"Thai-Schrift {thai}", exc)
        cjk = find_cjk_font()
        if cjk:  # Chinesisch: nur die verwendeten Zeichen (Oberfläche und Hilfe) in den Schriftatlas
            try:
                with dpg.font_registry():
                    with dpg.font(cjk, 19) as font:
                        self._cjk_ranges()
                self.cjk_font, self.cjk_font_path = font, cjk
            except Exception as exc:
                log_exception(f"Chinesische Schrift {cjk}", exc)
        self._build_size_fonts()

    @staticmethod
    def _cjk_chars() -> list[int]:
        """Alle Zeichen außerhalb von Latin-1, die Oberfläche und Hilfe auf Chinesisch verwenden."""
        from . import help_zh, i18n_zh
        text = "".join(i18n_zh.ZH.values()) + i18n.NAMES["Chinese"] + help_zh.TITLE + help_zh.SUBTITLE
        for title, content in help_zh.CHAPTERS:
            text += title + "".join(str(part) for item in content for part in item[1:])
        return sorted({ord(ch) for ch in text if ord(ch) > 0x2000})

    def _cjk_ranges(self) -> None:
        dpg.add_font_range_hint(dpg.mvFontRangeHint_Default)
        dpg.add_font_range(0x0370, 0x03FF)
        self._add_cjk_chars()

    def _add_cjk_chars(self) -> None:
        """Ältere Dear-PyGui-Versionen laden nur angemeldete Zeichen; ab 2.0 geschieht das automatisch und
        add_font_chars ist veraltet (Warnung, ohne Wirkung)."""
        try:
            major = int(str(dpg.get_dearpygui_version()).split(".")[0])
        except Exception:
            major = 1
        if major < 2 and hasattr(dpg, "add_font_chars"):
            dpg.add_font_chars(self._cjk_chars())

    def _build_size_fonts(self) -> None:
        """Alle Größen des Schriftreglers schon beim Start anlegen.

        Schriften, die erst während des Laufs entstehen, lassen Dear PyGui den Schriftatlas neu bauen; dabei
        gingen die lateinischen Zeichen der Thai-Schrift verloren (leere Einträge im Sprachmenü).
        """
        self.size_fonts = {}
        paths = [p for p in dict.fromkeys((self.ui_font_path, self.thai_font_path, self.cjk_font_path)) if p]
        for path in paths:
            for size in range(FONT_MIN, FONT_MAX + 1):
                if path == self.ui_font_path and size == FONT_DEFAULT and self.ui_font is not None:
                    self.size_fonts[(path, size)] = self.ui_font
                    continue
                try:
                    with dpg.font_registry():
                        with dpg.font(path, size) as font:
                            dpg.add_font_range_hint(dpg.mvFontRangeHint_Default)
                            dpg.add_font_range(0x0370, 0x03FF)
                            if path == self.thai_font_path:
                                dpg.add_font_range_hint(dpg.mvFontRangeHint_Thai)
                            if path == self.cjk_font_path:
                                self._add_cjk_chars()
                except Exception as exc:
                    log_exception(f"Schrift {path} {size}", exc)
                    break
                self.size_fonts[(path, size)] = font

    def _start_dir(self) -> str:
        start = self.settings.get("last_dir") or str(Path.home())
        return start if os.path.isdir(start) else str(Path.home())

    # ---------------------------------------------------------------- Datei-Browser
    def _build_file_dialog(self) -> None:
        """Eigener Browser: Filter nach Dateiendung unabhängig von Groß-/Kleinschreibung,
        Mehrfachauswahl per Häkchen, auch über mehrere Ordner."""
        with dpg.window(tag="file_browser", label=t("Dateien öffnen..."), modal=True, show=False,
                        width=900, height=600, no_collapse=True):
            with dpg.group(horizontal=True):
                dpg.add_button(label=t("Hoch"), callback=self._fb_up)
                dpg.add_button(label=t("Start"), callback=lambda: self._fb_go(str(Path.home())))
                drives = browser.drives()
                if drives:
                    dpg.add_combo(items=drives, width=70, default_value="", callback=lambda s, v: self._fb_go(v))
                self.fb_path = dpg.add_input_text(default_value=self.fb_dir, width=-1, on_enter=True,
                                                  callback=lambda s, v: self._fb_go(v))
            with dpg.group(horizontal=True):
                dpg.add_text(t("Dateityp"))
                self.fb_filter = dpg.add_combo(items=list(browser.FILTERS), default_value=browser.DEFAULT_FILTER,
                                               width=260, callback=lambda: self._fb_refresh())
                self.fb_name = dpg.add_input_text(hint=t("Name enthält"), width=200, callback=lambda: self._fb_refresh())
                dpg.add_button(label=t("Alle im Ordner"), callback=lambda: self._fb_select_all(True))
                dpg.add_button(label=t("Keine"), callback=lambda: self._fb_select_all(False))
            self.fb_error = dpg.add_text("", show=False)
            self.fb_list = dpg.add_child_window(height=-70, border=True)
            self.fb_count = dpg.add_text("")
            with dpg.group(horizontal=True):
                self.fb_open_btn = dpg.add_button(label=t("Öffnen"), width=120, callback=self._fb_open)
                dpg.add_button(label=t("Abbrechen"), width=120, callback=lambda: dpg.configure_item("file_browser", show=False))

    def _show_file_browser(self, mode: str = "data", on_open=None, title: str = "Dateien öffnen...",
                           start_dir: str | None = None) -> None:
        """mode: "data" für Messdateien, sonst "dbc"/"a2l"/"cdd" mit eigenem Filter und Rückruf.
        start_dir: in diesem Ordner beginnen (z. B. Basisordner der Auto-Auswertung)."""
        filters = browser.FILTERS if mode == "data" else browser.DATABASE_FILTERS[mode]
        filters = {t(name): suffixes for name, suffixes in filters.items()}  # Anzeige übersetzt
        dpg.configure_item("file_browser", show=False)
        if mode != self.fb_mode:
            self.fb_selected = {}
            key = "last_dir" if mode == "data" else "last_dir_db"
            start = self.settings.get(key) or self.settings.get("last_dir") or self.fb_dir
            self.fb_dir = start if os.path.isdir(start) else self.fb_dir
        if start_dir and os.path.isdir(start_dir):
            self.fb_dir = start_dir
        self.fb_mode, self.fb_filters, self.fb_on_open = mode, filters, on_open
        dpg.configure_item(self.fb_filter, items=list(filters))
        dpg.configure_item(self.fb_open_btn, label=t("Diesen Ordner wählen") if mode == "folder" else t("Öffnen"))
        dpg.set_value(self.fb_filter, next(iter(filters)))
        dpg.configure_item("file_browser", label=t(title))
        self._fb_go(self.fb_dir)
        width, height = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
        dpg.configure_item("file_browser", show=True, pos=[max(0, (width - 900) // 2), max(0, (height - 600) // 2)])

    def _fb_go(self, path: str) -> None:
        path = os.path.abspath(os.path.expanduser(str(path).strip() or "."))
        if os.path.isfile(path):  # Dateipfad eingetippt: Ordner zeigen, Datei vormerken
            self.fb_selected[path] = None
            path = os.path.dirname(path)
        if not os.path.isdir(path):
            self._fb_show_error(t("Ordner nicht gefunden: {path}", path=path))
            dpg.set_value(self.fb_path, self.fb_dir)
            return
        self.fb_dir = path
        dpg.set_value(self.fb_path, path)
        dpg.set_value(self.fb_name, "")
        self._fb_refresh()

    def _fb_up(self) -> None:
        self._fb_go(browser.parent_dir(self.fb_dir))

    def _fb_show_error(self, text: str) -> None:
        dpg.set_value(self.fb_error, text)
        dpg.configure_item(self.fb_error, show=bool(text), color=themes.color(self.mode, "error"))

    def _fb_refresh(self) -> None:
        dirs, files, error = browser.list_dir(self.fb_dir, dpg.get_value(self.fb_filter), dpg.get_value(self.fb_name),
                                              filters=self.fb_filters)
        self._fb_show_error(error)
        dpg.delete_item(self.fb_list, children_only=True)
        self.fb_boxes = {}
        dim = themes.color(self.mode, "text_dim")
        with dpg.table(parent=self.fb_list, header_row=True, row_background=True, resizable=True,
                       policy=dpg.mvTable_SizingStretchProp, borders_innerV=True):
            dpg.add_table_column(label=t("Name"), init_width_or_weight=5.0)
            dpg.add_table_column(label=t("Größe"), init_width_or_weight=1.0)
            dpg.add_table_column(label=t("Geändert"), init_width_or_weight=1.6)
            shown = 0
            for entry in dirs:
                if shown >= browser.MAX_ENTRIES:
                    break
                with dpg.table_row():
                    dpg.add_selectable(label=f"{t('[Ordner]')}  {entry.name}", span_columns=True,
                                       callback=self._fb_dir_clicked, user_data=entry.path)
                shown += 1
            for entry in files:
                if shown >= browser.MAX_ENTRIES:
                    break
                with dpg.table_row():
                    self.fb_boxes[entry.path] = dpg.add_checkbox(
                        label=entry.name, default_value=entry.path in self.fb_selected,
                        callback=self._fb_file_toggled, user_data=entry.path)
                    dpg.add_text(browser.human_size(entry.size), color=dim)
                    dpg.add_text(browser.human_time(entry.mtime), color=dim)
                shown += 1
        hidden = len(dirs) + len(files) - shown
        if hidden > 0:
            dpg.add_text(t("{count} weitere Einträge nicht gezeigt: Filter \"Name enthält\" nutzen.", count=hidden), parent=self.fb_list)
        if not dirs and not files and not error:
            dpg.add_text(t("Keine passenden Dateien in diesem Ordner."), parent=self.fb_list)
        self._fb_update_count()

    def _fb_dir_clicked(self, _sender, _app_data, path: str) -> None:
        self._fb_go(path)

    def _fb_file_toggled(self, _sender, checked, path: str) -> None:
        if checked:
            self.fb_selected[path] = None
        else:
            self.fb_selected.pop(path, None)
        self._fb_update_count()

    def _fb_select_all(self, checked: bool) -> None:
        for path, box in self.fb_boxes.items():
            dpg.set_value(box, checked)
            self._fb_file_toggled(None, checked, path)

    def _fb_update_count(self) -> None:
        count = len(self.fb_selected)
        here = sum(1 for p in self.fb_selected if os.path.dirname(p) == self.fb_dir)
        text = (t("{count} Datei(en) ausgewählt, davon {other} aus anderen Ordnern.", count=count, other=count - here)
                if count != here else t("{count} Datei(en) ausgewählt.", count=count))
        dpg.set_value(self.fb_count, text)

    def _fb_open(self) -> None:
        paths = [self.fb_dir] if self.fb_mode == "folder" else [p for p in self.fb_selected if os.path.isfile(p)]
        if not paths:
            self._fb_show_error(t("Bitte mindestens eine Datei anhaken."))
            return
        dpg.configure_item("file_browser", show=False)
        self.fb_selected = {}
        self.settings["last_dir" if self.fb_mode == "data" else "last_dir_db"] = self.fb_dir
        self._save_settings()
        if self.fb_on_open is None:
            self.open_files(paths)
        else:
            callback = self.fb_on_open
            self._later(lambda: callback(paths))   # kann selbst ein modales Fenster öffnen

    def _build_context_menu(self) -> None:
        dpg.add_window(tag="ctx_menu", popup=True, show=False, autosize=True)
        with dpg.handler_registry() as self.handlers:
            dpg.add_mouse_click_handler(button=dpg.mvMouseButton_Right, callback=self._on_right_down)
            dpg.add_mouse_release_handler(button=dpg.mvMouseButton_Right, callback=self._on_right_up)
            dpg.add_mouse_double_click_handler(button=dpg.mvMouseButton_Left, callback=self._on_double_click)
            dpg.add_mouse_click_handler(button=dpg.mvMouseButton_Left, callback=self._on_left_down)
            dpg.add_mouse_wheel_handler(callback=self._on_wheel)

    def _build_menu_bar(self) -> None:
        """Datei am linken Rand; Sprache und Hilfe am rechten Rand (Platzhalter dazwischen)."""
        with dpg.menu_bar() as self.menu_bar:
            with dpg.menu(label=t("Datei")) as self.file_menu:
                dpg.add_menu_item(label=t("Projekt öffnen..."), callback=lambda: self._show_file_browser(
                    "project", lambda paths: self.open_project(paths[0]), "Projekt öffnen"))
                dpg.add_menu_item(label=t("Projekt speichern"), callback=self._save_project_now)
                dpg.add_menu_item(label=t("Projekt speichern unter..."), callback=self._open_project_window)
                with dpg.menu(label=t("Zuletzt verwendete Projekte")) as self.recent_menu:
                    pass
                self._refresh_recent_projects()
                dpg.add_menu_item(label=t("Projekt schließen"), callback=self.close_project)
                dpg.add_separator()
                dpg.add_menu_item(label=t("Dateien öffnen..."), callback=lambda: self._show_file_browser())
                dpg.add_separator()
                dpg.add_menu_item(label=t("Ansicht speichern..."), callback=self._ask_save_session)
                dpg.add_menu_item(label=t("Ansicht laden..."), callback=lambda: self._show_file_browser(
                    "session", lambda paths: self.load_session(paths[0]), "Ansicht laden"))
                dpg.add_menu_item(label=t("Einstellungen auf andere Dateien übertragen..."),
                                  callback=lambda: self._open_transfer_window())
                dpg.add_menu_item(label=t("Letzte Ansicht beim Start wiederherstellen"), check=True,
                                  default_value=bool(self.settings.get("restore_last")), callback=self._on_restore_last)
                dpg.add_separator()
                dpg.add_menu_item(label=t("Downsampling..."), callback=self._open_ds_window)
                dpg.add_menu_item(label=t("Dateien vergleichen..."), callback=self._open_cmp_window)
            with dpg.menu(label=t("Graph-Optionen")) as self.graph_menu:
                self._colour(dpg.add_text(t("Grenzwerte")), "heading")
                dpg.add_menu_item(label=t("Grenzwert-Konfiguration laden (*.yaml)..."), callback=lambda: self._show_file_browser(
                    "limitconfig", lambda paths: self.load_limit_config(paths[0]), "Grenzwert-Konfiguration laden"))
                dpg.add_menu_item(label=t("Grenzwert-Konfigurator..."), callback=lambda: self.open_limit_editor())
                dpg.add_menu_item(label=t("Grenzwert-Konfiguration entfernen"), callback=lambda: self.close_limit_config())
                dpg.add_separator()
                self._colour(dpg.add_text(t("Berechnungen")), "heading")
                dpg.add_menu_item(label=t("Berechnungen laden (*.def)..."), callback=self._ask_load_definitions)
                dpg.add_menu_item(label=t("Berechnungen speichern (*.def)..."), callback=self._open_def_window)
                dpg.add_separator()
                self._colour(dpg.add_text(t("Drift-Regression")), "heading")
                self.reg_method_items = {}
                for number, (key, label) in enumerate(REG_METHODS.items(), 1):
                    self.reg_method_items[key] = dpg.add_menu_item(
                        label=f"({number}) {t(label)}", check=True, default_value=key == self.reg_method,
                        callback=lambda _s, _a, method: self.set_regression_method(method), user_data=key)
                self.reg_menu_item = dpg.add_menu_item(label=t("Regressionslinien im Graphen einblenden"), check=True,
                                                       default_value=self.reg_on,
                                                       callback=lambda _s, v: self._set_regression(v))
            with dpg.menu(label=t("Limiter")) as self.limiter_menu:
                dpg.add_menu_item(label=t("Limiter bearbeiten..."), callback=lambda: self.open_limiter_window())
                dpg.add_menu_item(label=t("Limiter-Konfiguration laden (*.yaml)..."), callback=lambda: self._show_file_browser(
                    "limiter", lambda paths: self.load_limiter(paths[0]), "Limiter-Konfiguration laden"))
                dpg.add_menu_item(label=t("Limiter-Konfiguration speichern..."), callback=lambda: self._ask_limiter_save())
                dpg.add_separator()
                self.limiter_item = dpg.add_menu_item(label=t("Limiter aktiv"), check=True,
                                                      default_value=bool(self.limiter and self.limiter.active),
                                                      callback=lambda _s, v: self.set_limiter_active(v))
                dpg.add_menu_item(label=t("Limiter entfernen"), callback=lambda: self.remove_limiter())
            with dpg.menu(label=t("Auto")) as self.auto_menu:
                dpg.add_menu_item(label=t("Auto-Auswertung einrichten..."), callback=lambda: self.open_auto_window())
                self.auto_start_item = dpg.add_menu_item(label=t("Start"), callback=lambda: self.start_auto())
                self.auto_stop_item = dpg.add_menu_item(label=t("Stopp"), callback=lambda: self.stop_auto())
                dpg.add_menu_item(label=t("Einen Zyklus jetzt ausführen"), callback=lambda: self.run_auto_now())
                dpg.add_separator()
                dpg.add_menu_item(label=t("Report erstellen..."), callback=lambda: self.open_report_window())
                dpg.add_separator()
                dpg.add_menu_item(label=t("Log anzeigen"), callback=lambda: self.open_auto_window(show_log=True))
            self.help_gap = dpg.add_spacer(width=8)      # ergibt den doppelten Abstand vor Hilfe (wird nachgemessen)
            with dpg.menu(label=t("Hilfe")) as self.help_menu:
                dpg.add_menu_item(label=t("Hilfe anzeigen"), callback=lambda: self.show_help())
                dpg.add_menu_item(label=t("Hilfe als PDF speichern..."), callback=self._ask_help_pdf)
                dpg.add_menu_item(label=t("Screenshots für die Hilfe erzeugen"), callback=self.start_screenshots)
            self.menu_spacer = dpg.add_spacer(width=self.spacer_width or 900)
            with dpg.menu(label=t("Sprache: {name}", name=i18n.NAMES[self.lang])) as self.lang_menu:
                self.lang_items = {}
                for language in i18n.LANGUAGES:
                    has_font = self._lang_font(language) is not None and (
                        language not in i18n.SCRIPT_LANGUAGES or self._lang_font(language) is not self.ui_font)
                    label = i18n.NAMES[language] if has_font else language
                    self.lang_items[language] = dpg.add_menu_item(label=label, check=True,
                                                                  default_value=language == self.lang,
                                                                  callback=self._on_language_item, user_data=language)

    # ---------------------------------------------------------------- Speichern-Dialog
    def _build_save_dialog(self) -> None:
        with dpg.window(tag="save_dialog", label=t("Speichern"), modal=True, show=False, width=720, height=170,
                        no_collapse=True):
            self.save_prompt = dpg.add_text("")
            self.save_path = dpg.add_input_text(width=-1, on_enter=True, callback=self._save_dialog_ok)
            self.save_note = dpg.add_text("")
            with dpg.group(horizontal=True):
                self.save_ok_btn = dpg.add_button(label=t("Speichern"), width=120, callback=self._save_dialog_ok)
                dpg.add_button(label=t("Abbrechen"), width=120, callback=lambda: dpg.configure_item("save_dialog", show=False))
        self.save_callback = None

    def _ask_save_path(self, title: str, prompt: str, default: str, callback, folder: bool = False) -> None:
        """Pfad erfragen. folder=True: Ziel ist ein (neuer) Ordner - fehlende Elternordner werden mit angelegt."""
        self.save_callback = callback
        self.save_folder = folder
        dpg.configure_item(self.save_ok_btn, label=t("Anlegen") if folder else t("Speichern"))
        dpg.configure_item("save_dialog", label=t(title))
        dpg.set_value(self.save_prompt, t(prompt, **getattr(self, "save_prompt_values", {})))
        self.save_prompt_values = {}
        dpg.set_value(self.save_path, default)
        dpg.set_value(self.save_note, t("Vorhandene Datei wird überschrieben."))
        width, height = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
        dpg.configure_item("save_dialog", show=True, pos=[max(0, (width - 720) // 2), max(0, (height - 170) // 2)])

    def _save_dialog_ok(self, *_args) -> None:
        path = os.path.abspath(os.path.expanduser(dpg.get_value(self.save_path).strip()))
        if getattr(self, "save_folder", False):        # neuer Ordner: samt fehlender Elternordner anlegen
            if not dpg.get_value(self.save_path).strip():
                dpg.set_value(self.save_note, t("Bitte einen Ordner angeben."))
                return
            try:
                os.makedirs(path, exist_ok=True)
            except OSError as exc:
                dpg.set_value(self.save_note, t("Auto: Zielordner nicht angelegt: {error}", error=exc))
                return
            dpg.configure_item("save_dialog", show=False)
            self.save_callback(path)
            return
        if not dpg.get_value(self.save_path).strip() or os.path.isdir(path):
            dpg.set_value(self.save_note, t("Bitte einen Dateinamen angeben."))
            return
        if not os.path.isdir(os.path.dirname(path)):
            dpg.set_value(self.save_note, t("Ordner nicht gefunden: {path}", path=os.path.dirname(path)))
            return
        dpg.configure_item("save_dialog", show=False)
        self.save_callback(path)

    # ---------------------------------------------------------------- Downsampling (MF4, Parquet)
    def _build_ds_window(self) -> None:
        heading, dim = themes.color(self.mode, "heading"), themes.color(self.mode, "text_dim")
        with dpg.window(tag="ds_window", label=t("Downsampling"), modal=True, show=False, width=640, height=470,
                        no_collapse=True):
            self.ds_current = dpg.add_text("", wrap=610)
            self._colour(self.ds_current, "text_dim")
            dpg.add_separator()
            self._colour(dpg.add_text(t("Modus"), color=heading), "heading")
            self.ds_mode = dpg.add_radio_button(items=[t(downsample.MODE_NAMES[m]) for m in downsample.MODES],
                                                callback=self._ds_mode_changed)
            dpg.add_spacer(height=4)
            with dpg.group() as self.ds_auto_group:
                self._colour(dpg.add_text(t("Automatisch"), color=heading), "heading")
                with dpg.group(horizontal=True):
                    dpg.add_text(t("Ab Werten je Signal"))
                    self.ds_threshold = dpg.add_input_int(width=160, step=0)
                with dpg.group(horizontal=True):
                    dpg.add_text(t("Reduzieren auf etwa"))
                    self.ds_target = dpg.add_input_int(width=160, step=0)
                self._colour(dpg.add_text(t("Nur sehr lange Signale werden reduziert, mit Min/Max je Block: Spitzen "
                                            "bleiben erhalten."), wrap=610, color=dim), "text_dim")
            with dpg.group() as self.ds_manual_group:
                self._colour(dpg.add_text(t("Manuell"), color=heading), "heading")
                with dpg.group(horizontal=True):
                    dpg.add_text(t("Methode"))
                    self.ds_method = dpg.add_combo(items=[t(downsample.METHOD_NAMES[m]) for m in downsample.METHODS],
                                                   width=330, callback=self._ds_mode_changed)
                with dpg.group(horizontal=True) as self.ds_factor_row:
                    dpg.add_text(t("Faktor (Blockgröße bzw. n)"))
                    self.ds_factor = dpg.add_input_int(width=120, step=1)
                with dpg.group(horizontal=True) as self.ds_interval_row:
                    dpg.add_text(t("Zeitraster (X-Einheit, meist s)"))
                    self.ds_interval = dpg.add_input_float(width=120, step=0, format="%.6g")
            dpg.add_separator()
            self._colour(dpg.add_text(t("Gilt für MF4 und Parquet. Die Messwerte der Marker stammen dann aus den "
                                        "reduzierten Daten. Die Darstellung langer Signale wird unabhängig davon "
                                        "immer flüssig gehalten."), wrap=610, color=dim), "text_dim")
            self.ds_status = dpg.add_text("", wrap=610)
            with dpg.group(horizontal=True):
                dpg.add_button(label=t("Übernehmen"), callback=lambda: self._ds_apply(False))
                self.ds_reload_btn = dpg.add_button(label=t("Übernehmen und geladene Dateien neu laden"),
                                                    callback=lambda: self._ds_apply(True))
                dpg.add_button(label=t("Abbrechen"), callback=lambda: dpg.configure_item("ds_window", show=False))

    def _open_ds_window(self, *_args) -> None:
        cfg = downsample.config()
        dpg.set_value(self.ds_current, cfg.describe())
        dpg.set_value(self.ds_mode, t(downsample.MODE_NAMES[cfg.mode]))
        dpg.set_value(self.ds_threshold, cfg.auto_threshold)
        dpg.set_value(self.ds_target, cfg.auto_target)
        dpg.set_value(self.ds_method, t(downsample.METHOD_NAMES[cfg.method]))
        dpg.set_value(self.ds_factor, cfg.factor)
        dpg.set_value(self.ds_interval, cfg.interval)
        dpg.set_value(self.ds_status, "")
        affected = [d for d in self.datasets if downsample.applies(d.path)]
        dpg.configure_item(self.ds_reload_btn, show=bool(affected))
        self._ds_mode_changed()
        width, height = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
        dpg.configure_item("ds_window", show=True, pos=[max(0, (width - 640) // 2), max(0, (height - 470) // 2)])

    def _ds_dialog_config(self) -> downsample.DownsampleConfig:
        modes = {t(downsample.MODE_NAMES[m]): m for m in downsample.MODES}
        methods = {t(downsample.METHOD_NAMES[m]): m for m in downsample.METHODS}
        return downsample.DownsampleConfig.from_dict({
            "mode": modes.get(dpg.get_value(self.ds_mode), "auto"),
            "auto_threshold": dpg.get_value(self.ds_threshold), "auto_target": dpg.get_value(self.ds_target),
            "method": methods.get(dpg.get_value(self.ds_method), "minmax"),
            "factor": dpg.get_value(self.ds_factor), "interval": dpg.get_value(self.ds_interval)})

    def _ds_mode_changed(self, *_args) -> None:
        cfg = self._ds_dialog_config()
        dpg.configure_item(self.ds_auto_group, show=cfg.mode == "auto")
        dpg.configure_item(self.ds_manual_group, show=cfg.mode == "manual")
        dpg.configure_item(self.ds_factor_row, show=cfg.method != "grid")
        dpg.configure_item(self.ds_interval_row, show=cfg.method == "grid")

    def _ds_apply(self, reload: bool) -> None:
        cfg = self._ds_dialog_config()
        downsample.set_config(cfg)
        self.settings["downsampling"] = cfg.to_dict()
        self._save_settings()
        dpg.configure_item("ds_window", show=False)
        if reload and any(downsample.applies(d.path) for d in self.datasets):
            self.apply_session(self.session_dict(), None)  # Dateien neu laden, Graphen und Ansicht bleiben
            self._message(t("Downsampling geändert, Dateien werden neu geladen: {text}", text=cfg.describe()))
        else:
            self._message(t("Downsampling gilt für neu geladene Dateien: {text}", text=cfg.describe()))

    # ---------------------------------------------------------------- Dateien vergleichen
    def _build_cmp_window(self) -> None:
        heading, dim = themes.color(self.mode, "heading"), themes.color(self.mode, "text_dim")
        with dpg.window(tag="cmp_window", label=t("Dateien vergleichen"), show=False, width=1100, height=760,
                        no_collapse=True):
            with dpg.group(horizontal=True):
                with dpg.group():
                    self._colour(dpg.add_text(t("Dateien"), color=heading), "heading")
                    with dpg.group(horizontal=True) as self.cmp_file_buttons:
                        dpg.add_button(label=t("Ähnliche wählen"), small=True, callback=self._cmp_suggest)
                        dpg.add_button(label=t("Alle"), small=True, callback=lambda: self._cmp_all_files(True))
                        dpg.add_button(label=t("Keine"), small=True, callback=lambda: self._cmp_all_files(False))
                    self.cmp_file_area = dpg.add_child_window(width=440, height=200, border=True)
                    dpg.add_spacer(height=4)
                    self._colour(dpg.add_text(t("Kennwerte"), color=heading), "heading")
                    self.cmp_stat_boxes = {}
                    with dpg.group(horizontal=True) as self.cmp_stat_row:
                        for stat in compare.STATS:
                            self.cmp_stat_boxes[stat] = dpg.add_checkbox(label=t(compare.STAT_NAMES[stat]),
                                                                         default_value=stat in self.cmp_stats)
                with dpg.group():
                    self._colour(dpg.add_text(t("Signale"), color=heading), "heading")
                    with dpg.group(horizontal=True) as self.cmp_filter_row:
                        self.cmp_filter = dpg.add_input_text(hint=t("Signal suchen"), width=250,
                                                             callback=lambda: self._cmp_refresh_signals())
                        dpg.add_button(label=t("Alle"), small=True, callback=lambda: self._cmp_all_signals(True))
                        dpg.add_button(label=t("Keine"), small=True, callback=lambda: self._cmp_all_signals(False))
                        self.cmp_common = dpg.add_checkbox(label=t("nur gemeinsame"), default_value=False,
                                                           callback=lambda: self._cmp_refresh_signals())
                        self._tooltip(self.cmp_common, t("Nur Signale zeigen, die in allen gewählten Dateien vorkommen."))
                    self.cmp_signal_area = dpg.add_child_window(width=-1, height=240, border=True)
            with dpg.group(horizontal=True) as self.cmp_actions:
                dpg.add_button(label=t("Vergleichen"), callback=self._cmp_start)
                dpg.add_button(label=t("In Zwischenablage kopieren"), callback=self._cmp_copy)
                self.cmp_path = dpg.add_input_text(width=420, hint=t("CSV-Datei"))
                dpg.add_button(label=t("CSV speichern"), callback=self._cmp_save)
                dpg.add_button(label=t("Schließen"), callback=lambda: dpg.configure_item("cmp_window", show=False))
            self.cmp_status = dpg.add_text("", wrap=1060)
            self._colour(self.cmp_status, "text_dim")
            self.cmp_table_area = dpg.add_child_window(width=-1, height=-1, border=True, horizontal_scrollbar=True)
        if self.cmp_result is not None:
            self._cmp_show(self.cmp_result)

    def _open_cmp_window(self, *_args) -> None:
        if len(self.datasets) < 2:
            self._message(t("Für einen Vergleich mindestens zwei Dateien öffnen."))
            return
        known = {os.path.abspath(d.path) for d in self.datasets}
        if self.cmp_files is None or not (self.cmp_files & known):
            self._cmp_suggest()
        else:
            self.cmp_files &= known
            self._cmp_refresh_files()
        if not dpg.get_value(self.cmp_path):
            dpg.set_value(self.cmp_path, str(Path(self.datasets[0].path).with_name("MessGraph_Vergleich.csv")))
        width, height = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
        dpg.configure_item("cmp_window", show=True, pos=[max(0, (width - 1100) // 2), max(0, (height - 760) // 2)])

    def _cmp_selected(self) -> list[Dataset]:
        return [d for d in self.datasets if os.path.abspath(d.path) in (self.cmp_files or set())]

    def _cmp_suggest(self, *_args) -> None:
        groups = compare.similar_groups(self.datasets)
        chosen = groups[0] if groups else self.datasets
        self.cmp_files = {os.path.abspath(d.path) for d in chosen}
        union = compare.signal_union(chosen)
        common = [name for name, count in union if count == len(chosen)]
        if not (self.cmp_signals & {name for name, _ in union}):
            self.cmp_signals = set(common) if len(common) <= 20 else set()   # Vorschlag: wenige gemeinsame Signale
        self._cmp_refresh_files()

    def _cmp_all_files(self, on: bool) -> None:
        self.cmp_files = {os.path.abspath(d.path) for d in self.datasets} if on else set()
        self._cmp_refresh_files()

    def _cmp_refresh_files(self) -> None:
        dpg.delete_item(self.cmp_file_area, children_only=True)
        selected = self._cmp_selected()
        for ds in self.datasets:
            on = ds in selected
            share = compare.group_similarity(ds, selected if on else selected + [ds])
            label = t("{name}  ({share} % gleiche Signalnamen)", name=ds.name, share=round(share * 100)) if len(selected) > 1 or not on \
                else ds.name
            box = dpg.add_checkbox(label=label, default_value=on, parent=self.cmp_file_area,
                                   callback=self._cmp_toggle_file, user_data=ds)
            self._tooltip(box, ds.path)
        self._cmp_refresh_signals()

    def _cmp_toggle_file(self, _sender, value, ds: Dataset) -> None:
        path = os.path.abspath(ds.path)
        self.cmp_files = (self.cmp_files or set()) | {path} if value else (self.cmp_files or set()) - {path}
        self._cmp_refresh_files()

    def _cmp_visible_signals(self) -> list[tuple[str, int]]:
        selected = self._cmp_selected()
        words = dpg.get_value(self.cmp_filter).lower().split()
        union = compare.signal_union(selected)
        if dpg.get_value(self.cmp_common):
            union = [(n, c) for n, c in union if c == len(selected)]
        return [(n, c) for n, c in union if all(w in n.lower() for w in words)]

    def _cmp_refresh_signals(self) -> None:
        dpg.delete_item(self.cmp_signal_area, children_only=True)
        selected = self._cmp_selected()
        visible = self._cmp_visible_signals()
        if not selected:
            dpg.add_text(t("Keine Datei gewählt."), parent=self.cmp_signal_area)
            return
        for name, count in visible[:MAX_LISTED]:
            label = name if count == len(selected) else t("{name}  (in {count} von {total} Dateien)", name=name,
                                                           count=count, total=len(selected))
            dpg.add_checkbox(label=label, default_value=name in self.cmp_signals, parent=self.cmp_signal_area,
                             callback=self._cmp_toggle_signal, user_data=name)
        if len(visible) > MAX_LISTED:
            dpg.add_text(t("{count} weitere Treffer: Filter verfeinern.", count=len(visible) - MAX_LISTED),
                         parent=self.cmp_signal_area)
        chosen = sum(1 for n, _ in compare.signal_union(selected) if n in self.cmp_signals)
        dpg.set_value(self.cmp_status, t("{files} Dateien, {signals} Signale gewählt.", files=len(selected), signals=chosen))

    def _cmp_toggle_signal(self, _sender, value, name: str) -> None:
        if value:
            self.cmp_signals.add(name)
        else:
            self.cmp_signals.discard(name)

    def _cmp_all_signals(self, on: bool) -> None:
        names = {n for n, _ in self._cmp_visible_signals()}   # wirkt auf die gefilterte Liste
        self.cmp_signals = self.cmp_signals | names if on else self.cmp_signals - names
        self._cmp_refresh_signals()

    def _cmp_start(self, *_args) -> None:
        selected = self._cmp_selected()
        stats = [s for s, box in self.cmp_stat_boxes.items() if dpg.get_value(box)]
        signals = [n for n, _ in compare.signal_union(selected) if n in self.cmp_signals]
        if len(selected) < 1 or not signals or not stats:
            dpg.set_value(self.cmp_status, t("Mindestens eine Datei, ein Signal und einen Kennwert wählen."))
            return
        self.cmp_stats = stats
        self.settings["compare_stats"] = stats
        self._save_settings()
        dpg.set_value(self.cmp_status, t("Kennwerte werden berechnet..."))
        self.pool.submit(self._cmp_worker, selected, signals, stats, self._start_job(t("Vergleich")))

    def _cmp_worker(self, datasets, signals, stats, job=None) -> None:
        try:
            with progress.track(job):
                result = compare.compute(datasets, signals, stats)
            self.results.put(("compare", result, None))
        except progress.Cancelled:
            self.results.put(("compare", None, CANCELLED))
        except Exception as exc:
            log_exception(t("Vergleich"), exc)
            self.results.put(("compare", None, f"{type(exc).__name__}: {exc}"))

    def _cmp_done(self, result, error) -> None:
        if error == CANCELLED:
            dpg.set_value(self.cmp_status, t("Abgebrochen."))
            return
        if error:
            dpg.set_value(self.cmp_status, t("Vergleich fehlgeschlagen: {error}", error=error))
            return
        self.cmp_result = result
        if dpg.does_item_exist("cmp_window"):
            self._cmp_show(result)

    def _cmp_show(self, result: compare.CompareResult) -> None:
        """Tabelle: Signal [Einheit], Toleranz in % (Eingabe je Signal), Kennwert, je Datei eine Spalte."""
        dpg.delete_item(self.cmp_table_area, children_only=True)
        dim = themes.color(self.mode, "text_dim")
        self.cmp_rows = []   # (Zeilenindex, Row, Signal-Text, Wert-Texte)
        self.cmp_pct_boxes = {}
        with dpg.table(parent=self.cmp_table_area, header_row=True, resizable=True, borders_innerV=True,
                       borders_outerH=True, row_background=True, policy=dpg.mvTable_SizingFixedFit,
                       scrollX=True, scrollY=True, freeze_rows=1, freeze_columns=1, height=-1) as self.cmp_table:
            dpg.add_table_column(label=t("Signal"))
            dpg.add_table_column(label="%")
            dpg.add_table_column(label=t("Kennwert"))
            for name in result.files:
                dpg.add_table_column(label=name)
            for number, row in enumerate(result.rows):
                with dpg.table_row():
                    first = number == 0 or result.rows[number - 1].signal != row.signal
                    label = f"{row.signal} [{row.unit}]" if row.unit else row.signal
                    name_text = dpg.add_text(label if first else "")
                    if first:
                        box = dpg.add_input_text(width=70, hint="%", default_value=self.cmp_pct.get(row.signal, ""),
                                                 callback=self._cmp_pct_changed, user_data=row.signal)
                        self.cmp_pct_boxes[row.signal] = box
                        self._tooltip(box, t("Toleranz in %: Zeile wird rot, wenn ein Dateiwert um mehr als diesen "
                                             "Wert vom Median aller Dateien abweicht (bei zwei Dateien: vom anderen Wert). Leer = keine Prüfung."))
                    else:
                        dpg.add_text("")
                    dpg.add_text(row.stat)
                    cells = []
                    for value, reduced in zip(row.values, row.reduced):
                        if value is None:
                            cells.append(dpg.add_text("-", color=dim))
                        else:
                            cells.append(dpg.add_text(compare.format_value(value) + ("*" if reduced else "")))
                self.cmp_rows.append((number, row, name_text, cells))
        self._cmp_mark()

    def _cmp_pct_changed(self, _sender, value, signal: str) -> None:
        text = str(value).strip()
        if text:
            self.cmp_pct[signal] = text
        else:
            self.cmp_pct.pop(signal, None)
        self.settings["compare_tolerance"] = dict(self.cmp_pct)
        self._save_settings()
        self._cmp_mark()

    def _cmp_mark(self) -> None:
        """Zeilen mit Abweichung über der Toleranz rot hinterlegen, abweichende Werte rot schreiben."""
        result = self.cmp_result
        if result is None or not getattr(self, "cmp_rows", None) or not dpg.does_item_exist(self.cmp_table):
            return
        text, dim = themes.color(self.mode, "text"), themes.color(self.mode, "text_dim")
        red_bg, red = (220, 40, 40, 90), (255, 85, 85, 255)
        flagged_signals, count = set(), 0
        marks = []
        for number, row, _name, cells in self.cmp_rows:
            flags = compare.deviations(row.values, compare.parse_percent(self.cmp_pct.get(row.signal, "")))
            marks.append(flags)
            if any(flags):
                flagged_signals.add(row.signal)
                count += 1
        for (number, row, name_text, cells), flags in zip(self.cmp_rows, marks):
            if any(flags):
                dpg.highlight_table_row(self.cmp_table, number, red_bg)
            else:
                dpg.unhighlight_table_row(self.cmp_table, number)
            dpg.configure_item(name_text, color=red if row.signal in flagged_signals else text)
            for cell, bad, value in zip(cells, flags, row.values):
                dpg.configure_item(cell, color=red if bad else (dim if value is None else text))
        lines = [t("{signals} Signale x {files} Dateien verglichen.", signals=len({r.signal for r in result.rows}),
                   files=len(result.files))]
        if count:
            lines.append(t("{count} Zeilen mit Abweichung über der Toleranz ({signals}).", count=count,
                           signals=", ".join(sorted(flagged_signals))))
        if result.any_reduced:
            lines.append(t("* aus reduzierten Daten (Downsampling beim Einlesen)"))
        if any(None in r.values for r in result.rows):
            lines.append(t("- = Signal fehlt in der Datei oder hat keine gültigen Werte."))
        lines += result.problems[:5]
        dpg.set_value(self.cmp_status, "  ".join(lines))

    def _decimal(self) -> str:
        return "," if self.lang == "Deutsch" else "."

    def _cmp_copy(self, *_args) -> None:
        if self.cmp_result is None:
            dpg.set_value(self.cmp_status, t("Erst \"Vergleichen\" ausführen."))
            return
        dpg.set_clipboard_text(compare.to_text(self.cmp_result, "\t", self._decimal(), tolerances=self.cmp_pct))
        dpg.set_value(self.cmp_status, t("Tabelle in die Zwischenablage kopiert (zum Einfügen in Excel)."))

    def _cmp_save(self, *_args) -> None:
        if self.cmp_result is None:
            dpg.set_value(self.cmp_status, t("Erst \"Vergleichen\" ausführen."))
            return
        try:
            path = compare.write_csv(os.path.expanduser(dpg.get_value(self.cmp_path).strip()), self.cmp_result,
                                     self._decimal(), tolerances=self.cmp_pct)
        except LoadError as exc:
            dpg.set_value(self.cmp_status, str(exc))
            return
        dpg.set_value(self.cmp_status, t("Gespeichert: {path}", path=path))

    # ---------------------------------------------------------------- Ansicht speichern / laden
    def session_options(self) -> dict:
        return {"link_x": self.link_x, "cross_on": self.cross_on, "cross_sync": self.cross_sync, "marker3_on": self.m3_on,
                "marker3_range": self.m3_range,
                "regression_lines": self.reg_on, "regression_method": self.reg_method,
                "limit_config": self.limit_cfg.path if self.limit_cfg else None, "limit_mode": self.cfg_mode,
                "limiter": dict(limiter.to_dict(self.limiter)["limiter"], path=self.limiter.path) if self.limiter else None,

                "date_axis": self.date_axis, "theme": self.mode, "left_width": self.left_width,
                "table_height": self.table_h, "downsampling": downsample.config().to_dict(),
                "graph_font_size": self.graph_font_size, "report_comment": self.report_comment}

    def session_dict(self, base_dir: str | None = None) -> dict:
        return sessions.build_session(self.datasets, self.layout, self.session_options(), base_dir)

    def _ask_save_session(self, *_args) -> None:
        default = self.settings.get("last_session") or str(Path.home() / f"MessGraph_Ansicht{sessions.SUFFIX}")
        self._ask_save_path("Ansicht speichern", "Datei für die Ansicht (Dateien, Datenbasen, Graphen, Namen, "
                            "Farben, Optionen):", default, self.save_session)

    def save_session(self, path: str) -> None:
        try:
            written = sessions.write_session(path, self.session_dict(os.path.dirname(os.path.abspath(path))))
        except OSError as exc:
            self._message(t("Ansicht nicht gespeichert: {error}", error=exc), error=True)
            return
        self.settings["last_session"] = written
        self._save_settings()
        self._message(t("Ansicht gespeichert: {path}", path=written))

    def load_session(self, path: str) -> None:
        try:
            data = sessions.read_session(path)
        except LoadError as exc:
            self._message(str(exc), error=True)
            return
        self.apply_session(data, os.path.dirname(os.path.abspath(path)))
        self.settings["last_session"] = path
        self._save_settings()

    def apply_session(self, data: dict, base_dir: str | None, done=None) -> None:
        """Ersetzt die aktuelle Ansicht. done: optionaler Rückruf nach dem Laden."""
        self._close_context_menu()
        self.loading.clear()
        for dataset in list(self.datasets):
            dataset.close()
        self.datasets = []
        self.layout = PlotLayout()
        self._layout_changed()
        self._refresh_channel_list()
        if "downsampling" in data.get("options", {}):  # vor dem Laden setzen: gilt für die Dateien der Ansicht
            cfg = downsample.DownsampleConfig.from_dict(data["options"]["downsampling"])
            downsample.set_config(cfg)
            self.settings["downsampling"] = cfg.to_dict()
            self._save_settings()
        self.pending += 1
        self._message(t("Ansicht wird geladen..."))
        self.pool.submit(self._session_worker, data, base_dir, done, self._start_job(t("Ansicht")))

    def _session_worker(self, data, base_dir, done, job=None) -> None:
        try:
            with progress.track(job):
                result = sessions.open_session(data, base_dir)
            self.results.put(("session", data, result, done, None))
        except progress.Cancelled:
            self.results.put(("session", data, None, done, CANCELLED))
        except Exception as exc:
            log_exception("Ansicht laden", exc)
            self.results.put(("session", data, None, done, f"{type(exc).__name__}: {exc}"))

    def _session_done(self, data, result, done, error) -> None:
        self.pending -= 1
        if error == CANCELLED:
            self._message(t("Laden der Ansicht abgebrochen."))
            return
        if error:
            self._message(f"{t('Ansicht nicht geladen: {error}', error=error)}  ({t('Details: {path}', path=LOG_FILE)})", error=True)
            return
        datasets, by_saved, problems = result
        self.datasets = sorted(datasets, key=lambda d: d.name.lower())
        layout, missing = sessions.restore_layout(data, by_saved)
        options = data.get("options", {})
        self.layout = layout
        self._apply_options(options)
        dpg.set_value(self.matrix_input, format_layout(layout.matrix, layout.spans))
        self._layout_changed()
        self._refresh_channel_list()
        if missing:
            problems.append(t("{count} Signale nicht gefunden: {names}", count=len(missing), names=", ".join(missing[:5])))
        self.last_session_problems = problems
        self._message(t("Ansicht geladen.") + (" " + " | ".join(problems) if problems else ""), error=bool(problems))
        if done:
            done()

    def _apply_options(self, options: dict) -> None:
        self.link_x = bool(options.get("link_x", self.link_x))
        self.cross_sync = bool(options.get("cross_sync", self.cross_sync))
        self.date_axis = bool(options.get("date_axis", self.date_axis))
        self.reg_on = bool(options.get("regression_lines", self.reg_on))
        if options.get("regression_method") in REG_METHODS and options["regression_method"] != self.reg_method:
            self.set_regression_method(options["regression_method"], quiet=True)
        config_path = options.get("limit_config")
        if config_path and (self.limit_cfg is None or os.path.abspath(self.limit_cfg.path) != os.path.abspath(config_path)):
            if os.path.isfile(config_path):
                self.load_limit_config(config_path, options.get("limit_mode"), quiet=True)
            else:
                self._message(t("Grenzwert-Konfiguration nicht gefunden: {path}", path=config_path), error=True)
        elif config_path is None and "limit_config" in options and self.limit_cfg is not None:
            self.close_limit_config()
        elif self.limit_cfg is not None and "limit_mode" in options:
            self.set_limit_mode(options.get("limit_mode"), quiet=True)
        if "limiter" in options:
            if options["limiter"]:
                try:
                    config = limiter.from_dict({"limiter": options["limiter"]})
                    config.path = options["limiter"].get("path")
                    self.limiter = config
                except LoadError as exc:
                    self._message(str(exc), error=True)
            else:
                self.limiter = None
        self.left_width = int(options.get("left_width", self.left_width))
        self.table_h = int(options.get("table_height", self.table_h))
        self.graph_font_size = max(FONT_MIN, min(FONT_MAX, int(options.get("graph_font_size", self.graph_font_size))))
        self.report_comment = str(options.get("report_comment", self.report_comment) or "")
        dpg.set_value(self.font_slider, self.graph_font_size)
        theme = options.get("theme", self.mode)
        if theme in themes.PALETTE and theme != self.mode:
            self.mode = theme
            self._apply_mode()
        for item, value in ((self.link_box, self.link_x), (self.sync_box, self.cross_sync), (self.reg_box, self.reg_on),
                            (self.date_box, self.date_axis), (self.theme_combo, t(self.mode))):
            dpg.set_value(item, value)
        dpg.configure_item(self.left_panel, width=self.left_width)
        dpg.configure_item(self.table_area, height=self.table_h)
        cross = bool(options.get("cross_on", False))
        dpg.set_value(self.cross_box, cross)
        self.cross_on = cross
        dpg.configure_item(self.table_area, show=cross)
        dpg.configure_item(self.split_table, show=cross)
        dpg.configure_item(self.plot_area, height=self._plot_area_height())
        self.m3_on = bool(options.get("marker3_on", False))
        dpg.set_value(self.m3_box, self.m3_on)
        if options.get("marker3_range") in self.M3_RANGES:
            self.set_m3_range(options["marker3_range"])

    def _on_restore_last(self, _sender, value) -> None:
        self.settings["restore_last"] = bool(value)
        self._save_settings()

    def _build_graph_tab(self) -> None:
        with dpg.child_window(height=-30, border=False):
            with dpg.group(horizontal=True):
                self._build_left_panel()
                self.split_left = dpg.add_button(label="", width=SPLIT, height=-1)
                self._tooltip(self.split_left, t("Ziehen: Breite der Dateiliste ändern"))
                with dpg.group():
                    self._build_toolbar()
                    self.plot_area = dpg.add_child_window(height=-1, border=True, payload_type=PAYLOAD,
                                                          drop_callback=self._on_drop)
                    self.split_table = dpg.add_button(label="", width=-1, height=SPLIT, show=False)
                    self._tooltip(self.split_table, t("Ziehen: Höhe der Wertanzeige ändern"))
                    with dpg.child_window(height=self.table_h, border=True, show=False) as self.table_area:
                        self._build_limit_source_row()
                        self.table_holder = dpg.add_child_window(height=-1, border=False)

    def _build_limit_source_row(self) -> None:
        """Kopfzeile der Wertanzeige: Quelle der Grenzen (manuell oder Mode der Grenzwert-Konfiguration)."""
        with dpg.group(horizontal=True):
            dpg.add_text(t("Mode"))
            self.mode_combo = dpg.add_combo(items=[t("(manuell)")], default_value=t("(manuell)"), width=230,
                                            callback=lambda _s, v: self.set_limit_mode(v))
            self._tooltip(self.mode_combo, t("Mode der Grenzwert-Konfiguration (Graph-Optionen > Grenzwert-Konfiguration "
                                             "laden). Für Signale, die der Mode nennt (enabled: true), gelten dessen "
                                             "Grenzen und steps; alle anderen behalten die manuellen Werte."))
            self.cfg_save = dpg.add_button(label=t("In YAML speichern"), callback=lambda: self.save_limit_config_back(),
                                           show=False)
            self._tooltip(self.cfg_save, t("Grenzen und steps, die hier oder im Konfigurator geändert wurden, in die "
                                           "geladene YAML-Datei zurückschreiben."))
            self.cfg_label = dpg.add_text("")
            self._colour(self.cfg_label, "text_dim")
        self._refresh_mode_combo()

    def _build_left_panel(self) -> None:
        with dpg.child_window(width=self.left_width, height=-1, border=True) as self.left_panel:
            with dpg.group(horizontal=True) as self.l_buttons:
                dpg.add_button(label=t("Dateien öffnen..."), callback=lambda: self._show_file_browser())
                dpg.add_button(label=t("Alle abwählen"), callback=self._on_clear_signals)
            self.same_name_box = dpg.add_checkbox(label=t("Gleichnamige Signale aller Dateien"),
                                                  default_value=bool(self.settings.get("same_name", False)),
                                                  show=len(self.datasets) > 1, callback=self._on_same_name)
            self._tooltip(self.same_name_box, t("An: Ein Häkchen wählt das gleichnamige Signal in allen offenen "
                                                "Dateien zugleich (gemeinsamer Graph: Zielgraph oder ein neuer), "
                                                "Abwählen entfernt sie alle. Aus: Einzelauswahl je Datei."))
            dpg.add_spacer(height=2)
            dpg.add_text(t("Zielgraph"))
            self.target_combo = dpg.add_combo(items=[t("Automatisch")], default_value=t("Automatisch"), width=-1)
            self._tooltip(self.target_combo, t("Graph für das nächste angehakte Signal."))
            self.filter_input = dpg.add_input_text(hint=t("Signal suchen"), width=-1,
                                                   callback=lambda: self._refresh_channel_list())
            # Suchtreffer, die es in mehreren Dateien gibt: über alle Dateien plotten
            with dpg.group(show=False) as self.multi_area:
                self.multi_title = dpg.add_text("", wrap=0)
                self._colour(self.multi_title, "heading")
                self.multi_combo = dpg.add_combo(items=[], width=-1, callback=lambda: self._multi_update_info())
                self._tooltip(self.multi_combo, t("Signal, das in mehreren geladenen Dateien vorkommt."))
                with dpg.group(horizontal=True):
                    self.multi_shared = dpg.add_button(label=t("Gemeinsamer Graph"), small=True, callback=self._multi_plot,
                                                       user_data="shared")
                    self._tooltip(self.multi_shared, t("Das Signal aller Dateien zusammen in einen Graphen "
                                                       "(gewählter Zielgraph oder ein neuer)."))
                    self.multi_single = dpg.add_button(label=t("Einzelgraphen"), small=True, callback=self._multi_plot,
                                                       user_data="single")
                    self._tooltip(self.multi_single, t("Je Datei ein eigener Graph mit diesem Signal."))
                    self.multi_remove = dpg.add_button(label=t("Entfernen"), small=True, callback=self._multi_remove)
                    self._tooltip(self.multi_remove, t("Dieses Signal aller Dateien aus allen Graphen entfernen."))
                self.multi_info = dpg.add_text("", wrap=0, color=themes.color(self.mode, "text_dim"))
                self._colour(self.multi_info, "text_dim")
            dpg.add_separator()
            self.channel_area = dpg.add_child_window(height=-1, border=False)

    def _toolbar_sep(self) -> None:
        """Dezenter senkrechter Trenner zwischen Gruppen der Werkzeugleiste."""
        dpg.add_spacer(width=2)
        sep = dpg.add_text("|")
        self._colour(sep, "border")
        dpg.add_spacer(width=2)

    def _build_toolbar(self) -> None:
        """Werkzeugleiste über den Graphen, zwei kompakte Zeilen mit Gruppen:
        1) Daten und Aufteilung: Datei | Matrix, Anwenden, Zeilen, Vorschlag | Alles anzeigen, Alle Plots löschen
        2) Anzeige und Messen: Marker, synchron | X koppeln, Datum/Uhrzeit, Regression | Vergleichen | Darstellung
        Selten Benötigtes (Farbschema, Schriftgröße) liegt im Aufklapper "Darstellung...". """
        with dpg.group() as self.toolbar_group:
            with dpg.group(horizontal=True) as self.toolbar_row1:
                label = dpg.add_text(t("Datei"))
                self._colour(label, "text_dim")
                self.file_combo = dpg.add_combo(items=[], width=260, callback=self._on_file_combo)
                self._tooltip(self.file_combo, t("Die vorhandenen Graphen mit den gleichnamigen Signalen dieser Datei "
                                                 "anzeigen. Signale anderer Dateien werden ersetzt, Matrix, Graphnamen, "
                                                 "Farben, Achsen und Grenzen bleiben."))
                self._toolbar_sep()
                label = dpg.add_text(t("Matrix"))
                self._colour(label, "text_dim")
                self.matrix_input = dpg.add_input_text(hint=t("z. B. 2*3"), width=110, on_enter=True,
                                                       callback=self._on_matrix)
                self._tooltip(self.matrix_input, t("n Zeilen * m Spalten, zum Beispiel 2*3.\nLeer: alle Graphen untereinander.\n"
                                                   "Zeilen zusammenfassen: 4*3: 3, 3, 2+1, 1 (je Zeile Anzahl gleich "
                                                   "breiter Graphen oder Breiten mit +)."))
                self.matrix_apply = dpg.add_button(label=t("Anwenden"), small=True, callback=self._on_matrix)
                self.rows_button = dpg.add_button(label=t("Zeilen..."), small=True, callback=lambda: self._open_rows_window())
                self._tooltip(self.rows_button, t("Graphbereiche in einzelnen Zeilen zusammenfassen, z. B. ein Graph über "
                                                  "zwei Spalten und einer über eine."))
                self.arrange_button = dpg.add_button(label=t("Vorschlag..."), small=True,
                                                     callback=lambda: self._open_arrange_window())
                self._tooltip(self.arrange_button, t("Anordnung vorschlagen: Signale nach Namen und Einheit gruppieren "
                                                     "(z. B. AC-Spannungen, AC-Ströme, Temperaturen) und eine passende "
                                                     "Matrix bilden."))
                self._toolbar_sep()
                self.fit_button = dpg.add_button(label=t("Alles anzeigen"), small=True, callback=self._fit_all)
                self._tooltip(self.fit_button, t("Alle Graphen auf den vollen Datenbereich zurücksetzen."))
                self.clear_plots_button = dpg.add_button(label=t("Alle Plots löschen"), small=True,
                                                         callback=self._clear_all_plots)
                self._tooltip(self.clear_plots_button, t("Plotbereich leeren: alle Graphen und die Aufteilung (Matrix, "
                                                         "zusammengefasste Bereiche) entfernen. Die Dateien bleiben geladen."))
            with dpg.group(horizontal=True) as self.toolbar_row2:
                self.cross_box = dpg.add_checkbox(label=t("Marker"), default_value=False, callback=self._on_cross_toggle)
                self.sync_box = dpg.add_checkbox(label=t("Marker synchron"), default_value=self.cross_sync,
                                                 callback=self._on_cross_sync)
                self.m3_box = dpg.add_checkbox(label=t("Marker 3"), default_value=self.m3_on,
                                               callback=lambda _s, v: self.set_marker3(v))
                self.m3_range_combo = dpg.add_combo([t(v) for v in self.M3_RANGES.values()],
                                                    default_value=t(self.M3_RANGES[self.m3_range]), width=190,
                                                    callback=self._on_m3_range)
                self._tooltip(self.m3_range_combo, t("Bereich für Min, Max, Average und Drift in der Wertetabelle "
                                                     "von Marker 3: zwischen M1 und M2 (nur bei eingeschalteten "
                                                     "Markern, sonst gesamter Verlauf) oder gesamter Signalverlauf."))
                self._tooltip(self.m3_box, t("Dritter Marker M3, unabhängig von M1 und M2: mit der Maus verschieben. "
                                             "Steht die Maus an M3, zeigt ein Tooltip die Werte aller Signale des "
                                             "Graphen an dieser Stelle als Tabelle. Mit \"Marker synchron\" laufen "
                                             "die M3 aller Graphen gleicher Achsenart mit."))
                self._toolbar_sep()
                self.link_box = dpg.add_checkbox(label=t("X-Achsen koppeln"), default_value=self.link_x,
                                                 callback=self._on_link)
                self.date_box = dpg.add_checkbox(label=t("Datum/Uhrzeit-Achse"), default_value=self.date_axis,
                                                 callback=self._on_date_axis)
                self._tooltip(self.date_box, t("X-Achse als Datum und Uhrzeit für Signale mit Startzeit\n"
                                               "(Zeitstempel in CSV/Parquet, Startzeit der MF4)."))
                self.reg_box = dpg.add_checkbox(label=t("Regressionslinien"), default_value=self.reg_on,
                                                callback=lambda _s, v: self._set_regression(v))
                self._tooltip(self.reg_box, t("Lineare Regressionsgerade über alle Daten je Signal als gestrichelte "
                                              "Linie in der Farbe des Signals (wie Spalte Drift (Regression)). Ohne "
                                              "eigenen Eintrag im Signalspiegel: Aktivieren/Deaktivieren des Signals "
                                              "dort schaltet seine Regressionslinie mit."))
                self._toolbar_sep()
                self.cmp_button = dpg.add_button(label=t("Dateien vergleichen..."), small=True,
                                                 callback=self._open_cmp_window)
                self._tooltip(self.cmp_button, t("Gleich oder ähnlich aufgebaute Dateien als Tabelle vergleichen (avg, min, max)."))
                self.view_button = dpg.add_button(label=t("Darstellung..."), small=True)
                self._tooltip(self.view_button, t("Farbschema und Schriftgröße der Graphen"))
                with dpg.popup(self.view_button, mousebutton=dpg.mvMouseButton_Left, tag="view_popup"):
                    dpg.add_text(t("Darstellung"))
                    self.theme_combo = dpg.add_combo(items=[t(mode) for mode in themes.MODES], default_value=t(self.mode),
                                                     width=200, callback=self._on_theme)
                    self._tooltip(self.theme_combo, t("Farbschema der Oberfläche und der Graphen. Die Linienfarben sind auf "
                                                      "den Hintergrund des Schemas abgestimmt; Druck, Export und Report "
                                                      "verwenden immer die helle Darstellung."))
                    dpg.add_text(t("Schrift"))
                    self.font_slider = dpg.add_slider_int(default_value=self.graph_font_size, min_value=FONT_MIN,
                                                          max_value=FONT_MAX, width=200, format="%d px",
                                                          callback=self._on_font_size)
                    self._tooltip(self.font_slider, t("Schriftgröße der Graphen (Titel, Achsen, Legende) und der Wertanzeige."))

    def _help_shown(self) -> bool:
        return dpg.does_item_exist("help_window") and bool(dpg.get_item_configuration("help_window").get("show"))

    def show_help(self) -> None:
        """Hilfe-Fenster öffnen (beim ersten Öffnen mittig, sonst dort, wo es zuletzt war)."""
        if not self._help_shown():
            vw, vh = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
            w, h = int(vw * 0.86), int(vh * 0.88)
            dpg.configure_item("help_window", show=True, width=w, height=h,
                               pos=[max(0, (vw - w) // 2), max(0, (vh - h) // 2)])
        try:
            dpg.focus_item("help_window")
        except Exception:
            pass

    def hide_help(self) -> None:
        if dpg.does_item_exist("help_window"):
            dpg.configure_item("help_window", show=False)

    def _build_help_tab(self) -> None:
        self.help_groups = {}
        self.help_textures = []
        with dpg.group(horizontal=True):
            with dpg.child_window(width=280, height=-30, border=True):
                self.help_pdf_btn = dpg.add_button(label=t("Als PDF speichern..."), width=-1, callback=self._ask_help_pdf)
                button = self.help_shots_btn = dpg.add_button(label=t("Screenshots erzeugen"), width=-1,
                                                              callback=self.start_screenshots)
                self._tooltip(button, t("Baut mit den Beispieldaten die gezeigten Situationen auf und\n"
                                        "fotografiert das Fenster (einige Sekunden, bitte nicht bedienen)."))
                dpg.add_separator()
                self.help_contents_label = dpg.add_text("")
                self._colour(self.help_contents_label, "heading")
                # Kapitel als Liste ohne feste Höhe: die Spalte scrollt als Ganzes
                self.help_list = dpg.add_group()
            self.help_content = dpg.add_child_window(height=-30, border=True)
        self._render_help()

    def _render_help(self) -> None:
        """Hilfe in der gewählten Sprache aufbauen, Screenshots einbinden, soweit vorhanden."""
        ui = help_content.ui(self.help_lang)
        chapters = help_content.chapters(self.help_lang)
        unicode_font = self.help_lang in help_content.NEEDS_UNICODE_FONT
        for item in (self.help_content, self.help_list):  # Thai: eigene Schrift nur für die Hilfe
            dpg.bind_item_font(item, self._lang_font(self.help_lang) or 0)
        dpg.set_value(self.help_contents_label, ui["contents"])
        dpg.delete_item(self.help_content, children_only=True)
        for texture in self.help_textures:
            if dpg.does_item_exist(texture):
                dpg.delete_item(texture)
        self.help_textures = []
        self.coloured_text = [(i, r) for i, r in self.coloured_text if dpg.does_item_exist(i)]
        self.help_groups = {}
        names = [title for title, _ in chapters]
        self.help_index = min(getattr(self, "help_index", 0), len(names) - 1)
        dpg.delete_item(self.help_list, children_only=True)
        self.help_items = {}
        for number, name in enumerate(names):
            self.help_items[name] = dpg.add_selectable(label=name, default_value=number == self.help_index,
                                                       parent=self.help_list, callback=self._on_help_select,
                                                       user_data=name)
        if unicode_font and self._lang_font(self.help_lang) is self.ui_font:
            self._colour(dpg.add_text(ui["no_font"], color=themes.color(self.mode, "error"), wrap=0,
                                      parent=self.help_content), "error")
        heading, dim = themes.color(self.mode, "heading"), themes.color(self.mode, "text_dim")
        for index, (title, content) in enumerate(chapters):
            with dpg.group(show=index == self.help_index, parent=self.help_content) as group:
                self.help_groups[title] = group
                self._colour(dpg.add_text(title, color=heading), "heading")
                dpg.add_separator()
                for item in content:
                    kind = item[0]
                    if kind == "h":
                        dpg.add_spacer(height=6)
                        self._colour(dpg.add_text(item[1], color=heading), "heading")
                    elif kind == "b":
                        dpg.add_text(item[1], bullet=True, wrap=0)
                    elif kind == "img":
                        self._help_image(item[1], item[2], dim)
                    elif kind == "m":
                        with dpg.group(horizontal=True):
                            dpg.add_text(f"({item[1]})", color=MARK_RGB)
                            dpg.add_text(item[2], wrap=0)
                    else:
                        dpg.add_text(item[1], wrap=0)

    def _help_image(self, image_id: str, caption: str, dim) -> None:
        path, illustration = help_content.image_path(image_id, HELP_IMAGES)
        loaded = dpg.load_image(str(path)) if path else None
        if illustration:
            caption += help_content.ui(self.help_lang)["illustration"]
        dpg.add_spacer(height=4)
        if loaded:
            width, height, _, data = loaded
            texture = dpg.add_static_texture(width, height, data, parent=self.texture_registry)
            self.help_textures.append(texture)
            shown = min(width, max(400, dpg.get_viewport_client_width() - self.left_width - 120))
            dpg.add_image(texture, width=shown, height=int(height * shown / width))
            self._colour(dpg.add_text(caption, color=dim, wrap=0), "text_dim")
        else:
            missing = help_content.UI_TEXT[self.help_lang]["missing"]
            self._colour(dpg.add_text(f"[{caption}]  {missing}", color=dim, wrap=0), "text_dim")
        dpg.add_spacer(height=4)

    def _on_help_language(self, _sender, value) -> None:
        """Rückwärtskompatibel: Die Hilfe folgt der Sprache der Oberfläche."""
        self.set_language(value)

    def _on_help_select(self, _sender, _value, title) -> None:
        self._on_help_chapter(None, title)

    def _on_help_chapter(self, _sender, title) -> None:
        names = list(self.help_groups)
        if title in names:
            self.help_index = names.index(title)
        for name, group in self.help_groups.items():
            dpg.configure_item(group, show=name == title)
        for name, item in getattr(self, "help_items", {}).items():   # gewähltes Kapitel markiert lassen
            if dpg.does_item_exist(item):
                dpg.set_value(item, name == title)

    # ---------------------------------------------------------------- Hilfe als PDF
    def _ask_help_pdf(self, *_args) -> None:
        suffix = {"Deutsch": "DE", "English": "EN", "Thai": "TH", "Chinese": "ZH"}.get(self.help_lang, "DE")
        default = str(Path(self.settings.get("last_pdf_dir") or Path.home()) / f"MessGraph_Hilfe_{suffix}.pdf")
        self.save_prompt_values = {"language": i18n.NAMES[self.help_lang]}
        self._ask_save_path("Hilfe als PDF", "PDF-Datei für die Hilfe ({language}):", default, self.save_help_pdf)

    def save_help_pdf(self, path: str) -> None:
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            pages = build_help_pdf(self.help_lang, path, self._load_help_image,
                                   font_path=self._lang_font_path(self.help_lang)
                                   if self.help_lang in i18n.SCRIPT_LANGUAGES else None)
        except LoadError as exc:
            self._message(t("PDF nicht erstellt: {error}", error=exc), error=True)
            return
        except Exception as exc:
            log_exception("Hilfe als PDF", exc)
            self._message(f"{t('PDF nicht erstellt: {error}', error=f'{type(exc).__name__}: {exc}')}  ({t('Details: {path}', path=LOG_FILE)})", error=True)
            return
        self.settings["last_pdf_dir"] = os.path.dirname(path)
        self._save_settings()
        drawn = [i for i in help_content.image_ids() if help_content.image_path(i, HELP_IMAGES)[1]]
        note = (" " + t("{count} Bilder sind nachgezeichnet; \"Screenshots erzeugen\" ersetzt sie durch echte Aufnahmen.",
                        count=len(drawn)) if drawn else "")
        self._message(t("Hilfe als PDF gespeichert: {path} ({pages} Seiten).", path=path, pages=pages) + note)

    # ---------------------------------------------------------------- Screenshots für die Hilfe
    def start_screenshots(self, *_args) -> None:
        if self.shots:
            return
        if not hasattr(dpg, "output_frame_buffer"):
            self._message(t("Diese Dear-PyGui-Version kann keine Screenshots speichern (output_frame_buffer fehlt)."),
                          error=True)
            return
        demo = [DEMO_DIR / n for n in ("demo_einfach.csv", "demo_deutsch_vorspann.csv", "demo_zeitstempel.csv")]
        if not all(p.exists() for p in demo):
            self._message(t("Beispieldaten fehlen in {path}: python tools/make_demo_data.py ausführen.", path=DEMO_DIR), error=True)
            return
        try:
            HELP_IMAGES.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._message(t("Bilderordner nicht anlegbar: {error}", error=exc), error=True)
            return
        extra = [p for p in (DEMO_DIR / "demo.mf4",) if p.exists()]
        self.shots = {"restore": self.session_dict(), "queue": list(SHOT_SCENES), "phase": "next",
                      "frames": SHOT_SETTLE_FRAMES, "done": [], "current": None}
        self._shot_cleanup()
        self.hide_help()
        demo_view = {"format": sessions.FORMAT, "version": sessions.VERSION, "graphs": [], "matrix": None,
                     "files": [{"path": str(p)} for p in demo + extra],
                     "options": {"cross_on": False, "date_axis": False, "link_x": True, "cross_sync": True}}
        self.apply_session(demo_view, None)
        self._message(t("Screenshots werden erzeugt, bitte nicht bedienen..."))

    def _shot_channel(self, file_name: str, name: str) -> Channel | None:
        for dataset in self.datasets:
            if dataset.name == file_name:
                return next((c for c in dataset.channels if c.name == name), None)
        return None

    def _shot_layout(self, graphs: list, matrix=None, cross=False, date_axis=False) -> None:
        """graphs: [(Titel, [(Datei, Kanal, Farbe oder None), ...]), ...]"""
        layout = PlotLayout()
        layout.matrix = matrix
        for title, signals in graphs:
            slot = GraphSlot(title=title)
            for entry in signals:  # (Datei, Kanal, Farbe[, rechte Achse])
                file_name, name, color = entry[:3]
                channel = self._shot_channel(file_name, name)
                if channel is not None and channel.loaded:
                    slot.signals.append(channel)
                    if color:
                        slot.colors[channel] = color
                    if len(entry) > 3 and entry[3]:
                        slot.right.add(channel)
            layout.slots.append(slot)
        if not matrix:
            layout.slots = [s for s in layout.slots if s.signals]
        self.layout = layout
        dpg.set_value(self.matrix_input, f"{matrix[0]}*{matrix[1]}" if matrix else "")
        self.date_axis = date_axis
        dpg.set_value(self.date_box, date_axis)
        if cross != self.cross_on:
            dpg.set_value(self.cross_box, cross)
            self._on_cross_toggle(None, cross)
        self._layout_changed()

    # Jede Szene setzt self.shot_marks = [(Nummer, Element, Lage[, Rahmen])], passend zur Legende der Hilfe.
    def _scene_uebersicht(self):
        self._shot_layout([("", [("demo_einfach.csv", "speed", None)]),
                           ("", [("demo_einfach.csv", "temperature", None)])])
        self.shot_marks = [("1", self.menu_bar, "left"), ("2", self.left_panel, "center"),
                           ("3", self.toolbar_group, "right", True), ("4", self.plot_area, "center"),
                           ("5", self.split_left, "center", True), ("6", self.status, "right")]

    def _scene_dateiliste(self):
        self._shot_layout([("", [("demo_deutsch_vorspann.csv", "Drehzahl", None)]),
                           ("", [("demo_einfach.csv", "speed", None)])])
        first_box = next(iter(self.checkboxes.values()), None)
        self.shot_marks = [("1", self.l_buttons, "right"), ("2", self.target_combo, "right"),
                           ("3", self.filter_input, "right")]
        if self.file_headers:
            self.shot_marks.append(("4", self.file_headers[0], "right"))
        if first_box is not None:
            self.shot_marks.append(("7", first_box, "right"))

    def _scene_browser(self):
        self._show_file_browser()
        self._fb_go(str(DEMO_DIR))
        self._fb_select_all(True)
        first = next(iter(self.fb_boxes.values()), None)
        self.shot_marks = [("1", self.fb_path, "left"), ("2", self.fb_filter, "right", True),
                           ("5", self.fb_count, "right"), ("6", self.fb_open_btn, "right")]
        if first is not None:
            self.shot_marks.append(("4", first, "right"))

    def _scene_matrix(self):
        self._shot_layout([("Fahrzeug", [("demo_einfach.csv", "speed", None),
                                         ("demo_einfach.csv", "temperature", (240, 200, 60), True)]),
                           ("Bordnetz", [("demo_einfach.csv", "voltage", None)]),
                           ("Prüfstand", [("demo_deutsch_vorspann.csv", "Drehzahl", None)]),
                           ("", [("demo_zeitstempel.csv", "Current", None)])], matrix=(2, 2))
        self.shot_marks = [("1", self.matrix_input, "bottom", True), ("4", self.target_combo, "right")]
        if self.slot_ui:
            self.shot_marks.append(("2", self.slot_ui[0].plot, "top"))
            if self.slot_ui[0].y2_axis is not None:
                self.shot_marks.append(("5", self.slot_ui[0].y2_axis, "left", True))

    def _scene_kontextmenue(self):
        self._scene_matrix()
        if not self.slot_ui:
            return False
        plot = self.slot_ui[0].plot
        try:
            x, y = dpg.get_item_rect_min(plot)
        except Exception:
            x, y = 400, 200
        self._open_context_menu(self.slot_ui[0].slot, (x + 160, y + 40))
        self.shot_marks = [("1", self.ctx_title, "left"), ("2", self.ctx_filter, "left"),
                           ("3", self.ctx_remove_first, "left"), ("4", self.ctx_color_first, "left"),
                           ("6", self.ctx_axis_first, "left"), ("7", getattr(self, "ctx_print_all", None), "left")]

    def _scene_berechnen(self):
        path = DEMO_DIR / "demo_lauf_1.csv"
        if not path.exists():
            return False
        self._shot_layout([])
        dataset = load_file(str(path))
        dataset.extra["shot_demo"] = True
        power = formula.add_or_replace(dataset, formula.compute(dataset, "Leistung", "kW", "{Strom} * {Spannung} / 1000"))
        self.datasets.append(dataset)
        self.layout.add(power)
        self._layout_changed()
        self._refresh_channel_list()
        self._open_calc_window(None, None, dataset)
        dpg.set_value(self.calc_name, "Widerstand")
        dpg.set_value(self.calc_formula, "{Spannung} / {Strom}")
        self.shot_marks = [("2", self.calc_list, "right", True), ("3", self.calc_name, "right", True),
                           ("4", self.calc_formula, "right", True), ("5", self.calc_signal, "right", True),
                           ("6", self.calc_run, "bottom", True), ("7", self.checkboxes.get(power), "right", True)]

    def _scene_drucken(self):
        self._scene_matrix()
        if not self.slot_ui:
            return False
        self.slot_ui[0].slot.legend = "ne"   # Legende oben rechts zeigen
        self._open_export("all")
        dpg.set_value(self.exp_target, t(TARGET_NAMES["pdf"]))
        self._exp_target_changed()
        self.shot_marks = [("1", self.exp_target, "right", True), ("2", self.exp_orient, "right", True),
                           ("3", self.exp_paper, "right", True), ("4", self.exp_path, "bottom", True),
                           ("5", self.exp_run_btn, "right", True)]

    def _scene_crosslines(self):
        self._shot_layout([("Fahrzeug", [("demo_einfach.csv", "speed", None),
                                         ("demo_einfach.csv", "temperature", (240, 200, 60))]),
                           ("Bordnetz", [("demo_einfach.csv", "voltage", None)])], cross=True)
        self._shot_limits(1, "voltage", [12.8, 13.95])
        self.shot_marks = [("1", self.cross_box, "bottom", True), ("4", self.table_area, "center"),
                           ("5", self.split_table, "center", True), ("6", self.limit_boxes.get((1, "voltage", 0)), "bottom", True)]

    def _scene_datumsachse(self):
        self._shot_layout([("", [("demo_zeitstempel.csv", "Current", None)])], cross=True, date_axis=True)
        self._shot_limits(0, "Current", [-20.0, None])
        self.shot_marks = [("1", self.date_box, "bottom", True), ("3", self.table_area, "center"),
                           ("5", self.limit_boxes.get((0, "Current", 0)), "bottom", True),
                           ("6", self.table_preds[0][1] if self.table_preds else None, "top", True)]

    def _shot_limits(self, index: int, name: str, limits: list) -> None:
        """Grenzen für ein Signal im Bild setzen und Graphen samt Tabelle neu aufbauen."""
        slot = self.layout.slots[index]
        channel = next((c for c in slot.signals if c.name == name), None)
        if channel is not None:
            slot.limits[channel] = limits
            self._layout_changed()

    def _scene_datenbasen(self):
        dataset = next((d for d in self.datasets if "mdf" in d.extra), None)
        if dataset is None:
            return False
        self._shot_layout([])
        self._open_db_window(None, None, dataset)
        self.shot_marks = [("1", self.db_dbc_area, "left"), ("2", self.db_add_btn, "left"),
                           ("3", self.db_a2l_area, "left"), ("4", self.db_cdd_area, "left"),
                           ("5", self.db_last_button, "right"), ("7", self.db_auto, "left")]

    def _scene_ansicht(self):
        self._scene_uebersicht()
        name, comment, path = self.project_name, self.project_comment, self.project_path
        self.project_name, self.project_comment = "Prüfstand 3", "Lauf nach Software-Update"
        self.project_path = str(Path.home() / f"Pruefstand3{project.SUFFIX}")
        self._open_project_window()
        self.project_name, self.project_comment, self.project_path = name, comment, path
        self.shot_marks = [("3", self.proj_name, "left"), ("4", self.proj_path, "bottom"),
                           ("5", self.proj_save_btn, "right")]

    def _scene_allefiles(self):
        paths = [DEMO_DIR / f"demo_lauf_{i}.csv" for i in (1, 2, 3)]
        if not all(p.exists() for p in paths):
            return False
        self._shot_layout([])
        for path in paths:
            dataset = load_file(str(path))
            dataset.extra["shot_demo"] = True
            self.datasets.append(dataset)
        dpg.set_value(self.filter_input, "temp")    # wird beim Abschluss wieder geleert
        self._refresh_channel_list()
        dpg.set_value(self.multi_combo, "Temperatur")
        self._multi_plot(None, None, "shared")
        self.shot_marks = [("1", self.filter_input, "right"), ("2", self.multi_combo, "right"),
                           ("3", self.multi_remove, "right"), ("4", self.multi_info, "right")]

    def _scene_vorschlag(self):
        path = DEMO_DIR / "demo_pruefstand.asc"
        if not path.exists():
            return False
        dpg.set_value(self.filter_input, "")
        self._shot_layout([])
        dataset = load_file(str(path))
        dataset.extra["shot_demo"] = True
        self.datasets.append(dataset)
        self._refresh_channel_list()
        self._open_arrange_window()
        self.shot_marks = [("1", self.arrange_button, "bottom"), ("2", self.arr_source, "left"),
                           ("3", self.arr_preview, "left"), ("4", self.arr_list, "right"),
                           ("5", self.arr_apply_btn, "right")]

    def _scene_konfigurator(self):
        path, config = DEMO_DIR / "demo_pruefstand.asc", DEMO_DIR / "demo_grenzen.yaml"
        if not path.exists() or not config.exists():
            return False
        dpg.set_value(self.filter_input, "")
        self._shot_layout([])
        dataset = load_file(str(path))
        dataset.extra["shot_demo"] = True
        self.datasets.append(dataset)
        self._refresh_channel_list()
        self.load_limit_config(str(config), "EU_AC_3ph_11kW_800V", quiet=True)
        self.open_limit_editor()
        self.shot_marks = [("1", self.le_file, "right"), ("2", self.le_mode, "right"), ("3", self.le_steps, "right"),
                           ("4", self.le_margin, "right"), ("5", self.le_table_area, "inside", True)]

    def _scene_zeilen(self):
        path = DEMO_DIR / "demo_lauf_1.csv"
        if not path.exists():
            return False
        dpg.set_value(self.filter_input, "")
        self._shot_layout([])
        dataset = load_file(str(path))
        dataset.extra["shot_demo"] = True
        self.datasets.append(dataset)
        self._refresh_channel_list()
        spans = [[1, 1, 1], [1, 1, 1], [2, 1], [3]]
        self.layout.set_matrix((4, 3), spans)
        for index, slot in enumerate(self.layout.slots):
            slot.signals.append(dataset.channels[index % len(dataset.channels)])
        dpg.set_value(self.matrix_input, format_layout((4, 3), spans))
        self._layout_changed()
        self._open_rows_window()
        self.shot_marks = [("1", self.matrix_input, "bottom"), ("2", self.rows_button, "bottom"),
                           ("5", self.rows_area, "left"), ("6", self.rows_preview, "top"),
                           ("7", self.rows_apply_btn, "left")]

    def _scene_ascii(self):
        path = DEMO_DIR / "demo_pruefstand.asc"
        if not path.exists():
            return False
        dpg.set_value(self.filter_input, "")
        self._shot_layout([])
        dataset = load_file(str(path))
        dataset.extra["shot_demo"] = True
        self.datasets.append(dataset)
        self._refresh_channel_list()
        self._open_ascii_window(None, None, str(path))
        self.shot_marks = [("1", self.ascii_lines, "left"), ("2", self.ascii_header, "left"),
                           ("3", self.ascii_decimal, "right"), ("4", self.ascii_result, "left"),
                           ("5", self.ascii_apply_btn, "left")]

    def _scene_vergleich(self):
        dpg.set_value(self.filter_input, "")
        paths = [DEMO_DIR / f"demo_lauf_{i}.csv" for i in (1, 2, 3)]
        if not all(p.exists() for p in paths):
            return False
        self._shot_layout([])
        for path in paths:
            dataset = load_file(str(path))
            dataset.extra["shot_demo"] = True
            self.datasets.append(dataset)
        self._refresh_channel_list()
        self.cmp_files, self.cmp_signals = None, set()
        self._open_cmp_window()
        self.cmp_signals = {"Drehzahl", "Strom", "Spannung", "Temperatur"}
        self._cmp_refresh_signals()
        selected = self._cmp_selected()
        self.cmp_result = compare.compute(selected, [n for n, _ in compare.signal_union(selected) if n in self.cmp_signals],
                                          compare.STATS)
        self.shot_pct_backup = dict(self.cmp_pct)   # Toleranzen nur für das Bild, danach zurück
        self.cmp_pct = {"Strom": "4", "Spannung": "1"}
        self._cmp_show(self.cmp_result)
        red = next((name for _n, row, name, _c in self.cmp_rows if row.signal == "Strom"), None)
        width, height = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
        dpg.configure_item("cmp_window", pos=[30, 40], width=max(900, width - 60), height=max(600, height - 80))
        self.shot_marks = [("1", self.cmp_file_area, "right", True), ("2", self.cmp_file_buttons, "right"),
                           ("3", self.cmp_stat_row, "right"), ("4", self.cmp_filter_row, "bottom"),
                           ("5", self.cmp_signal_area, "left", True), ("6", self.cmp_actions, "right"),
                           ("7", self.cmp_table_area, "inside", True), ("9", self.cmp_pct_boxes.get("Strom"), "right", True),
                           ("10", red, "left", True)]

    def _scene_hilfe(self):
        self._shot_layout([])
        self.show_help()
        names = list(self.help_groups)
        index = next((i for i, (_, content) in enumerate(help_content.chapters(self.help_lang))
                      if any(it[0] == "img" and it[1] == "kontextmenue" for it in content)), 0)
        self._on_help_chapter(None, names[index])
        self.shot_marks = [("1", self.lang_menu, "bottom", True), ("2", self.help_pdf_btn, "right"),
                           ("3", self.help_shots_btn, "right"), ("4", self.help_list, "right", True),
                           ("6", self.help_menu, "bottom", True)]

    def _draw_marks(self) -> None:
        """Nummerierte Markierungen über das Fenster legen (wie in den Bildern der Hilfe)."""
        self.shot_overlay = dpg.add_viewport_drawlist(front=True)
        width, height = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
        for mark in self.shot_marks:
            number, item, where = mark[:3]
            try:
                x0, y0 = dpg.get_item_rect_min(item)
                x1, y1 = dpg.get_item_rect_max(item)
            except Exception:
                continue
            if x1 <= x0 or y1 <= y0:
                continue
            if len(mark) > 3 and mark[3]:
                dpg.draw_rectangle((x0 - 4, y0 - 3), (x1 + 4, y1 + 3), color=(*MARK_RGB, 255), thickness=2.5,
                                   rounding=5, parent=self.shot_overlay)
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            cx = {"left": x0 - 22, "right": x1 + 22}.get(where, cx)
            cy = {"top": y0 - 20, "bottom": y1 + 20}.get(where, cy)
            cx, cy = max(16, min(width - 16, cx)), max(16, min(height - 16, cy))
            dpg.draw_circle((cx, cy), 15, color=(255, 255, 255, 255), fill=(*MARK_RGB, 255), thickness=2,
                            parent=self.shot_overlay)
            dpg.draw_text((cx - 5 * len(number), cy - 10), number, color=(255, 255, 255, 255), size=19,
                          parent=self.shot_overlay)

    def _clear_marks(self) -> None:
        if self.shot_overlay is not None and dpg.does_item_exist(self.shot_overlay):
            dpg.delete_item(self.shot_overlay)
        self.shot_overlay = None
        self.shot_marks = []

    def _shot_cleanup(self) -> None:
        self._clear_marks()
        self.hide_help()
        self._close_context_menu()
        for window in ("file_browser", "db_window", "save_dialog", "cmp_window", "export_window", "calc_window", "ascii_window",
                       "project_window", "rows_window",
                       "arrange_window", "limit_editor"):
            dpg.configure_item(window, show=False)
        self.fb_selected = {}
        demo = [d for d in self.datasets if d.extra.get("shot_demo")]
        if demo:  # Beispielläufe des Vergleichsbilds wieder entfernen
            for dataset in demo:
                self.datasets.remove(dataset)
                for channel in dataset.channels:
                    self.layout.remove(channel)
                dataset.close()
            self._layout_changed()
            self.cmp_files, self.cmp_signals, self.cmp_result = None, set(), None
            self.cmp_pct = getattr(self, "shot_pct_backup", self.cmp_pct)
            self._refresh_channel_list()

    def _poll_screenshots(self) -> None:
        shots = self.shots
        if not shots or self.pending or self.loading or not self.results.empty():
            return
        if shots["frames"] > 0:
            shots["frames"] -= 1
            return
        if shots["phase"] == "capture":
            self._draw_marks()
            shots["phase"], shots["frames"] = "shoot", 2   # Markierungen erst zeichnen lassen
            return
        if shots["phase"] == "shoot":
            dpg.output_frame_buffer(file=str(HELP_IMAGES / f"{shots['current']}.png"))
            shots["done"].append(shots["current"])
            shots["phase"], shots["frames"] = "next", 5
            return
        self._shot_cleanup()
        while shots["queue"]:
            scene = shots["queue"].pop(0)
            try:
                skipped = getattr(self, f"_scene_{scene}")() is False
            except Exception as exc:
                log_exception(f"Screenshot {scene}", exc)
                skipped = True
            if not skipped:
                shots["current"], shots["phase"], shots["frames"] = scene, "capture", SHOT_SETTLE_FRAMES
                return
        self._finish_screenshots()

    def _finish_screenshots(self) -> None:
        shots, self.shots = self.shots, None
        done = shots["done"]
        restore = shots["restore"]
        dpg.set_value(self.filter_input, "")
        self.date_axis = bool(restore.get("options", {}).get("date_axis", self.settings.get("date_axis", False)))

        def finished():
            self._render_help()
            self.show_help()
            missing = [s for s in SHOT_SCENES if s not in done]
            note = " " + t("Nicht erzeugt: {names} (dafür fehlen Beispieldaten).", names=", ".join(missing)) if missing else ""
            self._message(t("{count} Screenshots gespeichert in {path}.", count=len(done), path=HELP_IMAGES) + note)

        self.apply_session(restore, None, done=finished)

    def _load_help_image(self, image_id: str):
        """Bild als RGB für das PDF, auf höchstens 1400 Pixel Breite verkleinert.

        Eigene Aufnahme vor mitgelieferter Abbildung. Eine unlesbare oder beschädigte Datei (z. B. abgebrochene
        Aufnahme mit Größe 0) bricht das PDF nicht ab: dann die mitgelieferte Abbildung, sonst ein Hinweis im PDF."""
        path, illustration = help_content.image_path(image_id, HELP_IMAGES)
        candidates = [(path, illustration)] if path else []
        bundled = help_content.BUNDLED_IMAGES / f"{image_id}.png"
        if bundled.exists() and (not path or Path(path) != bundled):
            candidates.append((bundled, True))
        for candidate, drawn in candidates:
            try:
                rgb = self._read_rgb(str(candidate))
            except Exception as exc:
                log_exception(f"Hilfe-Bild {candidate}", exc)
                rgb = None
            if rgb is not None:
                step = max(1, int(np.ceil(rgb.shape[1] / 1400)))
                rgb = np.ascontiguousarray(rgb[::step, ::step])
                return rgb.shape[1], rgb.shape[0], rgb.tobytes(), drawn
            self._message(t("Bild nicht lesbar, übersprungen: {path}", path=candidate), error=True)
        return None

    @staticmethod
    def _read_rgb(path: str):
        """Bilddatei -> uint8-Array (Höhe, Breite, 3) oder None. Pillow, sonst dpg.load_image mit Prüfung der Maße."""
        try:
            from PIL import Image
        except ImportError:
            Image = None
        if Image is not None:
            with Image.open(path) as image:
                rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
            return rgb if rgb.ndim == 3 and rgb.shape[0] > 0 and rgb.shape[1] > 0 else None
        loaded = dpg.load_image(path)
        if not loaded or len(loaded) < 4:
            return None
        width, height, channels, data = (int(loaded[0]), int(loaded[1]), int(loaded[2]), loaded[3])
        if width <= 0 or height <= 0 or channels not in (3, 4):
            return None
        flat = np.asarray(data, dtype=np.float32).ravel()
        if flat.size != width * height * channels:
            return None
        pixels = flat.reshape(height, width, channels)[:, :, :3]
        return (np.clip(pixels, 0.0, 1.0) * 255 + 0.5).astype(np.uint8)

    def _colour(self, item: int, role: str) -> None:
        self.coloured_text.append((item, role))

    @staticmethod
    def _tooltip(item: int, text: str) -> None:
        with dpg.tooltip(item):
            dpg.add_text(text)

    # ---------------------------------------------------------------- Dateien
    def open_files(self, paths) -> None:
        known = {os.path.abspath(d.path) for d in self.datasets}
        fresh, seen = [], set()
        for path in paths:
            absolute = os.path.abspath(path)
            if absolute not in known and absolute not in seen:
                fresh.append(absolute)
                seen.add(absolute)
        if not fresh:
            self._message(t("Keine neue Datei gewählt.") if paths else t("Keine lesbare Datei gewählt."))
            return
        self.pending += len(fresh)
        self._message(t("Lade {count} Datei(en)...", count=self.pending))
        for path in fresh:  # Fortschritt für MF4 und Parquet
            job = self._start_job(Path(path).name) if downsample.applies(path) else None
            self.pool.submit(self._load_worker, path, job)

    def _start_job(self, name: str) -> progress.Job:
        job = progress.Job(name)
        self.jobs.append(job)
        return job

    def _cancel_jobs(self, *_args) -> None:
        for job in self.jobs:
            job.cancelled = True
        if not self.jobs:                      # Statuszeile zeigt gerade die Auto-Auswertung
            self.cancel_auto()

    def _poll_progress(self) -> None:
        if not self.jobs:
            return
        active = [job for job in self.jobs if not job.done]
        if not active:  # alles fertig: Anzeige ausblenden, nächster Ladevorgang beginnt bei 0 %
            self.jobs.clear()
            dpg.configure_item(self.progress_row, show=False)
            return
        job = active[0]
        _fraction, text, busy = job.snapshot()
        total = progress.overall(self.jobs)
        overlay = f"{int(total * 100)} %"
        if job.cancelled:
            overlay = t("Abbrechen...")
        elif busy:  # Dauer unbekannt: Punkte laufen, damit sichtbar bleibt, dass gearbeitet wird
            overlay += " " + "." * (1 + int(time.monotonic() * 3) % 3)
        line = f"{job.name}: {text}  ({int(time.monotonic() - job.started)} s)"
        if len(self.jobs) > 1:
            line = t("{done} von {count} fertig", done=len(self.jobs) - len(active), count=len(self.jobs)) + " | " + line
        if len(active) > 1:
            line += "  " + t("(+{count} parallel)", count=len(active) - 1)
        dpg.set_value(self.progress_bar, total)
        dpg.configure_item(self.progress_bar, overlay=overlay)
        dpg.set_value(self.progress_text, line)
        dpg.configure_item(self.progress_row, show=True)

    def _load_worker(self, path: str, job=None, options: dict | None = None) -> None:
        try:
            with progress.track(job):
                dataset = self._load_with_template(path, options)
            self.results.put(("file", path, dataset, None))
        except progress.Cancelled:
            self.results.put(("file", path, None, CANCELLED))
        except Exception as exc:  # jede Fremddatei kann Unerwartetes auslösen
            log_exception(f"Datei laden: {path}", exc)
            text = str(exc) if isinstance(exc, LoadError) else f"{type(exc).__name__}: {exc}"
            self.results.put(("file", path, None, text))

    def _load_with_template(self, path: str, options: dict | None) -> Dataset:
        """ASCII: Vorgabe des Nutzers (Dialog bzw. gemerkte Vorlage für asc/txt/dat ...), sonst automatisch."""
        if options is None and is_ascii(path) and not path.lower().endswith(".csv"):
            template = self.settings.get("ascii_template")
            if template:
                try:
                    return load_file(path, template)
                except LoadError:
                    pass                      # Vorlage passt nicht: automatische Erkennung
        return load_file(path, options) if options else load_file(path)

    def _channel_worker(self, channel: Channel, job=None) -> None:
        try:
            with progress.track(job):
                channel.load()
            self.results.put(("channel", channel, None))
        except progress.Cancelled:
            self.results.put(("channel", channel, CANCELLED))
        except Exception as exc:
            log_exception(f"Kanal laden: {channel.name} aus {channel.source}", exc)
            text = str(exc) if isinstance(exc, LoadError) else f"{type(exc).__name__}: {exc}"
            self.results.put(("channel", channel, text))

    def _drain_results(self) -> None:
        while True:
            try:
                item = self.results.get_nowait()
            except queue.Empty:
                return
            if item[0] == "file":
                self._file_done(*item[1:])
            elif item[0] == "db":
                self._db_done(*item[1:])
            elif item[0] == "session":
                self._session_done(*item[1:])
            elif item[0] == "compare":
                self._cmp_done(*item[1:])
            elif item[0] == "calc":
                self._calc_done(*item[1:])
            elif item[0] == "definitions":
                self._definitions_done(*item[1:])
            elif item[0] == "ascii":
                self._ascii_done(*item[1:])
            else:
                self._channel_done(*item[1:])
            if self._apply_limiter():                       # neue Datei oder nachgeladener Kanal: Limiter anwenden
                self._layout_changed()
                self._limiter_status()

    def _file_done(self, path, dataset, error) -> None:
        self.pending -= 1
        name = Path(path).name
        if error == CANCELLED:
            self._message(t("{name}: Laden abgebrochen.", name=name))
            return
        if error:
            self._message(f"{name}: {error}  ({t('Details: {path}', path=LOG_FILE)})", error=True)
            if is_ascii(path) and os.path.isfile(path):   # Struktur nicht erkannt: Kopfzeile selbst festlegen
                self._open_ascii_window(None, None, path)
                dpg.set_value(self.ascii_status, t("Nicht erkannt: {error}. Bitte Kopfzeile und Trennzeichen "
                                                   "festlegen.", error=error))
            return
        self.datasets.append(dataset)
        self.datasets.sort(key=lambda d: d.name.lower())  # Ladereihenfolge ist zufällig
        self._refresh_channel_list()
        text = (t("{name}: {count} Signale. Noch {pending} Datei(en) in Arbeit.", name=name,
                  count=len(dataset.channels), pending=self.pending) if self.pending
                else t("{name}: {count} Signale.", name=name, count=len(dataset.channels)))
        groups = compare.similar_groups(self.datasets) if not self.pending else []
        group = groups[0] if groups else None   # nach dem letzten Ladevorgang: ähnliche Dateien vorhanden?
        if group:
            text += " " + t("{count} Dateien mit ähnlichem Aufbau: Vergleich über \"Dateien vergleichen...\".", count=len(group))
        self._message(text)
        bus = dataset.extra.get("bus_raw") or "blf" in dataset.extra
        if bus and self._db_auto_apply(dataset):
            return
        if dataset.extra.get("bus_raw") and not dpg.is_item_shown("db_window"):
            self._open_db_window(None, None, dataset)  # Rohdaten: ohne DBC gibt es keine Signale

    def _channel_done(self, channel, error) -> None:
        if channel not in self.loading:
            return  # inzwischen abgewählt oder Datei geschlossen
        target = self.loading.pop(channel)
        if target is LIMITER:
            if error and error != CANCELLED:
                self._message(f"{t('Limiter')}: {error}", error=True)
            return
        if target is FILE_SWITCH:
            self._switch_channel_done(channel, error)
            return
        if error == CANCELLED:
            self._sync_checkboxes()
            self._message(t("{name}: Laden abgebrochen.", name=channel.name))
            return
        if error:
            self._sync_checkboxes()
            self._message(f"{error}  ({t('Details: {path}', path=LOG_FILE)})", error=True)
            return
        self._add_signal(channel, target)

    # ---------------------------------------------------------------- Datenbasen (MF4)
    # ---------------------------------------------------------------- ASCII-Import
    ASCII_SEPS = [("", "Automatisch"), (",", "Komma"), (";", "Semikolon"), ("\t", "Tabulator"),
                  (" ", "Leerzeichen"), ("|", "Senkrechtstrich")]
    ASCII_DECIMALS = [("", "Automatisch"), (".", "Punkt"), (",", "Komma")]

    def _build_ascii_window(self) -> None:
        dim = themes.color(self.mode, "text_dim")
        self.ascii_path = None
        with dpg.window(tag="ascii_window", label=t("ASCII-Import"), show=False, width=980, height=700,
                        no_collapse=True):
            self.ascii_title = dpg.add_text("")
            self._colour(self.ascii_title, "heading")
            item = dpg.add_text(t("Anfang der Datei (Zeilennummern wie im Editor). Markiert: Kopfzeile, "
                                  "Einheitenzeile, erste Datenzeile. Zusatzinformationen wie <{Continue}> werden "
                                  "ignoriert, die Fortsetzung gehört zur vorigen Zeile."), wrap=940, color=dim)
            self._colour(item, "text_dim")
            self.ascii_lines = dpg.add_child_window(width=-1, height=300, border=True, horizontal_scrollbar=True)
            with dpg.group(horizontal=True):
                dpg.add_text(t("Kopfzeile"))
                self.ascii_header = dpg.add_input_int(width=110, min_value=-1, min_clamped=True, default_value=0,
                                                      callback=lambda: self._ascii_preview())
                self._tooltip(self.ascii_header, t("Zeilennummer der Signalnamen. 0 = automatisch erkennen, "
                                                   "-1 = keine Kopfzeile (Spaltennamen werden erzeugt)."))
                dpg.add_spacer(width=12)
                dpg.add_text(t("Einheitenzeile"))
                self.ascii_units = dpg.add_input_int(width=110, min_value=-1, min_clamped=True, default_value=0,
                                                     callback=lambda: self._ascii_preview())
                self._tooltip(self.ascii_units, t("0 = automatisch (Zeile direkt unter der Kopfzeile, falls sie "
                                                  "Einheiten enthält), -1 = keine."))
                dpg.add_spacer(width=12)
                dpg.add_text(t("Trennzeichen"))
                self.ascii_sep = dpg.add_combo(items=[t(n) for _k, n in self.ASCII_SEPS], width=140,
                                               default_value=t("Automatisch"), callback=lambda: self._ascii_preview())
                dpg.add_text(t("Dezimalzeichen"))
                self.ascii_decimal = dpg.add_combo(items=[t(n) for _k, n in self.ASCII_DECIMALS], width=120,
                                                   default_value=t("Automatisch"), callback=lambda: self._ascii_preview())
            self.ascii_result = dpg.add_text("", wrap=940)
            self.ascii_names = dpg.add_text("", wrap=940, color=dim)
            self._colour(self.ascii_names, "text_dim")
            self.ascii_template = dpg.add_checkbox(label=t("Als Vorlage für weitere ASCII-Dateien (asc, txt, dat ...) "
                                                           "verwenden"))
            self._tooltip(self.ascii_template, t("Neu geöffnete ASCII-Dateien (nicht CSV) werden zuerst mit diesen "
                                                 "Angaben gelesen; passt es nicht, wird automatisch erkannt."))
            self.ascii_status = dpg.add_text("", wrap=940)
            with dpg.group(horizontal=True):
                self.ascii_apply_btn = dpg.add_button(label=t("Übernehmen und einlesen"), callback=self._ascii_apply)
                dpg.add_button(label=t("Automatisch"), callback=self._ascii_reset)
                dpg.add_button(label=t("Schließen"), callback=lambda: dpg.configure_item("ascii_window", show=False))

    def _ascii_options(self) -> csv_reader.AsciiOptions:
        seps = {t(n): k for k, n in self.ASCII_SEPS}
        decimals = {t(n): k for k, n in self.ASCII_DECIMALS}
        return csv_reader.AsciiOptions(int(dpg.get_value(self.ascii_header) or 0), int(dpg.get_value(self.ascii_units) or 0),
                                       seps.get(dpg.get_value(self.ascii_sep), ""),
                                       decimals.get(dpg.get_value(self.ascii_decimal), ""))

    def _open_ascii_window(self, _sender, _app_data, path: str) -> None:
        self.ascii_path = path
        dataset = next((d for d in self.datasets if os.path.abspath(d.path) == os.path.abspath(path)), None)
        opts = csv_reader.AsciiOptions.from_dict(((dataset.extra.get("ascii") or {}).get("options")) if dataset else None)
        if dataset is None and self.settings.get("ascii_template") and not path.lower().endswith(".csv"):
            opts = csv_reader.AsciiOptions.from_dict(self.settings["ascii_template"])
        dpg.set_value(self.ascii_header, opts.header_line)
        dpg.set_value(self.ascii_units, opts.units_line)
        dpg.set_value(self.ascii_sep, t(dict(self.ASCII_SEPS).get(opts.sep, "Automatisch")))
        dpg.set_value(self.ascii_decimal, t(dict(self.ASCII_DECIMALS).get(opts.decimal, "Automatisch")))
        dpg.set_value(self.ascii_template, bool(self.settings.get("ascii_template")))
        dpg.set_value(self.ascii_title, t("ASCII-Import: {name}", name=Path(path).name))
        dpg.set_value(self.ascii_status, "")
        self._ascii_preview()
        width, height = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
        dpg.configure_item("ascii_window", show=True, pos=[max(0, (width - 980) // 2), max(0, (height - 700) // 2)])

    def _ascii_reset(self) -> None:
        for item in (self.ascii_header, self.ascii_units):
            dpg.set_value(item, 0)
        dpg.set_value(self.ascii_sep, t("Automatisch"))
        dpg.set_value(self.ascii_decimal, t("Automatisch"))
        self._ascii_preview()

    def _ascii_preview(self) -> None:
        if not self.ascii_path:
            return
        result = csv_reader.preview(self.ascii_path, self._ascii_options())
        self.ascii_last_preview = result
        dpg.delete_item(self.ascii_lines, children_only=True)
        heading, good, dim = (themes.color(self.mode, k) for k in ("heading", "ok", "text_dim"))
        span = result.header_span or (0, -1)
        for number, line in enumerate(result.lines, 1):
            text = line if len(line) <= 240 else line[:240] + " ..."
            mark, color = "   ", None
            if span[0] <= number <= span[1]:
                mark, color = "K> ", heading
            elif number == result.units_line:
                mark, color = "E> ", heading
            elif number == result.data_line:
                mark, color = "D> ", good
            elif csv_reader.MARKER.search(line):
                color = dim
            kwargs = {"color": color} if color else {}
            dpg.add_text(f"{mark}{number:>4} | {text}", parent=self.ascii_lines, **kwargs)
        if result.error:
            dpg.set_value(self.ascii_result, t("Nicht lesbar: {error}", error=result.error))
            dpg.configure_item(self.ascii_result, color=themes.color(self.mode, "error"))
            dpg.set_value(self.ascii_names, "")
            return
        sep = t(csv_reader._SEP_NAMES.get(result.sep, result.sep))
        head = (t("Kopfzeile: {lines}", lines=csv_reader._line_text(*result.header_span)) if result.header_span
                else t("ohne Kopfzeile"))
        parts = [head, t("Daten ab Zeile {line}", line=result.data_line), t("{count} Spalten", count=len(result.names)),
                 t("Trennzeichen: {sep}, Dezimalzeichen: {dec}", sep=sep, dec=result.decimal)]
        if result.removed:
            parts.append(t("{count} Zusatzinformation(en) entfernt", count=result.removed))
        dpg.set_value(self.ascii_result, "  |  ".join(parts))
        dpg.configure_item(self.ascii_result, color=themes.color(self.mode, "text"))
        shown = ", ".join(result.names[:40]) + (t(" ... und {count} weitere", count=len(result.names) - 40)
                                                 if len(result.names) > 40 else "")
        dpg.set_value(self.ascii_names, t("Signale: {names}", names=shown))

    def _ascii_apply(self) -> None:
        path = self.ascii_path
        if not path:
            return
        opts = self._ascii_options()
        if dpg.get_value(self.ascii_template) and not opts.automatic:
            self.settings["ascii_template"] = opts.to_dict()
        elif not dpg.get_value(self.ascii_template):
            self.settings.pop("ascii_template", None)
        self._save_settings()
        dataset = next((d for d in self.datasets if os.path.abspath(d.path) == os.path.abspath(path)), None)
        options = opts.to_dict() if not opts.automatic else None
        dpg.configure_item("ascii_window", show=False)
        if dataset is None:                 # noch nicht geöffnet (z. B. automatische Erkennung fehlgeschlagen)
            self.pending += 1
            self._message(t("Lade {count} Datei(en)...", count=self.pending))
            self.pool.submit(self._load_worker, os.path.abspath(path), None, options or {})
            return
        self._message(t("{name} wird neu eingelesen...", name=dataset.name))
        self.pool.submit(self._ascii_worker, dataset, options)

    def _ascii_worker(self, dataset: Dataset, options: dict | None) -> None:
        try:
            fresh = load_file(dataset.path, options) if options else load_file(dataset.path)
            self.results.put(("ascii", dataset, fresh, None))
        except Exception as exc:
            log_exception(f"ASCII neu einlesen: {dataset.path}", exc)
            self.results.put(("ascii", dataset, None, str(exc) if isinstance(exc, LoadError)
                              else f"{type(exc).__name__}: {exc}"))

    def _ascii_done(self, dataset: Dataset, fresh: Dataset | None, error: str | None) -> None:
        if dataset not in self.datasets:
            return
        if error:
            self._message(f"{dataset.name}: {error}", error=True)
            self._open_ascii_window(None, None, dataset.path)
            dpg.set_value(self.ascii_status, error)
            return
        count = self._replace_channels(dataset, fresh)
        self._layout_changed()
        self._refresh_channel_list()
        self._message(t("{name} neu eingelesen: {count} Signale.", name=dataset.name, count=count))

    def _replace_channels(self, dataset: Dataset, fresh: Dataset) -> int:
        """Neue Kanäle übernehmen; gleichnamige behalten ihr Objekt (Graphen, Farben, Grenzen bleiben)."""
        old = {c.name: c for c in dataset.channels if not c.formula}
        computed = [c for c in dataset.channels if c.formula]
        channels = []
        for channel in fresh.channels:
            keep = old.pop(channel.name, None)
            if keep is None:
                channels.append(channel)
                continue
            for name in ("unit", "x_name", "x_unit", "x", "y", "loader", "x_epoch", "ds_note"):
                setattr(keep, name, getattr(channel, name))
            keep._regression = None
            channels.append(keep)
        for gone in old.values():           # gibt es nicht mehr: aus den Graphen nehmen
            self.loading.pop(gone, None)
            self.layout.remove(gone)
        dataset.channels = channels + computed
        dataset.info, dataset.warnings = fresh.info, fresh.warnings
        dataset.extra.update({k: v for k, v in fresh.extra.items()})
        for channel in computed:            # berechnete Signale mit den neuen Werten bilden
            try:
                formula.add_or_replace(dataset, formula.compute(dataset, channel.name, channel.unit, channel.formula,
                                                                exclude=channel), channel)
            except LoadError as exc:
                self._message(f"{dataset.name}: {channel.name}: {exc}", error=True)
        return len(channels)

    # ---------------------------------------------------------------- Projekt
    def _build_project_window(self) -> None:
        dim = themes.color(self.mode, "text_dim")
        with dpg.window(tag="project_window", label=t("Projekt speichern"), show=False, width=760, height=430,
                        no_collapse=True, modal=True):
            item = dpg.add_text(t("Das Projekt hält alles für die Wiederverwendung: Messdateien mit Pfad, Datenbasen, "
                                  "ASCII-Struktur, berechnete Signale, Graphen mit Signalen, Farben, Achsen, Grenzen, "
                                  "Legenden und Bemerkungen, Matrix, Optionen sowie die Einstellungen für Report, "
                                  "Export, Vergleich und Downsampling."), wrap=720, color=dim)
            self._colour(item, "text_dim")
            dpg.add_text(t("Projektname"))
            self.proj_name = dpg.add_input_text(width=-1)
            dpg.add_text(t("Bemerkung"))
            self.proj_comment = dpg.add_input_text(width=-1, height=90, multiline=True)
            dpg.add_text(t("Projektdatei (*.mgproj)"))
            self.proj_path = dpg.add_input_text(width=-1)
            self.proj_summary = dpg.add_text("", wrap=720, color=dim)
            self._colour(self.proj_summary, "text_dim")
            self.proj_note = dpg.add_text("", wrap=720)
            with dpg.group(horizontal=True):
                self.proj_save_btn = dpg.add_button(label=t("Speichern"), width=120, callback=self._project_window_ok)
                dpg.add_button(label=t("Abbrechen"), width=120,
                               callback=lambda: dpg.configure_item("project_window", show=False))

    def _project_ui_state(self) -> dict:
        return {"filter": dpg.get_value(self.filter_input), "target": dpg.get_value(self.target_combo)}

    def project_dict(self, base_dir: str | None) -> dict:
        settings = dict(self.settings)
        settings["downsampling"] = downsample.config().to_dict()
        return project.build(self.session_dict(base_dir), settings, self.project_name, self.project_comment,
                             self._project_ui_state(), base_dir, self.project_created)

    def _open_project_window(self, *_args) -> None:
        name = self.project_name or (Path(self.project_path).stem if self.project_path else "")
        default = self.project_path or str(Path(self.settings.get("last_dir") or Path.home())
                                           / f"{name or 'MessGraph_Projekt'}{project.SUFFIX}")
        dpg.set_value(self.proj_name, name)
        dpg.set_value(self.proj_comment, self.project_comment)
        dpg.set_value(self.proj_path, default)
        info = project.summary(self.session_dict(None))
        dpg.set_value(self.proj_summary, t("Inhalt: {files} Dateien, {graphs} Graphen mit {signals} Signalen, "
                                           "{computed} berechnete Signale, {databases} Datenbasen", **info))
        dpg.set_value(self.proj_note, t("Vorhandene Datei wird überschrieben."))
        width, height = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
        dpg.configure_item("project_window", show=True, pos=[max(0, (width - 760) // 2), max(0, (height - 430) // 2)])

    def _project_window_ok(self, *_args) -> None:
        raw = dpg.get_value(self.proj_path).strip()
        path = os.path.abspath(os.path.expanduser(raw)) if raw else ""
        if not raw or os.path.isdir(path):
            dpg.set_value(self.proj_note, t("Bitte einen Dateinamen angeben."))
            return
        if not os.path.isdir(os.path.dirname(path)):
            dpg.set_value(self.proj_note, t("Ordner nicht gefunden: {path}", path=os.path.dirname(path)))
            return
        self.project_name = dpg.get_value(self.proj_name).strip()
        self.project_comment = dpg.get_value(self.proj_comment).strip()
        dpg.configure_item("project_window", show=False)
        self.save_project(path)

    def _save_project_now(self, *_args) -> None:
        """Projekt speichern: ins geöffnete Projekt, sonst wie "speichern unter"."""
        if self.project_path:
            self.save_project(self.project_path)
        else:
            self._open_project_window()

    def save_project(self, path: str) -> str | None:
        if not path.lower().endswith(project.SUFFIX):
            path += project.SUFFIX
        if not self.project_name:
            self.project_name = Path(path).stem
        try:
            data = self.project_dict(os.path.dirname(os.path.abspath(path)))
            written = project.write(path, data)
        except LoadError as exc:
            self._message(str(exc), error=True)
            return None
        self.project_path, self.project_created = written, data["created"]
        self._remember_project(written)
        self._update_title()
        self._message(t("Projekt gespeichert: {path}", path=written))
        return written

    def open_project(self, path: str) -> None:
        try:
            data = project.read(path)
        except LoadError as exc:
            self._message(str(exc), error=True)
            return
        base_dir = os.path.dirname(os.path.abspath(path))
        missing = project.relocate(data, base_dir)
        for key, value in (data.get("settings") or {}).items():
            if key in project.SETTINGS_KEYS:
                self.settings[key] = value
        if "downsampling" in (data.get("settings") or {}):
            downsample.set_config(downsample.DownsampleConfig.from_dict(data["settings"]["downsampling"]))
        self._save_settings()
        self.project_path = os.path.abspath(path)
        self.project_name = str(data.get("name") or Path(path).stem)
        self.project_comment = str(data.get("comment") or "")
        self.project_created = data.get("created")
        self._remember_project(self.project_path)
        self._update_title()
        ui = data.get("ui") or {}

        def finished():
            dpg.set_value(self.filter_input, str(ui.get("filter") or ""))
            self._refresh_channel_list()
            if ui.get("target") in self.layout.target_names():
                dpg.set_value(self.target_combo, ui["target"])
            text = t("Projekt geöffnet: {name}", name=self.project_name)
            if missing:
                text += " | " + t("Datenbasis nicht gefunden: {names}", names=", ".join(Path(p).name for p in missing))
            self._message(text, error=bool(missing))
        self.apply_session(data["session"], base_dir, done=finished)

    def close_project(self, *_args) -> None:
        """Alle Dateien schließen und mit einem leeren Projekt beginnen."""
        self.project_path, self.project_name, self.project_comment, self.project_created = None, "", "", None
        self._update_title()
        dpg.set_value(self.filter_input, "")
        self.apply_session({"files": [], "graphs": [], "options": {}}, None,
                           done=lambda: self._message(t("Projekt geschlossen.")))

    def _remember_project(self, path: str) -> None:
        recent = [p for p in self.settings.get("recent_projects", []) if os.path.abspath(p) != os.path.abspath(path)]
        self.settings["recent_projects"] = [os.path.abspath(path)] + recent[:7]
        self._save_settings()
        self._refresh_recent_projects()

    def _refresh_recent_projects(self) -> None:
        if not dpg.does_item_exist(self.recent_menu):
            return
        dpg.delete_item(self.recent_menu, children_only=True)
        recent = [p for p in self.settings.get("recent_projects", []) if os.path.isfile(p)]
        if not recent:
            dpg.add_menu_item(label=t("keine"), parent=self.recent_menu, enabled=False)
        for path in recent:
            dpg.add_menu_item(label=f"{Path(path).stem}   ({Path(path).parent})", parent=self.recent_menu,
                              callback=lambda _s, _a, p: self.open_project(p), user_data=path)

    def _update_title(self) -> None:
        title = f"MessGraph {__version__}" + (f" - {self.project_name}" if self.project_path else "")
        try:
            dpg.set_viewport_title(title)
        except (AttributeError, SystemError):
            pass

    # ---------------------------------------------------------------- Anordnung vorschlagen
    def _build_arrange_window(self) -> None:
        dim = themes.color(self.mode, "text_dim")
        self.arr_sources, self.arr_proposal = {}, None
        with dpg.window(tag="arrange_window", label=t("Anordnung vorschlagen"), show=False, width=980, height=700,
                        no_collapse=True):
            item = dpg.add_text(t("Die Signale werden nach Namen und Einheit gruppiert: gleiche Größe desselben Systems "
                                  "in einen Graphen (Ist- und Sollwerte gemeinsam), je System eine Zeile der Matrix "
                                  "(z. B. AC: Spannung, Strom, Leistung, Frequenz), Temperaturen und Zustände in "
                                  "eigenen Zeilen."), wrap=940, color=dim)
            self._colour(item, "text_dim")
            with dpg.group(horizontal=True):
                dpg.add_text(t("Signale"))
                self.arr_source = dpg.add_combo(items=[], width=360, callback=lambda: self._arrange_preview())
                dpg.add_text(t("Kurven je Graph höchstens"))
                self.arr_curves = dpg.add_input_int(default_value=8, width=90, min_value=1, max_value=32,
                                                    min_clamped=True, max_clamped=True,
                                                    callback=lambda: self._arrange_preview())
                dpg.add_text(t("Spalten höchstens"))
                self.arr_cols = dpg.add_input_int(default_value=4, width=90, min_value=1, max_value=8,
                                                  min_clamped=True, max_clamped=True,
                                                  callback=lambda: self._arrange_preview())
            self.arr_own = dpg.add_checkbox(label=t("Temperaturen und Zustände in eigenen Zeilen"), default_value=True,
                                            callback=lambda: self._arrange_preview())
            self.arr_summary = dpg.add_text("")
            self._colour(self.arr_summary, "heading")
            with dpg.group(horizontal=True):
                self.arr_preview = dpg.add_drawlist(width=560, height=380)
                self.arr_list = dpg.add_child_window(width=-1, height=380, border=True)
            self.arr_notes = dpg.add_text("", wrap=940, color=dim)
            self._colour(self.arr_notes, "text_dim")
            with dpg.group(horizontal=True):
                self.arr_apply_btn = dpg.add_button(label=t("Übernehmen"), width=120, callback=self._arrange_apply)
                self._tooltip(self.arr_apply_btn, t("Ersetzt die aktuelle Anordnung der Graphen."))
                dpg.add_button(label=t("Schließen"), width=120,
                               callback=lambda: dpg.configure_item("arrange_window", show=False))

    def _arrange_source_lists(self) -> dict:
        """Auswahl der Signale: angezeigte, Treffer der Suche, alle einer Datei."""
        sources = {}
        shown = list(dict.fromkeys(self.layout.signals()))
        if shown:
            sources[t("Angezeigte Signale ({count})", count=len(shown))] = shown
        words = dpg.get_value(self.filter_input).lower().split()
        if words:
            found = [c for d in self.datasets for c in d.channels if all(w in c.label.lower() for w in words)]
            if found:
                sources[t("Treffer der Suche \"{text}\" ({count})", text=" ".join(words), count=len(found))] = found
        for dataset in self.datasets:
            sources[t("Alle Signale: {name} ({count})", name=dataset.name, count=len(dataset.channels))] = \
                list(dataset.channels)
        return sources

    def _open_arrange_window(self) -> None:
        self.arr_sources = self._arrange_source_lists()
        if not self.arr_sources:
            self._message(t("Bitte zuerst Dateien öffnen."), error=True)
            return
        labels = list(self.arr_sources)
        dpg.configure_item(self.arr_source, items=labels)
        if dpg.get_value(self.arr_source) not in labels:
            dpg.set_value(self.arr_source, labels[0])
        self._arrange_preview()
        width, height = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
        dpg.configure_item("arrange_window", show=True, pos=[max(0, (width - 980) // 2), max(0, (height - 700) // 2)])

    def _arrange_preview(self) -> None:
        channels = self.arr_sources.get(dpg.get_value(self.arr_source), [])
        proposal = arrange.propose(channels, dpg.get_value(self.arr_curves), dpg.get_value(self.arr_cols),
                                   dpg.get_value(self.arr_own))
        self.arr_proposal = proposal
        dpg.delete_item(self.arr_preview, children_only=True)
        dpg.delete_item(self.arr_list, children_only=True)
        dpg.set_value(self.arr_notes, " ".join(proposal.notes))
        if not proposal.groups:
            dpg.set_value(self.arr_summary, t("Keine Signale für einen Vorschlag."))
            return
        rows, cols = proposal.matrix
        dpg.set_value(self.arr_summary, t("Vorschlag: Matrix {layout}, {count} Graphen mit {signals} Signalen",
                                          layout=layout_text(proposal), count=proposal.count,
                                          signals=sum(len(g.signals) for g in proposal.groups)))
        w, h, gap = 560.0, 380.0, 4.0
        row_h = min(70.0, (h - gap * (rows - 1)) / rows)
        col_w = (w - gap * (cols - 1)) / cols
        line, fill, text, dim = (themes.color(self.mode, k) for k in ("heading", "frame", "text", "text_dim"))
        index = 0
        for r, widths in enumerate(proposal.spans):
            col = 0
            for width in widths:
                group = proposal.groups[index]
                x0, y0 = col * (col_w + gap), r * (row_h + gap)
                x1 = x0 + width * col_w + (width - 1) * gap
                dpg.draw_rectangle((x0, y0), (x1, y0 + row_h), color=(*line, 255), fill=(*fill, 255),
                                   parent=self.arr_preview)
                limit = max(4, int((x1 - x0 - 10) / 7))
                title = group.title if len(group.title) <= limit else group.title[:limit - 2] + ".."
                dpg.draw_text((x0 + 5, y0 + 4), title, size=13, color=(*text, 255), parent=self.arr_preview)
                if row_h >= 30:
                    dpg.draw_text((x0 + 5, y0 + 20), t("{count} Kurven", count=len(group.signals)), size=12,
                                  color=(*dim, 255), parent=self.arr_preview)
                col += width
                index += 1
        current = None
        for number, group in enumerate(proposal.groups, 1):
            if group.row != current:
                current = group.row
                item = dpg.add_text(current, parent=self.arr_list)
                self._colour(item, "heading")
            names = ", ".join(c.name for c in group.signals)
            dpg.add_text(f"  {number}. {group.title}: {names}", wrap=380, parent=self.arr_list)

    def _arrange_apply(self) -> None:
        proposal = self.arr_proposal
        if not proposal or not proposal.groups:
            return
        dpg.configure_item("arrange_window", show=False)
        self.loading.clear()
        self.layout.slots = []
        self.layout.set_matrix(proposal.matrix, proposal.spans)
        for slot, group in zip(self.layout.slots, proposal.groups):
            slot.title = group.title
        for slot, group in zip(self.layout.slots, proposal.groups):
            for channel in group.signals:
                if channel.loaded:
                    self.layout.add(channel, self.layout.slots.index(slot))
                else:
                    self._request_add(channel, slot)       # MF4: wird erst geladen
        dpg.set_value(self.matrix_input, format_layout(self.layout.matrix, self.layout.spans))
        self._layout_changed()
        self._message(t("Anordnung übernommen: Matrix {layout}, {count} Graphen.", layout=layout_text(proposal),
                        count=proposal.count))

    # ---------------------------------------------------------------- Zeilen zusammenfassen
    def _build_rows_window(self) -> None:
        dim = themes.color(self.mode, "text_dim")
        self.rows_inputs, self.rows_matrix = [], None
        with dpg.window(tag="rows_window", label=t("Zeilen zusammenfassen"), show=False, width=640, height=560,
                        no_collapse=True):
            self.rows_title = dpg.add_text("")
            self._colour(self.rows_title, "heading")
            item = dpg.add_text(t("Je Zeile die Anzahl gleich breiter Graphen (3 = drei Graphen, 1 = ein Graph über die "
                                  "ganze Breite) oder die Breiten in Spalten mit + (2+1 = ein Graph über zwei Spalten "
                                  "und einer über eine)."), wrap=600, color=dim)
            self._colour(item, "text_dim")
            with dpg.group(horizontal=True):
                self.rows_area = dpg.add_child_window(width=230, height=360, border=False)
                with dpg.group():
                    dpg.add_text(t("Vorschau"))
                    self.rows_preview = dpg.add_drawlist(width=360, height=320)
            self.rows_status = dpg.add_text("", wrap=600)
            with dpg.group(horizontal=True):
                self.rows_apply_btn = dpg.add_button(label=t("Übernehmen"), width=120, callback=self._rows_apply)
                dpg.add_button(label=t("Alle Einzelgraphen"), callback=self._rows_reset)
                dpg.add_button(label=t("Schließen"), width=120,
                               callback=lambda: dpg.configure_item("rows_window", show=False))

    def _open_rows_window(self) -> None:
        try:
            matrix, spans = parse_layout(dpg.get_value(self.matrix_input))
        except ValueError:
            matrix, spans = self.layout.matrix, self.layout.spans
        if not matrix:
            self._message(t("Bitte zuerst eine Matrix festlegen, zum Beispiel 4*3."), error=True)
            return
        self.rows_matrix = matrix
        rows = spans or [[1] * matrix[1] for _ in range(matrix[0])]
        dpg.set_value(self.rows_title, t("Matrix {rows}*{cols}", rows=matrix[0], cols=matrix[1]))
        dpg.delete_item(self.rows_area, children_only=True)
        self.rows_inputs = []
        for number, widths in enumerate(rows, 1):
            with dpg.group(horizontal=True, parent=self.rows_area):
                dpg.add_text(t("Zeile {number}", number=number))
                field = dpg.add_input_text(default_value=format_row(widths), width=110,
                                           callback=lambda: self._rows_preview())
                self.rows_inputs.append(field)
        self._rows_preview()
        width, height = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
        dpg.configure_item("rows_window", show=True, pos=[max(0, (width - 640) // 2), max(0, (height - 560) // 2)])

    def _rows_spans(self):
        """(Breiten je Zeile, Fehlertext)."""
        cols = self.rows_matrix[1]
        spans = []
        for number, field in enumerate(self.rows_inputs, 1):
            try:
                spans.append(parse_row(dpg.get_value(field), cols))
            except ValueError as exc:
                return None, t("Zeile {number}: {error}", number=number, error=exc)
        return spans, ""

    def _rows_preview(self) -> None:
        dpg.delete_item(self.rows_preview, children_only=True)
        spans, error = self._rows_spans()
        dpg.set_value(self.rows_status, error)
        dpg.configure_item(self.rows_status, color=themes.color(self.mode, "error" if error else "text"))
        if spans is None:
            return
        rows, cols = self.rows_matrix
        w, h, gap = 360.0, 320.0, 4.0
        row_h = min(48.0, (h - gap * (rows - 1)) / rows)
        col_w = (w - gap * (cols - 1)) / cols
        line, fill, text = (themes.color(self.mode, k) for k in ("heading", "frame", "text"))
        number = 0
        for r, widths in enumerate(spans):
            col = 0
            for width in widths:
                number += 1
                x0, y0 = col * (col_w + gap), r * (row_h + gap)
                x1 = x0 + width * col_w + (width - 1) * gap
                dpg.draw_rectangle((x0, y0), (x1, y0 + row_h), color=(*line, 255), fill=(*fill, 255),
                                   parent=self.rows_preview)
                dpg.draw_text((x0 + 6, y0 + row_h / 2 - 7), t("Graph {number}", number=number), size=13,
                              color=(*text, 255), parent=self.rows_preview)
                col += width
        if not error:
            dpg.set_value(self.rows_status, t("{count} Graphen", count=number))

    def _rows_reset(self) -> None:
        for field in self.rows_inputs:
            dpg.set_value(field, str(self.rows_matrix[1]))
        self._rows_preview()

    def _rows_apply(self) -> None:
        spans, error = self._rows_spans()
        if spans is None:
            dpg.set_value(self.rows_status, error)
            return
        dpg.configure_item("rows_window", show=False)
        self._apply_layout(self.rows_matrix, spans)

    # ---------------------------------------------------------------- Einstellungen übertragen
    def _build_transfer_window(self) -> None:
        dim = themes.color(self.mode, "text_dim")
        self.tr_source, self.tr_data, self.tr_rows, self.tr_targets = None, None, [], {}
        with dpg.window(tag="transfer_window", label=t("Einstellungen übertragen"), show=False, width=900,
                        height=560, no_collapse=True):
            item = dpg.add_text(t("Überträgt Graphen mit Signalen, Farben, Achsen, Grenzen, Legenden und Bemerkungen, "
                                  "berechnete Signale, Datenbasen und ASCII-Struktur von den gespeicherten Dateien auf "
                                  "andere Dateien gleicher Struktur. Signale werden über den Namen zugeordnet."),
                                wrap=860, color=dim)
            self._colour(item, "text_dim")
            with dpg.group(horizontal=True):
                dpg.add_text(t("Quelle"))
                self.tr_source_text = dpg.add_text("")
                self._colour(self.tr_source_text, "heading")
            with dpg.group(horizontal=True):
                dpg.add_button(label=t("Aktueller Stand"), callback=lambda: self._tr_set_source(None))
                dpg.add_button(label=t("Ansicht laden..."), callback=lambda: self._later(lambda: self._show_file_browser(
                    "session", lambda paths: self._tr_set_source(paths[0]), "Ansicht laden")))
                dpg.add_button(label=t("Projekt öffnen..."), callback=lambda: self._later(lambda: self._show_file_browser(
                    "project", lambda paths: self._tr_set_source(paths[0]), "Projekt öffnen")))
            dpg.add_separator()
            dpg.add_text(t("Zuordnung: gespeicherte Datei -> Zieldatei"))
            self.tr_table_area = dpg.add_child_window(width=-1, height=250, border=True)
            self.tr_keep = dpg.add_checkbox(label=t("Bisherige Dateien zusätzlich geöffnet lassen (ohne Graphen)"))
            self.tr_settings = dpg.add_checkbox(label=t("Einstellungen des Projekts übernehmen (Report, Export, "
                                                        "Vergleich, Downsampling ...)"), default_value=True)
            self.tr_status = dpg.add_text("", wrap=860)
            with dpg.group(horizontal=True):
                self.tr_apply_btn = dpg.add_button(label=t("Übertragen"), width=120, callback=self._tr_apply)
                dpg.add_button(label=t("Schließen"), width=120,
                               callback=lambda: dpg.configure_item("transfer_window", show=False))

    def _open_transfer_window(self, source: str | None = None) -> None:
        width, height = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
        dpg.configure_item("transfer_window", show=True, pos=[max(0, (width - 900) // 2), max(0, (height - 560) // 2)])
        self._tr_set_source(source)

    def _tr_set_source(self, path: str | None) -> None:
        """Quelle: None = aktueller Stand, sonst .mgraph oder .mgproj."""
        dpg.set_value(self.tr_status, "")
        settings = None
        try:
            if path is None:
                data = self.session_dict(None)
            elif path.lower().endswith(project.SUFFIX):
                proj = project.read(path)
                project.relocate(proj, os.path.dirname(os.path.abspath(path)))
                data, settings = proj["session"], proj.get("settings") or {}
            else:
                data = sessions.read_session(path)
        except LoadError as exc:
            dpg.set_value(self.tr_status, str(exc))
            dpg.configure_item(self.tr_status, color=themes.color(self.mode, "error"))
            return
        self.tr_source, self.tr_data, self.tr_settings_data = path, data, settings
        dpg.configure_item(self.tr_settings, show=settings is not None)
        dpg.set_value(self.tr_source_text, t("Aktueller Stand") if path is None else Path(path).name)
        self.tr_targets = {}
        files = self._tr_sources()
        others = [d for d in self.datasets if os.path.abspath(d.path) not in files]
        computed = {os.path.abspath(e.get("path", "")): {c.get("name") for c in e.get("computed", [])}
                    for e in data.get("files", [])}
        for saved in files:        # Vorschlag: ähnlichste geöffnete andere Datei (gleiche Signalnamen)
            source_ds = next((d for d in self.datasets if os.path.abspath(d.path) == saved), None)
            wanted = set(self._tr_signal_names(saved))
            best, score = None, 0.0
            for candidate in others:
                if source_ds is not None:
                    value = compare.similarity(source_ds, candidate)
                else:
                    names = {c.name for c in candidate.channels} | computed.get(saved, set())
                    value = len(wanted & names) / max(1, len(wanted))
                if value > score:
                    best, score = candidate, value
            if best is not None and score >= 0.5:
                self.tr_targets[saved] = os.path.abspath(best.path)
        self._tr_refresh()

    def _tr_sources(self) -> list[str]:
        """Gespeicherte Dateien mit etwas Übertragbarem (angezeigte Signale, Berechnungen, Datenbasen, ASCII)."""
        shown = {os.path.abspath(sig.get("file", "")) for g in self.tr_data.get("graphs", []) for sig in g.get("signals", [])}
        out = []
        for entry in self.tr_data.get("files", []):
            path = os.path.abspath(entry.get("path", ""))
            if path in shown or entry.get("computed") or entry.get("databases") or entry.get("ascii"):
                out.append(path)
        return out

    def _tr_signal_names(self, saved: str) -> list[str]:
        names = [sig.get("name") for g in self.tr_data.get("graphs", []) for sig in g.get("signals", [])
                 if os.path.abspath(sig.get("file", "")) == saved]
        return list(dict.fromkeys(n for n in names if n))

    def _tr_choices(self) -> dict:
        choices = {t("unverändert (gespeicherte Datei)"): None}
        for dataset in sorted(self.datasets, key=lambda d: d.name.lower()):
            label = dataset.name
            if label in choices:
                label = f"{dataset.name} ({Path(dataset.path).parent.name})"
            choices[label] = os.path.abspath(dataset.path)
        choices[t("Andere Datei wählen...")] = "browse"
        return choices

    def _tr_refresh(self) -> None:
        dpg.delete_item(self.tr_table_area, children_only=True)
        self.tr_rows = []
        sources = self._tr_sources() if self.tr_data else []
        if not sources:
            dpg.add_text(t("Die Quelle enthält keine Dateien mit Graphen, Berechnungen oder Datenbasen."),
                         parent=self.tr_table_area)
            return
        choices = self._tr_choices()
        labels = list(choices)
        computed = {os.path.abspath(e.get("path", "")): {c.get("name") for c in e.get("computed", [])}
                    for e in self.tr_data.get("files", [])}
        with dpg.table(header_row=True, parent=self.tr_table_area, resizable=True, borders_innerH=True,
                       borders_outerH=True, policy=dpg.mvTable_SizingStretchProp):
            dpg.add_table_column(label=t("Gespeicherte Datei"), init_width_or_weight=1.0)
            dpg.add_table_column(label=t("Zieldatei"), init_width_or_weight=1.3)
            dpg.add_table_column(label=t("Signale im Ziel"), init_width_or_weight=0.8)
            for saved in sources:
                target = self.tr_targets.get(saved)
                current = next((label for label, value in choices.items() if value == target and target), None)
                if current is None:
                    current = labels[0] if not target else t("Andere Datei wählen...")
                with dpg.table_row():
                    dpg.add_text(Path(saved).name)
                    self._tooltip(dpg.last_item(), saved)
                    with dpg.group():
                        combo = dpg.add_combo(items=labels, default_value=current, width=-1,
                                              callback=self._tr_choice_changed, user_data=saved)
                        if target and current == t("Andere Datei wählen..."):
                            dpg.add_text(target, wrap=380)
                    wanted = self._tr_signal_names(saved)
                    dataset = next((d for d in self.datasets if os.path.abspath(d.path) == (target or saved)), None)
                    if not wanted:
                        info = t("keine angezeigten Signale")
                    elif dataset is None:
                        info = t("{count} Signale, Prüfung beim Übertragen", count=len(wanted))
                    else:
                        names = {c.name for c in dataset.channels} | computed.get(saved, set())
                        found = sum(1 for n in wanted if n in names)
                        info = t("{found} von {count} vorhanden", found=found, count=len(wanted))
                    dpg.add_text(info)
                self.tr_rows.append((saved, combo))

    def _tr_choice_changed(self, _sender, value, saved: str) -> None:
        target = self._tr_choices().get(value)
        if target == "browse":
            def chosen(paths, saved=saved):
                self.tr_targets[saved] = os.path.abspath(paths[0])
                self._tr_refresh()
            self._later(lambda: self._show_file_browser("data", chosen, "Zieldatei wählen"))
            return
        if target is None:
            self.tr_targets.pop(saved, None)
        else:
            self.tr_targets[saved] = target
        self._tr_refresh()

    def _tr_apply(self) -> None:
        if not self.tr_data:
            return
        mapping = {saved: target for saved, target in self.tr_targets.items() if target and target != saved}
        if not mapping:
            dpg.set_value(self.tr_status, t("Bitte mindestens einer gespeicherten Datei eine andere Zieldatei zuordnen."))
            dpg.configure_item(self.tr_status, color=themes.color(self.mode, "error"))
            return
        keep = [d.path for d in self.datasets] if dpg.get_value(self.tr_keep) else []
        data = sessions.remap(self.tr_data, mapping, keep)
        if self.tr_settings_data and dpg.get_value(self.tr_settings):
            for key, value in self.tr_settings_data.items():
                if key in project.SETTINGS_KEYS:
                    self.settings[key] = value
            self._save_settings()
        base_dir = os.path.dirname(os.path.abspath(self.tr_source)) if self.tr_source else None
        pairs = ", ".join(f"{Path(a).name} -> {Path(b).name}" for a, b in mapping.items())
        dpg.configure_item("transfer_window", show=False)
        self.project_path, self.project_created = None, None     # neue Auswertung: nicht ins alte Projekt speichern
        self._update_title()

        def finished():
            problems = getattr(self, "last_session_problems", [])
            text = t("Einstellungen übertragen: {pairs}", pairs=pairs)
            self._message(text + (" | " + " | ".join(problems) if problems else ""), error=bool(problems))
        self.apply_session(data, base_dir, done=finished)

    def _build_db_window(self) -> None:
        heading = themes.color(self.mode, "heading")
        dim = themes.color(self.mode, "text_dim")
        with dpg.window(tag="db_window", label=t("Datenbasen"), show=False, width=820, height=600, no_collapse=True):
            self.db_title = dpg.add_text("")
            self._colour(self.db_title, "heading")
            item = dpg.add_text(t("Eine Aufzeichnung kann mehrere Datenbasen brauchen: DBC, ARXML, A2L und CDD lassen "
                                  "sich beliebig kombinieren. Angewendet wird bei Bedarf; Dateien ohne passende "
                                  "Botschaft oder Messgröße werden nur gemeldet."), wrap=780, color=dim)
            self._colour(item, "text_dim")
            with dpg.group(horizontal=True):
                self.db_add_btn = dpg.add_button(label=t("Datenbasen hinzufügen..."), callback=lambda: self._show_file_browser(
                    "databases", self._db_add_files, "Datenbasen wählen (dbc, arxml, a2l, cdd)"))
                self._tooltip(self.db_add_btn, t("Mehrere Dateien auf einmal wählen; sie werden nach der Endung einsortiert."))
                dpg.add_button(label=t("Alle entfernen"), callback=self._db_clear)
            dpg.add_separator()
            item = dpg.add_text(t("DBC und ARXML (AUTOSAR): CAN-Botschaften der Aufzeichnung in Signale dekodieren"),
                                color=heading)
            self._colour(item, "heading")
            self.db_dbc_area = dpg.add_group()
            dpg.add_spacer(height=4)
            dpg.add_separator()
            item = dpg.add_text(t("A2L: Einheiten und Umrechnungen für gleichnamige Kanäle"), color=heading)
            self._colour(item, "heading")
            self.db_a2l_area = dpg.add_group()
            self.db_a2l_convert = dpg.add_checkbox(label=t("Rohwerte mit der A2L-Umrechnung in physikalische Werte umrechnen"),
                                                   callback=self._db_convert_toggled)
            self._tooltip(self.db_a2l_convert, t("Nur einschalten, wenn die MF4 Rohwerte (Steuergeräte-Ganzzahlen) enthält.\n"
                                                 "Bereits physikalische Werte würden sonst doppelt umgerechnet."))
            dpg.add_spacer(height=4)
            dpg.add_separator()
            item = dpg.add_text(t("CDD: Diagnosebeschreibung"), color=heading)
            self._colour(item, "heading")
            self.db_cdd_area = dpg.add_group()
            self.db_cdd_text = self.db_cdd_area
            item = dpg.add_text(t("Die CDD wird zugeordnet und gemerkt. Die Auswertung von Diagnosedaten "
                                  "ist noch nicht eingebaut."), wrap=780, color=dim)
            self._colour(item, "text_dim")
            dpg.add_spacer(height=4)
            dpg.add_separator()
            self.db_auto = dpg.add_checkbox(label=t("Neue Busaufzeichnungen (MF4/MDF/BLF) automatisch mit den zuletzt "
                                                    "verwendeten Datenbasen dekodieren"),
                                            default_value=bool(self.settings.get("databases_auto")),
                                            callback=self._db_auto_toggled)
            self.db_status = dpg.add_text("", wrap=780)
            with dpg.group(horizontal=True):
                self.db_last_button = dpg.add_button(label=t("Zuletzt verwendete übernehmen"), callback=self._db_take_last)
                dpg.add_button(label=t("Anwenden"), width=110, callback=self._db_apply)
                dpg.add_button(label=t("Schließen"), width=110, callback=lambda: dpg.configure_item("db_window", show=False))

    def _open_db_window(self, _sender, _app_data, dataset: Dataset) -> None:
        self.db_dataset = dataset
        self.db_config = DatabaseConfig.from_dict(dataset.extra.get("config", DatabaseConfig()).to_dict())
        dpg.set_value(self.db_title, t("Datenbasen für {name}", name=dataset.name))
        dpg.set_value(self.db_status, t("Bitte Busrohdaten-Aufzeichnung mit einer DBC dekodieren.")
                      if dataset.extra.get("bus_raw") and self.db_config.empty else "")
        dpg.configure_item(self.db_status, color=themes.color(self.mode, "text"))
        dpg.configure_item(self.db_last_button, show=bool(self.settings.get("databases_last")))
        self._db_refresh_view()
        width, height = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
        dpg.configure_item("db_window", show=True, pos=[max(0, (width - 820) // 2), max(0, (height - 600) // 2)])

    def _db_refresh_view(self) -> None:
        config = self.db_config
        for area in (self.db_dbc_area, self.db_a2l_area, self.db_cdd_area):
            dpg.delete_item(area, children_only=True)
        if not config.bus:
            dpg.add_text(t("Keine DBC oder ARXML zugeordnet."), parent=self.db_dbc_area)
        choices = [t(c) for c in CAN_CHOICES]
        for kind in ("dbc", "arxml"):
            for index, (path, channel) in enumerate(getattr(config, kind)):
                with dpg.group(horizontal=True, parent=self.db_dbc_area):
                    dpg.add_text(f"{kind.upper():<5}")
                    dpg.add_combo(items=choices, default_value=choices[channel] if channel < len(choices) else choices[0],
                                  width=130, callback=self._db_channel_changed, user_data=(kind, index))
                    dpg.add_button(label=t("Entfernen"), small=True, callback=self._db_remove, user_data=(kind, index))
                    dpg.add_text(Path(path).name)
                    self._tooltip(dpg.last_item(), path)
        for kind, area in (("a2l", self.db_a2l_area), ("cdd", self.db_cdd_area)):
            paths = getattr(config, kind)
            if not paths:
                dpg.add_text(t("keine"), parent=area)
            for index, path in enumerate(paths):
                with dpg.group(horizontal=True, parent=area):
                    dpg.add_button(label=t("Entfernen"), small=True, callback=self._db_remove, user_data=(kind, index))
                    dpg.add_text(Path(path).name)
                    self._tooltip(dpg.last_item(), path)
        dpg.set_value(self.db_a2l_convert, config.a2l_convert)

    def _db_add_files(self, paths) -> None:
        unknown = self.db_config.add(list(paths))
        self._db_refresh_view()
        if unknown:
            dpg.set_value(self.db_status, t("Nicht als Datenbasis erkannt (nur dbc, arxml, a2l, cdd): {names}",
                                            names=", ".join(Path(p).name for p in unknown)))
            dpg.configure_item(self.db_status, color=themes.color(self.mode, "error"))

    _db_add_dbc = _db_add_files

    def _db_remove(self, _sender, _app_data, target) -> None:
        kind, index = target
        self.db_config.remove(kind, index)
        self._db_refresh_view()

    def _db_remove_dbc(self, _sender, _app_data, index: int) -> None:
        self._db_remove(None, None, ("dbc", index))

    def _db_clear(self) -> None:
        self.db_config = DatabaseConfig(a2l_convert=self.db_config.a2l_convert)
        self._db_refresh_view()

    def _db_channel_changed(self, _sender, value, target) -> None:
        kind, index = target if isinstance(target, tuple) else ("dbc", target)
        entries = getattr(self.db_config, kind)
        path, _ = entries[index]
        entries[index] = (path, [t(c) for c in CAN_CHOICES].index(value))

    def _db_set(self, kind: str, paths) -> None:
        """Ohne Pfade: alle Dateien dieser Art entfernen, sonst hinzufügen."""
        if not paths:
            setattr(self.db_config, kind, [])
            self._db_refresh_view()
        else:
            self._db_add_files(paths)

    def _db_convert_toggled(self, _sender, value) -> None:
        self.db_config.a2l_convert = value

    def _db_auto_toggled(self, _sender, value) -> None:
        self.settings["databases_auto"] = bool(value)
        self._save_settings()

    def _db_take_last(self) -> None:
        self.db_config = DatabaseConfig.from_dict(self.settings.get("databases_last"))
        self._db_refresh_view()

    def _db_apply(self) -> None:
        dataset = self.db_dataset
        if dataset is None or dataset not in self.datasets:
            dpg.configure_item("db_window", show=False)
            return
        dpg.set_value(self.db_status, t("Datenbasen werden angewendet..."))
        self._db_start(dataset, DatabaseConfig.from_dict(self.db_config.to_dict()))

    def _db_start(self, dataset: Dataset, config: DatabaseConfig) -> None:
        shown = {c.name for c in self.layout.signals() if c in dataset.channels}
        self.pool.submit(self._db_worker, dataset, config, shown, self._start_job(dataset.name))

    def _db_auto_apply(self, dataset: Dataset) -> bool:
        """Bei Bedarf: neue Busaufzeichnung gleich mit den zuletzt verwendeten Datenbasen dekodieren."""
        last = DatabaseConfig.from_dict(self.settings.get("databases_last"))
        if not self.settings.get("databases_auto") or not last.bus or dataset.extra.get("config") is not None:
            return False
        missing = [Path(p).name for _k, p in last.files() if not os.path.isfile(p)]
        if missing:
            self._message(t("Automatisch dekodieren nicht möglich, Datenbasis fehlt: {names}", names=", ".join(missing)),
                          error=True)
            return False
        self._message(t("{name}: Datenbasen werden automatisch angewendet ({files})...", name=dataset.name,
                        files=", ".join(Path(p).name for _k, p in last.files())))
        self._db_start(dataset, last)
        return True

    def _db_worker(self, dataset: Dataset, config: DatabaseConfig, shown: set, job=None) -> None:
        try:
            with progress.track(job):
                progress.busy(t("Datenbasen anwenden..."))
                result = apply_databases(dataset, config, shown, _mf4_entries, dataset.extra.get("start"))
            self.results.put(("db", dataset, config, result, None))
        except progress.Cancelled:
            self.results.put(("db", dataset, config, None, CANCELLED))
        except Exception as exc:
            log_exception(f"Datenbasen: {dataset.path}", exc)
            text = str(exc) if isinstance(exc, LoadError) else f"{type(exc).__name__}: {exc}"
            self.results.put(("db", dataset, config, None, text))

    def _db_done(self, dataset: Dataset, config: DatabaseConfig, result, error) -> None:
        if error == CANCELLED:
            dpg.set_value(self.db_status, t("Abgebrochen."))
            self._message(t("{name}: Laden abgebrochen.", name=dataset.name))
            return
        if error:
            if dataset in self.datasets and not dpg.is_item_shown("db_window"):   # z. B. automatisch angewendet
                self._open_db_window(None, None, dataset)
                self.db_config = DatabaseConfig.from_dict(config.to_dict())
                self._db_refresh_view()
            dpg.set_value(self.db_status, f"{error}  ({t('Details: {path}', path=LOG_FILE)})")
            dpg.configure_item(self.db_status, color=themes.color(self.mode, "error"))
            self._message(f"{dataset.name}: {error}", error=True)
            return
        channels, info, warnings, opened = result
        if dataset not in self.datasets:  # inzwischen geschlossen
            for item in opened:
                item.close()
            return
        old = set(dataset.channels)
        by_name = {c.name: c for c in channels}
        dropped = 0
        for slot in self.layout.slots:
            kept = []
            for channel in slot.signals:
                if channel not in old:
                    kept.append(channel)
                    continue
                new = by_name.get(channel.name) or next((c for c in channels if channel.name in c.aliases), None)
                color = slot.colors.pop(channel, None)
                was_right = channel in slot.right
                slot.right.discard(channel)
                if new is not None and new.loaded:
                    kept.append(new)
                    if color:
                        slot.colors[new] = color
                    if was_right:
                        slot.right.add(new)
                else:
                    dropped += 1
            slot.signals = kept
        if not self.layout.matrix:
            self.layout.slots = [s for s in self.layout.slots if s.signals]
        for channel in old:
            self.loading.pop(channel, None)
        install_databases(dataset, config, result)
        if not config.empty:
            self.settings["databases_last"] = config.to_dict()
            self._save_settings()
        dpg.configure_item("db_window", show=False)
        self._layout_changed()
        self._refresh_channel_list()
        note = " " + t("{count} angezeigte Signale gibt es nicht mehr.", count=dropped) if dropped else ""
        self._message(t("{name}: Datenbasen angewendet, {count} Signale.", name=dataset.name, count=len(channels))
                      + " " + " ".join(info) + note)

    def _close_dataset(self, _sender, _app_data, dataset: Dataset) -> None:
        if self.file_switch and self.file_switch[0] is dataset:
            self.file_switch = None           # Wechsel auf diese Datei hinfällig
        for channel in dataset.channels:
            self.layout.remove(channel)
            self.loading.pop(channel, None)
        self.datasets.remove(dataset)
        dataset.close()
        self._layout_changed()
        self._refresh_channel_list()
        self._message(t("{name} geschlossen.", name=dataset.name))

    # ---------------------------------------------------------------- Hinweise je Datei (dynamisch)
    HINT_NAMES = 12

    def _file_hints(self, dataset: Dataset, words: list[str]) -> list[str]:
        """Hinweise aus dem aktuellen Stand der Datei: nur Namen, die es dort wirklich gibt und die keine
        Zahlenwerte liefern; bei aktiver Signalsuche nur die passenden. Busrohdaten nennen die vorhandenen
        Rahmenkanäle und berücksichtigen, ob schon über Datenbasen dekodiert wurde."""
        hints = list(dataset.warnings)

        def matching(names):
            return [n for n in names if all(w in n.lower() for w in words)] if words else list(names)

        def listed(names):
            extra = len(names) - self.HINT_NAMES
            return ", ".join(names[:self.HINT_NAMES]) + (" " + t("(+{count} weitere)", count=extra) if extra > 0 else "")
        empty = matching(dataset.extra.get("no_values") or [])
        if empty:
            hints.append(t("Ohne Zahlenwerte, nicht angeboten: {names}", names=listed(empty)))
        if dataset.extra.get("bus_raw"):
            raw = [c for c in dataset.channels if c.name.startswith(BUS_FRAME_PREFIXES)]
            groups = matching(list(dict.fromkeys(c.name.split(".")[0] for c in raw)))
            base = set(dataset.extra.get("base") or [])
            decoded = [c for c in dataset.channels if c not in base and not c.formula]
            if groups and decoded:
                hints.append(t("Busrohdaten {names}: {count} Signale über die Datenbasen dekodiert.",
                               names=listed(groups), count=len(decoded)))
            elif groups:
                hints.append(t("Busrohdaten ohne physikalische Werte: {names}. Signale entstehen erst durch "
                               "Dekodierung mit DBC oder ARXML: Schaltfläche \"Datenbasen...\".", names=listed(groups)))
        return hints

    # ---------------------------------------------------------------- Signalliste
    def _refresh_channel_list(self) -> None:
        dpg.delete_item(self.channel_area, children_only=True)
        self.checkboxes = {}
        self.file_headers = []
        self.limiter_hints = {}
        self.coloured_text = [(i, r) for i, r in self.coloured_text if dpg.does_item_exist(i)]
        self._update_file_combo()
        if dpg.does_item_exist(getattr(self, "same_name_box", 0) or 0):
            dpg.configure_item(self.same_name_box, show=len(self.datasets) > 1)   # nur bei mehreren Dateien
        if bool(self.datasets) != getattr(self, "plots_have_files", bool(self.datasets)):
            self._rebuild_plots()         # erste Datei geladen oder letzte geschlossen: Plotbereich neu aufbauen
        if not self.datasets:
            dpg.add_text(t("Noch keine Datei geladen."), parent=self.channel_area, wrap=0)
            return
        words = dpg.get_value(self.filter_input).lower().split()
        self._multi_refresh(words)
        for dataset in self.datasets:
            with dpg.collapsing_header(label=dataset.name, default_open=True, parent=self.channel_area) as header:
                self.file_headers.append(header)
                with dpg.group(horizontal=True):
                    dpg.add_button(label=t("Schließen"), small=True, callback=self._close_dataset, user_data=dataset)
                    if "mdf" in dataset.extra or "blf" in dataset.extra:
                        button = dpg.add_button(label=t("Datenbasen..."), small=True, callback=self._open_db_window,
                                                user_data=dataset)
                        self._tooltip(button, t("DBC und ARXML für diese BLF-Datei zuordnen (CAN-Signale dekodieren).")
                                      if "blf" in dataset.extra else
                                      t("DBC, ARXML, A2L und CDD für diese MF4/MDF-Datei zuordnen (auch mehrere)."))
                    if is_ascii(dataset.path):
                        button = dpg.add_button(label=t("ASCII-Import..."), small=True,
                                                callback=self._open_ascii_window, user_data=dataset.path)
                        self._tooltip(button, t("Kopfzeile, Einheitenzeile, Trenn- und Dezimalzeichen prüfen oder "
                                                "selbst festlegen; die Datei wird damit neu eingelesen."))
                    button = dpg.add_button(label=t("Berechnen..."), small=True, callback=self._open_calc_window,
                                            user_data=dataset)
                    self._tooltip(button, t("Neues Signal aus Signalen dieser Datei berechnen (+ - * /), "
                                            "z. B. Strom * Spannung."))
                info = dpg.add_text(t("Erkennung (Maus hierher)"), color=themes.color(self.mode, "text_dim"))
                self._colour(info, "text_dim")
                self._tooltip(info, "\n".join(str(i18n.retranslate(line)) for line in dataset.info))
                if self.limiter and self.limiter.rules_for(dataset.name):
                    item = dpg.add_text(self._limiter_text(dataset), wrap=0)
                    self._colour(item, "heading")
                    self.limiter_hints[dataset.path] = item
                for hint in self._file_hints(dataset, words):
                    item = dpg.add_text(t("Hinweis: {text}", text=hint), wrap=0, color=themes.color(self.mode, "text_dim"))
                    self._colour(item, "text_dim")
                matches = [c for c in dataset.channels if all(w in self._search_text(c) for w in words)]
                for channel in matches[:MAX_LISTED]:
                    if not channel.plottable:                 # Text/VLSD, 1 Wert oder leer: grau, nicht darstellbar
                        self._add_unplottable(channel)
                        continue
                    box = dpg.add_checkbox(label=("= " + channel.label) if channel.formula else channel.label,
                                           callback=self._on_channel, user_data=channel,
                                           default_value=self.layout.contains(channel) or channel in self.loading)
                    if channel.formula and getattr(channel, "fourier", None):
                        self._fourier_tooltip(box, channel)
                    elif channel.formula:
                        self._tooltip(box, t("Berechnet: {formula}", formula=channel.formula)
                                      + (f"\n{channel.note}" if channel.note else ""))
                    elif channel.value_text:
                        states = list(channel.value_text.items())
                        lines = [f"{fmt(v)} = {txt}" for v, txt in states[:20]]
                        if len(states) > 20:
                            lines.append(t("... {count} weitere", count=len(states) - 20))
                        self._tooltip(box, t("Wert->Text-Umrechnung (Rohwerte im Graphen):") + "\n" + "\n".join(lines))
                    with dpg.drag_payload(parent=box, drag_data=channel, payload_type=PAYLOAD):
                        dpg.add_text(t("{label}  ->  in einen Graphen ziehen", label=channel.label))
                    self.checkboxes[channel] = box
                if len(matches) > MAX_LISTED:
                    dpg.add_text(t("{count} weitere Treffer: Filter verfeinern.", count=len(matches) - MAX_LISTED), wrap=0)
                if not matches:
                    dpg.add_text(t("Kein Treffer."))

    @staticmethod
    def _search_text(channel: Channel) -> str:
        """Suchtext eines Kanals: Anzeigename mit Einheit und frühere Namen (z. B. Kanal (G714))."""
        text = channel.label
        if channel.aliases:
            text += " " + " ".join(channel.aliases)
        return text.lower()

    UNPLOTTABLE = {"text": "Text/Byte-Feld (VLSD), nicht darstellbar",
                   "const": "nur 1 Wert (Konstante), nicht darstellbar",
                   "empty": "keine Messwerte"}

    def _add_unplottable(self, channel: Channel) -> None:
        reason = t(self.UNPLOTTABLE.get(channel.kind, "nicht darstellbar"))
        with dpg.group(horizontal=True):
            item = dpg.add_text(f"    {channel.label}  ({reason})", color=themes.color(self.mode, "text_dim"))
            self._colour(item, "text_dim")
            tip = t("{name}: {reason}. Der Kanal wird nicht in Graphen gezeichnet.", name=channel.name, reason=reason)
            if channel.kind == "const":
                button = dpg.add_button(label=t("Wert"), small=True, callback=lambda s, a, u: self._show_constant(u),
                                        user_data=channel)
                self._tooltip(button, t("Den einen Messwert lesen und anzeigen."))
            self._tooltip(item, tip)

    def _constant_text(self, channel: Channel) -> str:
        result = channel.loader() if channel.loader else (channel.x, channel.y, channel.unit)
        x, y, unit = result[:3]
        table = (result[3] if len(result) > 3 else {}).get("value_text") or channel.value_text or {}
        y = np.asarray(y, dtype=np.float64).ravel()
        if y.size == 0:
            return t("{name}: keine Messwerte", name=channel.name)
        value = float(y[0])
        text = fmt(value, unit or channel.unit)
        label = table.get(value)
        x0 = np.asarray(x, dtype=np.float64).ravel()
        at = f" (t = {fmt(float(x0[0]), channel.x_unit)})" if x0.size else ""
        return t("{name}: Konstante {value}{text}{at}", name=channel.name, value=text,
                 text=f" = {label}" if label else "", at=at)

    def _show_constant(self, channel: Channel) -> None:
        try:
            self._message(self._constant_text(channel))
        except Exception as exc:
            self._message(t("{name}: Wert nicht lesbar ({error})", name=channel.name, error=exc), error=True)

    # ---------------------------------------------------------------- Signal über alle Dateien
    def _multi_candidates(self, words: list[str]) -> dict[str, list[Channel]]:
        """Suchtreffer, die in mindestens zwei Dateien vorkommen: {Signalname: [Kanal je Datei]}."""
        found: dict[str, list[Channel]] = {}
        for dataset in self.datasets:
            seen = set()
            for channel in dataset.channels:
                if channel.name in seen or not all(w in channel.label.lower() for w in words):
                    continue
                seen.add(channel.name)
                found.setdefault(channel.name, []).append(channel)
        return {name: chans for name, chans in found.items() if len(chans) >= 2}

    def _multi_refresh(self, words: list[str] | None = None) -> None:
        if words is None:
            words = dpg.get_value(self.filter_input).lower().split()
        self.multi_candidates = self._multi_candidates(words) if words and len(self.datasets) >= 2 else {}
        names = sorted(self.multi_candidates, key=str.lower)
        dpg.configure_item(self.multi_area, show=bool(names))
        if not names:
            return
        dpg.set_value(self.multi_title, t("Treffer in mehreren Dateien: {count} Signal(e)", count=len(names)))
        dpg.configure_item(self.multi_combo, items=names)
        if dpg.get_value(self.multi_combo) not in names:
            dpg.set_value(self.multi_combo, names[0])
        self._multi_update_info()

    def _multi_selected(self) -> list[Channel]:
        return list(getattr(self, "multi_candidates", {}).get(dpg.get_value(self.multi_combo), []))

    def _multi_update_info(self) -> None:
        channels = self._multi_selected()
        shown = sum(1 for c in channels if self.layout.contains(c))
        dpg.set_value(self.multi_info, t("in {count} von {total} Dateien, {shown} davon angezeigt",
                                         count=len(channels), total=len(self.datasets), shown=shown))

    def _multi_plot(self, _sender=None, _app_data=None, mode: str = "shared") -> None:
        channels = self._multi_selected()
        if not channels:
            return
        if mode == "single":
            for channel in channels:
                if not self.layout.contains(channel):
                    self._request_add(channel, self._new_slot())
            self._message(t("{name}: {count} Dateien in Einzelgraphen.", name=channels[0].name, count=len(channels)))
        else:
            target = self._selected_target()
            slot = self.layout.slots[target] if target is not None else self._new_slot()
            for channel in channels:
                if channel not in slot.signals:
                    self._request_add(channel, slot)
            self._message(t("{name}: {count} Dateien in einem gemeinsamen Graphen.", name=channels[0].name,
                            count=len(channels)))
        self._layout_changed()
        self._sync_checkboxes()
        self._multi_update_info()

    def _new_slot(self) -> GraphSlot:
        """Leerer Graph: ohne Matrix ein neuer, mit Matrix der erste leere (sonst der am wenigsten belegte)."""
        if not self.layout.matrix:
            slot = GraphSlot()
            self.layout.slots.append(slot)
            return slot
        empty = [s for s in self.layout.slots if not s.signals]
        return empty[0] if empty else min(self.layout.slots, key=lambda s: len(s.signals))

    def _multi_remove(self) -> None:
        channels = self._multi_selected()
        for channel in channels:
            self.loading.pop(channel, None)
            self.layout.remove(channel)
        self._layout_changed()
        self._sync_checkboxes()
        self._multi_update_info()

    def _on_same_name(self, _sender, value) -> None:
        self.settings["same_name"] = bool(value)
        self._save_settings()

    def _same_name_peers(self, channel: Channel) -> list[Channel]:
        """Gleichnamige Signale der anderen offenen Dateien (Option "Gleichnamige Signale aller Dateien")."""
        if not (len(self.datasets) > 1 and dpg.does_item_exist(getattr(self, "same_name_box", 0) or 0)
                and dpg.get_value(self.same_name_box)):
            return []
        return [c for d in self.datasets if d.path != channel.source for c in d.channels if c.name == channel.name]

    def _on_channel(self, _sender, checked, channel: Channel) -> None:
        peers = self._same_name_peers(channel)
        if peers:                                      # alle gleichnamigen Signale zugleich
            group = [channel] + peers
            if not checked:
                for c in group:
                    self.loading.pop(c, None)
                    self.layout.remove(c)
                self._layout_changed()
                self._sync_checkboxes()
                self._message(t("{name}: aus {count} Dateien entfernt.", name=channel.name, count=len(group)))
                return
            target = self._selected_target()
            slot = self.layout.slots[target] if target is not None and target < len(self.layout.slots) \
                else self._new_slot()
            for c in group:
                if c not in slot.signals:
                    self._request_add(c, slot)
            self._layout_changed()
            self._sync_checkboxes()
            self._message(t("{name}: {count} Dateien in einem gemeinsamen Graphen.", name=channel.name,
                            count=len(group)))
            return
        if not checked:
            self.loading.pop(channel, None)
            self.layout.remove(channel)  # Häkchen entfernen: aus allen Graphen
            self._layout_changed()
            return
        self._request_add(channel, self._selected_target())

    def _request_add(self, channel: Channel, target) -> None:
        """target: Index, GraphSlot oder None (automatisch). MF4-Kanäle werden erst geladen."""
        if not channel.plottable:                      # z. B. per Ziehen oder gespeicherter Ansicht
            if channel.kind == "const":
                self._show_constant(channel)
            else:
                self._message(t("{name}: {reason}", name=channel.name,
                                reason=t(self.UNPLOTTABLE.get(channel.kind, "nicht darstellbar"))), error=True)
            self._sync_checkboxes()
            return
        if channel.loaded:
            self._add_signal(channel, target)
            return
        first_request = channel not in self.loading
        self.loading[channel] = target
        self._sync_checkboxes()
        if first_request:
            self._message(t("Lade {name}...", name=channel.name))
            job = self._start_job(channel.name) if downsample.applies(channel.source) else None
            self.pool.submit(self._channel_worker, channel, job)

    def _selected_target(self) -> int | None:
        value = dpg.get_value(self.target_combo)
        names = self.layout.target_names()
        return names.index(value) - 1 if value in names and value != names[0] else None

    def _add_signal(self, channel: Channel, target) -> None:
        if isinstance(target, GraphSlot):
            target = self.layout.slots.index(target) if target in self.layout.slots else None
        if not self.layout.add(channel, target):
            self._sync_checkboxes()
            self._message(t("{label} ist dort bereits vorhanden.", label=channel.label))
            return
        self._layout_changed()
        text = (t("{label} in Graph {graph}: {count} Werte.", label=channel.label, graph=target + 1, count=channel.y.size)
                if target is not None else t("{label}: {count} Werte.", label=channel.label, count=channel.y.size))
        note = f" ({channel.ds_note})" if channel.ds_note else ""
        self._message(f"{text}{note} {self.plot_note}".strip())

    def _sync_checkboxes(self) -> None:
        for channel, box in self.checkboxes.items():
            if dpg.does_item_exist(box):
                dpg.set_value(box, self.layout.contains(channel) or channel in self.loading)

    def _on_clear_signals(self) -> None:
        self.loading.clear()
        self.layout.clear()
        self._layout_changed()

    # ---------------------------------------------------------------- Drag and Drop
    def _on_drop(self, sender, channel, _user_data=None) -> None:
        """Ablage auf einem Graphen (Plot oder Achse) oder auf der freien Fläche daneben."""
        if not isinstance(channel, Channel) or not any(channel in d.channels for d in self.datasets):
            return
        slot = self.drop_targets.get(sender)
        if sender in self.right_axes and slot is not None:
            if channel in slot.signals:  # schon im Graphen: nur auf die rechte Achse legen
                self._set_axis(slot, channel, True)
                return
            slot.right.add(channel)
        self._request_add(channel, slot)

    # ---------------------------------------------------------------- Kontextmenü (rechte Maustaste)
    def _all_ui(self) -> list:
        """Graphen des Plotbereichs und, wenn offen, der Graph im Detailfenster (dasselbe GraphSlot-Objekt)."""
        return self.slot_ui + ([self.zoom_ui] if self.zoom_ui is not None else [])

    def _hovered_ui(self) -> SlotUI | None:
        for ui in reversed(self._all_ui()):          # Detailfenster liegt oben
            if dpg.does_item_exist(ui.plot) and dpg.is_item_hovered(ui.plot):
                return ui
        return None

    def _hovered_slot(self) -> GraphSlot | None:
        ui = self._hovered_ui()
        return ui.slot if ui is not None else None

    def _on_right_down(self, *_args) -> None:
        hovered = self._hovered_ui()
        slot = hovered.slot if hovered is not None else None
        self.ctx_from_zoom = hovered is not None and hovered is self.zoom_ui
        self.right_down = (slot, dpg.get_mouse_pos(local=False)) if slot is not None else None
        if slot is not None:              # Stelle im Graphen für ein neues Kommentarfeld
            try:
                self.ctx_plot_pos = tuple(float(v) for v in dpg.get_plot_mouse_pos())[:2]
            except Exception:
                self.ctx_plot_pos = None

    def _on_right_up(self, *_args) -> None:
        down, self.right_down = self.right_down, None
        if down is None:
            return
        slot, start = down
        pos = dpg.get_mouse_pos(local=False)
        if abs(pos[0] - start[0]) > CLICK_TOLERANCE or abs(pos[1] - start[1]) > CLICK_TOLERANCE:
            return  # mit rechter Taste gezogen: Bereichszoom
        if slot in self.layout.slots:
            if self._legend_hovered(slot):
                self._open_legend_menu(slot, pos)
            else:
                self._open_context_menu(slot, pos)

    def _ctx_log(self, axis: str, value: bool) -> None:
        """Achse des Graphen logarithmisch/dezimal; Werte <= 0 zeigt eine log. Achse nicht."""
        slot = getattr(self, "ctx_slot", None)
        if slot is None:
            return
        setattr(slot, f"log_{axis}", bool(value))
        self._layout_changed()
        if value and self._uses_time_axis(slot) and axis == "x":
            self._message(t("Mit Datum/Uhrzeit-Achse bleibt X dezimal (Zeitachse)."))
        elif value:
            self._message(t("{axis}-Achse logarithmisch: Werte <= 0 werden nicht gezeigt.", axis=axis.upper()))

    def _open_context_menu(self, slot: GraphSlot, pos) -> None:
        menu = "ctx_menu"
        dpg.delete_item(menu, children_only=True)
        self.ctx_slot = slot
        index = self.layout.slots.index(slot)
        heading = themes.color(self.mode, "heading")
        dpg.add_text(slot.display_name(index), parent=menu, color=heading)
        dpg.add_separator(parent=menu)
        dpg.add_text(t("Name des Graphen"), parent=menu, color=heading)
        with dpg.group(horizontal=True, parent=menu):
            self.ctx_title = dpg.add_input_text(default_value=slot.title, hint=t("Graph {number}", number=index + 1), width=MENU_WIDTH - 110,
                                                on_enter=True, callback=self._ctx_rename)
            dpg.add_button(label=t("Übernehmen"), callback=self._ctx_rename)
        self._add_comment_section(slot, menu, heading)
        if slot.signals:
            dpg.add_separator(parent=menu)
            dpg.add_text(t("Achsen: dezimal oder logarithmisch"), parent=menu, color=heading)
            with dpg.group(horizontal=True, parent=menu):
                self.ctx_log_x = dpg.add_checkbox(label=t("X logarithmisch"), default_value=slot.log_x,
                                                  callback=lambda s, v: self._ctx_log("x", v))
                self.ctx_log_y = dpg.add_checkbox(label=t("Y logarithmisch"), default_value=slot.log_y,
                                                  callback=lambda s, v: self._ctx_log("y", v))
            dpg.add_separator(parent=menu)
            dpg.add_text(t("Legende (auch per Rechtsklick auf die Legende)"), parent=menu, color=heading)
            self._add_legend_choices(slot, menu)
        if any(s.signals for s in self.layout.slots):
            dpg.add_separator(parent=menu)
            dpg.add_text(t("Drucken und Export"), parent=menu, color=heading)
            if slot.signals:
                from_zoom = self.ctx_from_zoom
                self.ctx_print_one = dpg.add_selectable(label=t("Diesen Graphen drucken / exportieren..."), parent=menu,
                                                        callback=lambda: self._open_export("one", slot, from_zoom))
            self.ctx_print_all = dpg.add_selectable(label=t("Alle Graphen drucken / exportieren..."), parent=menu,
                                                    callback=lambda: self._open_export("all"))
            self.ctx_report = dpg.add_selectable(label=t("Report als PDF erstellen..."), parent=menu,
                                                 callback=lambda: self._open_export("report"))
        dpg.add_separator(parent=menu)
        dpg.add_text(t("Signal hinzufügen"), parent=menu, color=heading)
        if self.datasets:
            self.ctx_filter = dpg.add_input_text(hint=t("Signal suchen"), width=MENU_WIDTH, parent=menu,
                                                 callback=lambda: self._fill_context_list())
            self.ctx_list = dpg.add_child_window(width=MENU_WIDTH, height=200, border=True, parent=menu)
            self._fill_context_list()
        else:
            dpg.add_text(t("Zuerst eine Datei öffnen."), parent=menu)
        if slot.signals:
            dpg.add_separator(parent=menu)
            dpg.add_text(t("Signal entfernen"), parent=menu, color=heading)
            for number, channel in enumerate(slot.signals):
                item = dpg.add_selectable(label=t("Entfernen: {label}", label=channel.label), parent=menu,
                                          callback=self._ctx_remove, user_data=channel)
                if number == 0:
                    self.ctx_remove_first = item
            if len(slot.signals) > 1:
                dpg.add_selectable(label=t("Alle Signale dieses Graphen entfernen"), parent=menu,
                                   callback=self._ctx_remove, user_data=None)
            dpg.add_separator(parent=menu)
            dpg.add_text(t("Signalfarben (Klick auf das Farbfeld)"), parent=menu, color=heading)
            for position, channel in enumerate(slot.signals):
                item = dpg.add_color_edit(default_value=(*self._signal_color(slot, channel, position), 255), parent=menu,
                                          label=channel.label, no_inputs=True, no_alpha=True,
                                          callback=self._ctx_color, user_data=channel)
                if position == 0:
                    self.ctx_color_first = item
            if slot.colors:
                dpg.add_selectable(label=t("Standardfarben wiederherstellen"), parent=menu, callback=self._ctx_default_colors)
            dpg.add_separator(parent=menu)
            dpg.add_text(t("Rechte Y-Achse (sekundär)"), parent=menu, color=heading)
            for position, channel in enumerate(slot.signals):
                item = dpg.add_checkbox(label=channel.label, default_value=channel in slot.right, parent=menu,
                                        callback=self._ctx_axis, user_data=channel)
                if position == 0:
                    self.ctx_axis_first = item
        dpg.add_separator(parent=menu)
        dpg.add_selectable(label=t("Schließen"), parent=menu, callback=self._close_context_menu)
        x = max(0, min(int(pos[0]), dpg.get_viewport_client_width() - MENU_WIDTH - 30))
        y = max(0, min(int(pos[1]), dpg.get_viewport_client_height() - 420))
        dpg.configure_item(menu, pos=[x, y], show=True)

    def _fill_context_list(self) -> None:
        dpg.delete_item(self.ctx_list, children_only=True)
        words = dpg.get_value(self.ctx_filter).lower().split()
        multi_file = len(self.datasets) > 1
        shown = total = 0
        for dataset in self.datasets:
            for channel in dataset.channels:
                if channel in self.ctx_slot.signals:
                    continue
                text = f"{channel.label} - {dataset.name}" if multi_file else channel.label
                if not all(w in text.lower() for w in words):
                    continue
                total += 1
                if shown < MENU_LIST_MAX:
                    dpg.add_selectable(label=text, parent=self.ctx_list, callback=self._ctx_add, user_data=channel)
                    shown += 1
        if total > shown:
            dpg.add_text(t("{count} weitere Treffer: Suche verfeinern.", count=total - shown), parent=self.ctx_list)
        if total == 0:
            dpg.add_text(t("Kein passendes Signal."), parent=self.ctx_list)

    def _signal_color(self, slot: GraphSlot, channel: Channel, position: int) -> tuple:
        """Eigene Farbe des Signals in diesem Graphen, sonst die Standardfarbe seiner Position."""
        return tuple(slot.colors.get(channel) or themes.series_color(self.mode, position))

    def _theme_for(self, slot: GraphSlot, channel: Channel, position: int):
        color = slot.colors.get(channel)
        if not color:
            return self._series_theme(position)
        key = ("eigen", tuple(color))
        if key not in self.series_themes:
            self.series_themes[key] = themes.create_series_theme(tuple(color))
        return self.series_themes[key]

    # ---------------------------------------------------------------- Kommentarfelder (Rechtsklick)
    def _add_comment_section(self, slot: GraphSlot, menu, heading) -> None:
        dpg.add_separator(parent=menu)
        dpg.add_text(t("Kommentar an der Klickstelle"), parent=menu, color=heading)
        self.ctx_comment = dpg.add_input_text(hint=t("Text (mehrzeilig möglich)"), multiline=True, width=MENU_WIDTH,
                                              height=54, parent=menu)
        self.ctx_comment_add = dpg.add_button(label=t("Kommentar einfügen"), parent=menu, callback=self._ctx_add_comment)
        self.ctx_comment_edits = []
        for number, (_x, _y, text) in enumerate(slot.comments):
            with dpg.group(horizontal=True, parent=menu):
                edit = dpg.add_input_text(default_value=text, width=MENU_WIDTH - 196, on_enter=True,
                                          callback=self._ctx_edit_comment, user_data=number)
                self.ctx_comment_edits.append(edit)
                dpg.add_button(label=t("Übernehmen"), small=True, callback=self._ctx_edit_comment, user_data=number)
                button = dpg.add_button(label=t("Hierher"), small=True, callback=self._ctx_move_comment, user_data=number)
                self._tooltip(button, t("Kommentar an die Stelle des Rechtsklicks verschieben."))
                dpg.add_button(label=t("Löschen"), small=True, callback=self._ctx_delete_comment, user_data=number)

    def _comment_base(self, ui: SlotUI | None) -> float:
        """X-Versatz der Kommentare: mit Datumsachse die Startzeit des ersten Signals (wie die Kurven)."""
        if ui is None or not ui.slot.signals:
            return 0.0
        return float(self._offset(ui, ui.slot.signals[0]) or 0.0)

    def _ui_for(self, slot: GraphSlot) -> SlotUI | None:
        hovered = self._hovered_ui()
        if hovered is not None and hovered.slot is slot:
            return hovered
        return next((ui for ui in self._all_ui() if ui.slot is slot), None)

    def _draw_slot_comments(self, slot: GraphSlot) -> None:
        for ui in self._all_ui():
            if ui.slot is slot:
                self._draw_comments(ui)

    def _click_point(self, slot: GraphSlot):
        pos = getattr(self, "ctx_plot_pos", None)
        if not pos or len(pos) < 2 or not all(np.isfinite(pos)):
            return None
        return pos[0] - self._comment_base(self._ui_for(slot)), pos[1]

    def _ctx_add_comment(self, *_args) -> None:
        slot = self.ctx_slot
        text = dpg.get_value(self.ctx_comment).strip()
        point = self._click_point(slot)
        self._close_context_menu()
        if slot not in self.layout.slots or not text:
            return
        if point is None:
            self._message(t("Kommentar: keine Stelle im Graphen erkannt."), error=True)
            return
        slot.comments.append([point[0], point[1], text])
        self._draw_slot_comments(slot)
        index = self.layout.slots.index(slot)
        self._message(t("Kommentar in {name} eingefügt.", name=slot.display_name(index)))

    def _ctx_edit_comment(self, sender, _app_data, number: int) -> None:
        slot = self.ctx_slot
        if slot not in self.layout.slots or not 0 <= number < len(slot.comments):
            return
        text = dpg.get_value(self.ctx_comment_edits[number]).strip()
        self._close_context_menu()
        if not text:
            del slot.comments[number]          # leer übernommen: Kommentar entfernen
        else:
            slot.comments[number][2] = text
        self._draw_slot_comments(slot)

    def _ctx_move_comment(self, _sender, _app_data, number: int) -> None:
        slot = self.ctx_slot
        point = self._click_point(slot)
        self._close_context_menu()
        if slot in self.layout.slots and 0 <= number < len(slot.comments) and point is not None:
            slot.comments[number][:2] = list(point)
            self._draw_slot_comments(slot)

    def _ctx_delete_comment(self, _sender, _app_data, number: int) -> None:
        slot = self.ctx_slot
        self._close_context_menu()
        if slot in self.layout.slots and 0 <= number < len(slot.comments):
            del slot.comments[number]
            self._draw_slot_comments(slot)
            self._message(t("Kommentar gelöscht."))

    # Kommentar mit der linken Maustaste verschieben: Treffer über den Kasten in Pixeln (Maße wie die Anmerkung)
    COMMENT_OFFSET = (14, -14)

    def _px_per_unit(self, ui: SlotUI):
        """Pixel je Achseneinheit im Plotbereich (Ränder für Titel und Achsen aus der Schriftgröße geschätzt)."""
        try:
            w, h = (float(v) for v in dpg.get_item_rect_size(ui.plot))
            x0, x1 = (float(v) for v in dpg.get_axis_limits(ui.x_axis))
            y0, y1 = (float(v) for v in dpg.get_axis_limits(ui.y_axis))
        except Exception:
            return None
        font = float(self.graph_font_size)
        inner_w = w - font * 4.2 - (font * 4.2 if ui.y2_axis is not None else font * 0.8)
        inner_h = h - font * 1.8 - font * 2.8
        if inner_w < 20 or inner_h < 20 or x1 <= x0 or y1 <= y0:
            return None
        return inner_w / (x1 - x0), inner_h / (y1 - y0)

    def _comment_at(self, ui: SlotUI, mouse) -> int | None:
        """Index des Kommentars unter der Maus (oberster zuerst) oder None."""
        scale = self._px_per_unit(ui)
        if scale is None or not ui.slot.comments:
            return None
        base, font = self._comment_base(ui), float(self.graph_font_size)
        ox, oy = self.COMMENT_OFFSET
        for index in range(len(ui.slot.comments) - 1, -1, -1):
            x, y, text = ui.slot.comments[index]
            lines = str(text).splitlines() or [""]
            tw, th = max(len(line) for line in lines) * font * 0.6 + 12, len(lines) * font * 1.3 + 8
            dx = (mouse[0] - (x + base)) * scale[0]               # Pixel rechts vom Ankerpunkt
            dy = (y - mouse[1]) * scale[1]                         # Pixel unterhalb des Ankerpunkts
            if -8 <= dx <= ox + tw + 8 and oy - th - 8 <= dy <= 8:
                return index
        return None

    def _plot_mouse(self):
        try:
            pos = tuple(float(v) for v in dpg.get_plot_mouse_pos())[:2]
        except Exception:
            return None
        return pos if len(pos) == 2 and all(np.isfinite(pos)) else None

    def _on_left_down(self, *_args) -> None:
        ui = self._hovered_ui()
        mouse = self._plot_mouse() if ui is not None else None
        if mouse is None:
            return
        index = self._comment_at(ui, mouse)
        if index is None:
            return
        x, y, _text = ui.slot.comments[index]
        axes = [a for a in (ui.x_axis, ui.y_axis, ui.y2_axis) if a is not None]
        limits = {a: tuple(float(v) for v in dpg.get_axis_limits(a)) for a in axes}
        for axis, (lo, hi) in limits.items():          # Graph festhalten: Ziehen verschiebt sonst den Ausschnitt
            dpg.set_axis_limits(axis, lo, hi)
        self.comment_drag = {"ui": ui, "index": index, "grab": (x + self._comment_base(ui) - mouse[0], y - mouse[1]),
                             "axes": axes, "moved": False}

    def _poll_comment_drag(self) -> None:
        drag = getattr(self, "comment_drag", None)
        if drag is None:
            self._poll_comment_hover()
            return
        ui, index = drag["ui"], drag["index"]
        alive = ui in self._all_ui() and index < len(ui.slot.comments)
        if alive and dpg.is_mouse_button_down(dpg.mvMouseButton_Left):
            mouse = self._plot_mouse()
            if mouse is not None:
                x = mouse[0] + drag["grab"][0] - self._comment_base(ui)
                y = mouse[1] + drag["grab"][1]
                if [x, y] != ui.slot.comments[index][:2]:
                    ui.slot.comments[index][:2] = [x, y]
                    drag["moved"] = True
                    if index < len(ui.comment_items) and dpg.does_item_exist(ui.comment_items[index]):
                        dpg.configure_item(ui.comment_items[index], default_value=(x + self._comment_base(ui), y))
            return
        for axis in drag["axes"]:                       # losgelassen: Achsen wieder frei
            if dpg.does_item_exist(axis):
                dpg.set_axis_limits_auto(axis)
        self.comment_drag = None
        if alive and drag["moved"]:
            self._draw_slot_comments(ui.slot)          # auch die andere Darstellung desselben Graphen
            self._message(t("Kommentar verschoben."))

    def _poll_comment_hover(self) -> None:
        """Kommentar unter der Maus hervorheben (zeigt, dass er sich greifen lässt)."""
        hovered = None
        ui = self._hovered_ui() if any(u.slot.comments for u in self._all_ui()) else None
        if ui is not None:
            mouse = self._plot_mouse()
            if ui is not None and mouse is not None:
                index = self._comment_at(ui, mouse)
                if index is not None and index < len(ui.comment_items):
                    hovered = ui.comment_items[index]
        previous = getattr(self, "comment_hover", None)
        if hovered == previous:
            return
        for item, role in ((previous, "heading"), (hovered, "ok")):
            if item is not None and dpg.does_item_exist(item):
                dpg.configure_item(item, color=(*themes.color(self.mode, role), 230))
        self.comment_hover = hovered

    def _draw_comments(self, ui: SlotUI | None) -> None:
        """Kommentarfelder als Anmerkungen im Plot (Text in einem Kasten, an der Stelle verankert)."""
        if ui is None or not dpg.does_item_exist(ui.plot):
            return
        for item in ui.comment_items:
            if dpg.does_item_exist(item):
                dpg.delete_item(item)
        ui.comment_items = []
        base = self._comment_base(ui)
        color = (*themes.color(self.mode, "heading"), 230)
        for x, y, text in ui.slot.comments:
            ui.comment_items.append(dpg.add_plot_annotation(label=text, default_value=(x + base, y), offset=self.COMMENT_OFFSET,
                                                            color=color, clamped=True, parent=ui.plot))

    def _ctx_rename(self, *_args) -> None:
        slot = self.ctx_slot
        title = dpg.get_value(self.ctx_title).strip()
        self._close_context_menu()
        if slot in self.layout.slots and title != slot.title:
            slot.title = title
            self._layout_changed()
            index = self.layout.slots.index(slot)
            self._message(t("Graph {graph} heißt jetzt \"{title}\".", graph=index + 1, title=title) if title
                          else t("Graph {graph}: Standardname.", graph=index + 1))

    def _ctx_color(self, _sender, value, channel: Channel) -> None:
        """Farbe sofort übernehmen; das Menü bleibt für weitere Änderungen offen."""
        slot = self.ctx_slot
        if slot not in self.layout.slots:
            return
        rgb = [float(v) for v in list(value)[:3]]
        if all(v <= 1.0 for v in rgb):  # Dear PyGui liefert im Callback 0..1, get_value 0..255
            rgb = [v * 255 for v in rgb]
        slot.colors[channel] = tuple(int(round(min(max(v, 0), 255))) for v in rgb)
        for ui in self._all_ui():
            if ui.slot is slot and channel in ui.series:
                dpg.bind_item_theme(ui.series[channel], self._theme_for(slot, channel, ui.colors[channel]))
                if channel in ui.reg_series:
                    dpg.bind_item_theme(ui.reg_series[channel], self._theme_for(slot, channel, ui.colors[channel]))

    def _spec_regressions(self, ui: SlotUI) -> list:
        """Für Druck, Export und Report: (x0, y0, x1, y1, Farbe, rechte Achse, Kennung) je Signal."""
        if not self.reg_on:
            return []
        out = []
        for position, channel in enumerate(ui.slot.signals):
            if channel in ui.series and not self._series_active(ui, channel):
                continue                                   # wie im Graphen: über die Legende ausgeblendet
            extent = self._reg_extent(ui, channel) if channel in ui.colors else None
            if extent is None:
                continue
            x0, x1, m, b = extent
            rgb = tuple(ui.slot.colors.get(channel) or themes.series_color(themes.LIGHT, position))   # wie die Kurve
            out.append((x0, m * x0 + b, x1, m * x1 + b, rgb,
                        channel in ui.slot.right and ui.y2_axis is not None, f"s{position}"))
        return out

    def _ctx_axis(self, _sender, on_right, channel: Channel) -> None:
        slot = self.ctx_slot
        self._close_context_menu()
        if slot in self.layout.slots:
            self._set_axis(slot, channel, bool(on_right))

    def _set_axis(self, slot: GraphSlot, channel: Channel, on_right: bool) -> None:
        """Signal in diesem Graphen auf die rechte (sekundäre) oder linke Y-Achse legen."""
        if on_right:
            slot.right.add(channel)
        else:
            slot.right.discard(channel)
        self._rebuild_plots()
        self._message(t("{label} auf der rechten Y-Achse.", label=channel.label) if on_right
                      else t("{label} auf der linken Y-Achse.", label=channel.label))

    def _ctx_default_colors(self, *_args) -> None:
        slot = self.ctx_slot
        self._close_context_menu()
        if slot in self.layout.slots:
            slot.colors.clear()
            self._apply_mode()
            self._message(t("Standardfarben wiederhergestellt."))

    def _close_context_menu(self, *_args) -> None:
        dpg.configure_item("ctx_menu", show=False)

    def _ctx_add(self, _sender, _app_data, channel: Channel) -> None:
        slot = self.ctx_slot
        self._close_context_menu()
        if slot in self.layout.slots:
            self._request_add(channel, slot)

    def _ctx_remove(self, _sender, _app_data, channel: Channel | None) -> None:
        slot = self.ctx_slot
        self._close_context_menu()
        if slot not in self.layout.slots:
            return
        index = self.layout.slots.index(slot)
        if channel is None:
            self.layout.clear_slot(index)
            slot.colors.clear()
            text = t("Alle Signale aus Graph {graph} entfernt.", graph=index + 1)
        else:
            self.layout.remove_from(index, channel)
            text = t("{label} aus Graph {graph} entfernt.", label=channel.label, graph=index + 1)
        self._layout_changed()
        self._message(text)

    # ---------------------------------------------------------------- Bedienelemente
    def _on_matrix(self) -> None:
        try:
            matrix, spans = parse_layout(dpg.get_value(self.matrix_input))
        except ValueError as exc:
            self._message(str(exc), error=True)
            return
        self._apply_layout(matrix, spans)

    def _apply_layout(self, matrix, spans) -> None:
        self.layout.set_matrix(matrix, spans)
        dpg.set_value(self.matrix_input, format_layout(self.layout.matrix, self.layout.spans))
        self._layout_changed()
        if not matrix:
            self._message(t("Graphen untereinander."))
        elif self.layout.spans:
            self._message(t("Matrix {rows}*{cols} mit zusammengefassten Bereichen: {count} Graphen.",
                            rows=matrix[0], cols=matrix[1], count=len(self.layout.slots)))
        else:
            self._message(t("Matrix {rows}*{cols}.", rows=matrix[0], cols=matrix[1]))

    def _on_link(self, _sender, value) -> None:
        self.link_x = value
        self._rebuild_plots()

    def _plot_area_height(self) -> int:
        return -(self.table_h + SPLIT + 12) if self.cross_on else -1

    def _on_cross_toggle(self, _sender, value) -> None:
        self.cross_on = value
        if dpg.does_item_exist(getattr(self, "zoom_cross", 0) or 0):
            dpg.set_value(self.zoom_cross, value)
            self._zoom_heights()
        dpg.configure_item(self.table_area, show=value)
        dpg.configure_item(self.split_table, show=value)
        dpg.configure_item(self.plot_area, height=self._plot_area_height())
        self.last_height = None
        if value:
            self._init_cross_positions()
            self._markers_into_view()
        for ui in self._all_ui():
            for line in ui.v_lines:
                dpg.configure_item(line, show=value and not ui.fourier)   # Marker nur am Grundsignal
            for items in ui.limit_series.values():  # Grenzlinien gehören zu den Markern
                for item in items:
                    dpg.configure_item(item, show=value)
        self._sync_lines_to_state()
        self._update_measurements()

    def _on_cross_sync(self, _sender, value) -> None:
        self.cross_sync = value
        if dpg.does_item_exist(getattr(self, "zoom_sync", 0) or 0):
            dpg.set_value(self.zoom_sync, value)
        if value and self._all_ui() and self.cross_on:
            for kind in (False, True):
                first = next((u.slot.cross for u in self._all_ui()
                              if u.time_axis == kind and u.slot.cross[0] is not None), None)
                for ui in self._all_ui():
                    if first and ui.time_axis == kind:
                        ui.slot.cross = list(first)
            self._sync_lines_to_state()
            self._update_measurements()

    def _on_date_axis(self, _sender, value) -> None:
        self.date_axis = value
        self.settings["date_axis"] = value
        self._save_settings()
        for slot in self.layout.slots:  # Positionen gelten nur für die bisherige Achsenart
            slot.cross = [None, None]
        self._rebuild_plots()
        if value and not any(ui.time_axis for ui in self.slot_ui) and self.slot_ui:
            self._message(t("Keines der angezeigten Signale hat eine Startzeit: Die Achse bleibt in Sekunden."))

    def _on_theme(self, _sender, value) -> None:
        value = {t(mode): mode for mode in themes.PALETTE}.get(value, value)  # Anzeige ist übersetzt
        self.mode = value
        self.settings["theme"] = value
        self._save_settings()
        self._apply_mode()

    def _apply_mode(self) -> None:
        dpg.bind_theme(self.global_themes[self.mode])
        for item in (self.split_left, self.split_table):
            dpg.bind_item_theme(item, self.splitter_themes[self.mode])
        for item, role in self.coloured_text:
            if dpg.does_item_exist(item):
                dpg.configure_item(item, color=themes.color(self.mode, role))
        for ui in self._all_ui():
            for channel, series in ui.series.items():
                dpg.bind_item_theme(series, self._theme_for(ui.slot, channel, ui.colors[channel]))
            for channel, item in ui.reg_series.items():
                dpg.bind_item_theme(item, self._theme_for(ui.slot, channel, ui.colors[channel]))
            self._colour_lines(ui)
        self.alarm_plots = set()                      # Plothintergrund im neuen Schema neu binden
        self._update_alarms()

    def _colour_lines(self, ui: SlotUI) -> None:
        for k in (0, 1):
            col = (*themes.color(self.mode, "cross")[k], 255)
            dpg.configure_item(ui.v_lines[k], color=col)
        if ui.m3_line is not None:
            dpg.configure_item(ui.m3_line, color=(*themes.color(self.mode, "ok"), 255))

    def _series_theme(self, index: int):
        return self.series_themes[self.mode, index % len(themes.PALETTE[self.mode]["series"])]

    def _message(self, text: str, error: bool = False) -> None:
        dpg.set_value(self.status, text)
        dpg.configure_item(self.status, color=themes.color(self.mode, "error" if error else "text"))

    # ---------------------------------------------------------------- Graphen
    def _layout_changed(self) -> None:
        self._apply_limiter()
        names = self.layout.target_names()
        dpg.configure_item(self.target_combo, items=names)
        if dpg.get_value(self.target_combo) not in names:
            dpg.set_value(self.target_combo, names[0])
        self._sync_checkboxes()
        self._rebuild_plots()
        self._update_file_combo()
        if getattr(self, "multi_candidates", None) and dpg.does_item_exist(self.multi_info):
            self._multi_update_info()

    def _subplot_height(self, rows: int) -> int:
        """-1 füllt den Bereich; passt die Mindesthöhe nicht, rollt der Bereich."""
        available = dpg.get_viewport_client_height() - 168 - (self.table_h + SPLIT + 12 if self.cross_on else 0)
        needed = rows * MIN_PLOT_HEIGHT
        return -1 if needed <= available else needed

    def _uses_time_axis(self, slot: GraphSlot) -> bool:
        """Datumsachse nur, wenn alle Signale des Graphen eine Startzeit haben."""
        return self.date_axis and bool(slot.signals) and all(c.x_epoch is not None for c in slot.signals)

    @staticmethod
    def _offset(ui: SlotUI, channel: Channel) -> float:
        """Plot-X = Kanal-X + Versatz. Mit Datumsachse ist der Versatz die Startzeit des Kanals."""
        return channel.x_epoch if ui.time_axis else 0.0

    def _rebuild_plots(self) -> None:
        dpg.delete_item(self.plot_area, children_only=True)
        self.slot_ui = []
        self.drop_targets = {}
        self.right_axes = set()
        self.subplots = None
        self.row_subplots = []
        self.link_last, self.link_release, self.link_settle = {}, [], 4
        self.manual_link = False
        self.y_release = {}               # Y-Achse -> Bilder bis zur Freigabe (Rand wie im Report)
        self.comment_drag, self.comment_hover = None, None   # Kommentar wird gezogen / liegt unter der Maus
        self.plot_note = ""
        rows, cols = self.layout.grid()
        self.plots_have_files = bool(self.datasets)
        if not self.datasets:
            pass                          # keine Datei geladen: Plotbereich bleibt leer (auch bei gesetzter Matrix)
        elif rows == 0:
            dpg.add_text(t("Noch kein Signal ausgewählt. Links ein Signal anhaken oder hierher ziehen."),
                         parent=self.plot_area)
        else:
            self.last_height = self._subplot_height(rows)
            multi_file = len({c.source for c in self.layout.signals()}) > 1
            kinds = {self._uses_time_axis(s) for s in self.layout.slots if s.signals and not self._is_fourier_slot(s)}
            link = self.link_x and len(kinds) <= 1  # Datums- und Sekundenachse lassen sich nicht koppeln
            # Fourier-Graphen haben eine eigene X-Achse: keine native Kopplung, die übrigen koppelt _poll_link
            self.manual_link = link and any(self._is_fourier_slot(s) for s in self.layout.slots)
            if self.manual_link:
                link = False
                self.link_settle = max(getattr(self, "link_settle", 0), 3)
            if self.layout.merged:
                # Zusammengefasste Bereiche: je Zeile eigene Subplots mit Spaltenbreiten; die X-Kopplung über
                # die Zeilen hinweg übernimmt _poll_link
                self.last_height = self._row_height(rows)
                index = 0
                for widths in self.layout.row_spans():
                    sub = dpg.add_subplots(1, len(widths), column_ratios=[float(w) for w in widths], no_title=True,
                                           width=-1, height=self.last_height, link_all_x=link, parent=self.plot_area)
                    self.row_subplots.append(sub)
                    for _ in widths:
                        if index < len(self.layout.slots):
                            self._build_plot(index, self.layout.slots[index], multi_file, sub)
                        index += 1
                self.subplots = self.row_subplots[0]
            else:
                self.subplots = dpg.add_subplots(rows, cols, no_title=True, width=-1, height=self.last_height,
                                                 link_all_x=link, parent=self.plot_area)
                for index, slot in enumerate(self.layout.slots):
                    self._build_plot(index, slot, multi_file)
            self.plot_note = (t("Datumsachse nur in Graphen, deren Signale alle eine Startzeit haben; "
                                "die X-Achsen sind deshalb nicht gekoppelt.")
                              if self.date_axis and len(kinds) > 1 else "")
            if self.plot_note:
                self._message(self.plot_note)
        self.alarm_plots = set()               # neue Plots: Hintergrund wird neu gebunden
        self._build_zoom()                     # Detailfenster zeigt denselben Graphen (oder schließt sich)
        if self.slot_ui and self.cross_on:
            self._init_cross_positions()
            self._sync_lines_to_state()
        self._rebuild_table()
        self._apply_graph_font()

    # ---------------------------------------------------------------- Datei für die vorhandenen Graphen wählen
    def _file_names(self) -> list[str]:
        """Anzeigenamen der Dateien; gleiche Namen bekommen den Ordner dazu."""
        names = [d.name for d in self.datasets]
        return [f"{n} ({Path(d.path).parent.name})" if names.count(n) > 1 else n for n, d in zip(names, self.datasets)]

    def _update_file_combo(self) -> None:
        if not dpg.does_item_exist(getattr(self, "file_combo", 0) or 0):
            return
        names = self._file_names()
        dpg.configure_item(self.file_combo, items=([t("Alle Dateien")] if len(names) > 1 else []) + names)
        sources = {os.path.abspath(c.source) for c in self.layout.signals() if c.source}
        value = ""
        if len(sources) == 1:
            path = next(iter(sources))
            value = next((n for n, d in zip(names, self.datasets) if os.path.abspath(d.path) == path), "")
        elif len(sources) > 1:
            value = t("Mehrere Dateien")
        dpg.set_value(self.file_combo, value)

    @staticmethod
    def _match_channel(channel: Channel, dataset: Dataset) -> Channel | None:
        """Gleichnamiges Signal in der Datei: Name, dann Beschriftung, dann Name ohne Groß-/Kleinschreibung."""
        if channel in dataset.channels:
            return channel
        for key in (lambda c: c.name, lambda c: c.label, lambda c: c.name.casefold()):
            wanted = key(channel)
            found = next((c for c in dataset.channels if key(c) == wanted), None)
            if found is not None:
                return found
        return None

    def _on_file_combo(self, _sender=None, value=None, _user_data=None) -> None:
        if value == t("Alle Dateien"):
            self.switch_to_all_files()
            return
        names = self._file_names()
        if value not in names:
            return
        self.switch_to_file(self.datasets[names.index(value)])

    def _layout_signature(self) -> tuple:
        return (self.layout.matrix, tuple(tuple(slot.signals) for slot in self.layout.slots))

    def _remember_all_files(self) -> None:
        """Vor dem Wechsel auf eine Datei: Graphen mit Signalen aus mehreren Dateien merken (genau so, wie sie sind)."""
        if len({c.source for c in self.layout.signals()}) <= 1:
            return
        self.all_files_snapshot = {
            "slots": [(list(s.signals), dict(s.colors), set(s.right), dict(s.limits), dict(s.targets))
                      for s in self.layout.slots],
            "matrix": self.layout.matrix, "after": None}

    def switch_to_all_files(self) -> None:
        """Alle Graphen wieder über alle geladenen Dateien: die gemerkte Darstellung zurück, wenn die Graphen seit
        dem Wechsel nicht anders belegt wurden, sonst je Signal das gleichnamige Signal aller Dateien."""
        if not self.layout.signals():
            self._update_file_combo()
            self._message(t("Noch keine Plots: zuerst Signale auswählen oder einen Vorschlag übernehmen."))
            return
        snap = self.all_files_snapshot
        present = {c for d in self.datasets for c in d.channels}
        if (snap and snap["after"] == self._layout_signature() and len(snap["slots"]) == len(self.layout.slots)
                and all(c in present and c.loaded for sl in snap["slots"] for c in sl[0])):
            for slot, (signals, colors, right, limits, targets) in zip(self.layout.slots, snap["slots"]):
                slot.signals, slot.colors, slot.right = list(signals), dict(colors), set(right)
                slot.limits, slot.targets = dict(limits), dict(targets)
            self.all_files_snapshot = None
            self._layout_changed()
            self._sync_checkboxes()
            self._message(t("Alle Dateien: {count} Signale in den Graphen.", count=len(self.layout.signals())))
            return
        for channel, target in list(self.loading.items()):
            if target is FILE_SWITCH:
                self.loading.pop(channel, None)
        waiting = {m for c in self.layout.signals() for d in self.datasets
                   if (m := self._match_channel(c, d)) is not None and not m.loaded}
        self.file_switch = (None, waiting, [])
        if not waiting:
            self._apply_file_switch()
            return
        self._message(t("Lade {count} Signale aus {name}...", count=len(waiting), name=t("Alle Dateien")))
        for channel in waiting:
            self.loading[channel] = FILE_SWITCH
            job = self._start_job(channel.name) if downsample.applies(channel.source) else None
            self.pool.submit(self._channel_worker, channel, job)

    def switch_to_file(self, dataset: Dataset) -> None:
        """Alle Graphen auf die gleichnamigen Signale dieser Datei umstellen (MF4-Kanäle werden erst geladen)."""
        if not self.layout.signals():
            self._update_file_combo()
            self._message(t("Noch keine Plots: zuerst Signale auswählen oder einen Vorschlag übernehmen."))
            return
        self._remember_all_files()
        for channel, target in list(self.loading.items()):     # ältere Wechsel und noch ladende Signale verwerfen
            if target is FILE_SWITCH or channel.source != dataset.path:
                self.loading.pop(channel, None)
        matches = {c: self._match_channel(c, dataset) for c in self.layout.signals()}
        waiting = {m for m in matches.values() if m is not None and not m.loaded}
        self.file_switch = (dataset, waiting, [])
        if not waiting:
            self._apply_file_switch()
            return
        self._message(t("Lade {count} Signale aus {name}...", count=len(waiting), name=dataset.name))
        for channel in waiting:
            self.loading[channel] = FILE_SWITCH
            job = self._start_job(channel.name) if downsample.applies(channel.source) else None
            self.pool.submit(self._channel_worker, channel, job)

    def _switch_channel_done(self, channel: Channel, error) -> None:
        if not self.file_switch or channel not in self.file_switch[1]:
            return
        self.file_switch[1].discard(channel)
        if error:
            self.file_switch[2].append(channel.label)
        if not self.file_switch[1]:
            self._apply_file_switch()

    def _apply_file_switch(self) -> None:
        dataset, _waiting, failed = self.file_switch
        self.file_switch = None
        missing, replaced = [], 0
        sources = [dataset] if dataset is not None else list(self.datasets)
        for slot in self.layout.slots:
            signals, colors, right, limits, targets = [], {}, set(), {}, {}
            for channel in slot.signals:
                found = [m for d in sources if (m := self._match_channel(channel, d)) is not None and m.loaded]
                if not found:
                    if channel.label not in missing:
                        missing.append(channel.label)
                    continue
                for new in found:
                    if new in signals:              # gleiches Signal mehrerer Dateien: nur einmal
                        continue
                    signals.append(new)
                    replaced += new is not channel
                    # eigene Farbe nur beim Wechsel auf eine Datei bzw. für das Signal selbst (sonst alle gleich)
                    if channel in slot.colors and (dataset is not None or new is channel):
                        colors[new] = slot.colors[channel]
                    if channel in slot.right:
                        right.add(new)
                    if channel in slot.limits:
                        limits[new] = slot.limits[channel]
                    if channel in slot.targets:
                        targets[new] = slot.targets[channel]
            slot.signals, slot.colors, slot.right, slot.limits, slot.targets = signals, colors, right, limits, targets
        if not self.layout.matrix:
            self.layout.slots = [s for s in self.layout.slots if s.signals]
        self._layout_changed()
        self._sync_checkboxes()
        if dataset is not None and self.all_files_snapshot is not None:
            self.all_files_snapshot["after"] = self._layout_signature()   # gilt, solange niemand die Graphen ändert
        name = dataset.name if dataset is not None else t("Alle Dateien")
        text = t("{name}: {count} Signale in den Graphen.", name=name, count=len(self.layout.signals()))
        if missing:
            text += " " + t("Nicht in {name}: {names}", name=name, names=", ".join(missing[:6])
                            + (" ..." if len(missing) > 6 else ""))
        self._message(text, error=bool(missing or failed))

    def _clear_all_plots(self, *_args) -> None:
        """Plotbereich leeren: Graphen samt Aufteilung (Matrix, Bereiche) entfernen; die Dateien bleiben geladen."""
        self.loading.clear()
        self.file_switch = None
        self.layout = PlotLayout()                     # ohne Matrix und ohne Graphen
        self.all_files_snapshot = None
        dpg.set_value(self.matrix_input, "")
        self._layout_changed()
        self._sync_checkboxes()
        self._message(t("Alle Plots und die Aufteilung gelöscht. Die Dateien bleiben geladen."))

    def _row_height(self, rows: int) -> int:
        """Höhe je Zeile bei zusammengefassten Bereichen (jede Zeile hat eigene Subplots)."""
        available = dpg.get_viewport_client_height() - 168 - (self.table_h + SPLIT + 12 if self.cross_on else 0)
        return max(MIN_PLOT_HEIGHT, int((available - 6 * (rows - 1)) / max(1, rows)))

    def _add_plot(self, label: str, parent=None):
        kwargs = dict(label=label, width=-1, height=-1, parent=parent or self.subplots,
                      no_menus=True,  # das eigene Kontextmenü ersetzt das eingebaute von ImPlot
                      payload_type=PAYLOAD, drop_callback=self._on_drop)
        try:  # Uhrzeitformat der Datumsachse; ältere Dear-PyGui-Versionen kennen die Optionen nicht
            return dpg.add_plot(**kwargs, use_24hour_clock=True, use_ISO8601=False, use_local_time=False)
        except Exception:
            return dpg.add_plot(**kwargs)

    LOG_GRID_DECADES = 0      # Hilfslinien bis zur nächsten vollen Dekade um den Datenbereich (ImPlot passt die
                              # Achse beim Einpassen auch an diese Linien an - mehr Dekaden würden die Ansicht dehnen)

    @staticmethod
    def _log_lines(values) -> list[float]:
        """1..9 * 10^k über den positiven Datenbereich (plus Rand), höchstens 300 Linien."""
        arr = np.asarray(values, dtype=np.float64)
        arr = arr[np.isfinite(arr) & (arr > 0)]
        if not arr.size:
            return []
        lo = math.floor(math.log10(float(arr.min()))) - App.LOG_GRID_DECADES
        hi = math.ceil(math.log10(float(arr.max()))) + App.LOG_GRID_DECADES
        lines = [m * 10.0 ** k for k in range(lo, hi + 1) for m in range(1, 10) if m * 10.0 ** k <= 10.0 ** hi]
        return lines[:300]

    def _log_gridlines(self, ui: SlotUI) -> None:
        """Hilfslinien für logarithmische Achsen (Dekaden und 2..9 dazwischen) als unendliche Linien in Gitterfarbe,
        unabhängig von der Dear-PyGui-Version; ohne Legendeneintrag."""
        if not hasattr(dpg, "add_inf_line_series") or not (ui.slot.log_x or ui.slot.log_y):
            return
        slot = ui.slot
        theme = self._grid_theme()
        if slot.log_y and ui.y_axis is not None:
            ys = np.concatenate([np.asarray(c.y, float) for c in slot.signals if c.y is not None and c not in slot.right]
                                or [np.array([])])
            lines = self._log_lines(ys)
            if lines:
                item = dpg.add_inf_line_series(lines, label="##logy", horizontal=True, parent=ui.y_axis)
                dpg.bind_item_theme(item, theme)
        if slot.log_x and not ui.time_axis:
            xs = np.concatenate([np.asarray(c.x, float) for c in slot.signals if c.x is not None] or [np.array([])])
            lines = self._log_lines(xs)
            if lines:
                item = dpg.add_inf_line_series(lines, label="##logx", parent=ui.y_axis)
                dpg.bind_item_theme(item, theme)

    def _grid_theme(self):
        """Theme der Hilfslinien: Gitterfarbe des Farbschemas, halbtransparent."""
        key = ("grid", self.mode)
        if key not in self.series_themes:
            col = themes.color(self.mode, "grid")
            with dpg.theme() as theme:
                with dpg.theme_component(dpg.mvInfLineSeries if hasattr(dpg, "mvInfLineSeries") else dpg.mvAll):
                    dpg.add_theme_color(dpg.mvPlotCol_Line, (*col[:3], 150), category=dpg.mvThemeCat_Plots)
            self.series_themes[key] = theme
        return self.series_themes[key]

    @staticmethod
    def _log_kwargs() -> dict:
        """Logarithmische Achse: Dear PyGui 2.x scale=mvPlotScale_Log10, 1.x log_scale=True."""
        return {"scale": dpg.mvPlotScale_Log10} if hasattr(dpg, "mvPlotScale_Log10") else {"log_scale": True}

    @staticmethod
    def _is_bar(channel: Channel) -> bool:
        return getattr(channel, "plot_style", "line") == "bar" and hasattr(dpg, "add_bar_series")

    def _add_x_axis(self, plot, label: str, time_axis: bool, log: bool = False):
        kwargs = dict(label=label, parent=plot, payload_type=PAYLOAD, drop_callback=self._on_drop)
        if log and not time_axis:
            kwargs.update(self._log_kwargs())
        elif time_axis:  # Dear PyGui 2.x: scale=mvPlotScale_Time, 1.x: time=True
            if hasattr(dpg, "mvPlotScale_Time"):
                kwargs["scale"] = dpg.mvPlotScale_Time
            else:
                kwargs["time"] = True
        return dpg.add_plot_axis(dpg.mvXAxis, **kwargs)

    def _build_plot(self, index: int, slot: GraphSlot, multi_file: bool, parent=None, zoom: bool = False) -> None:
        time_axis = self._uses_time_axis(slot)
        plot = self._add_plot(slot.display_name(index), parent)
        x_label, y_label = self._axis_labels(slot, time_axis)
        x_axis = self._add_x_axis(plot, x_label, time_axis, log=slot.log_x)
        y_axis = dpg.add_plot_axis(dpg.mvYAxis, label=y_label, parent=plot, payload_type=PAYLOAD,
                                   drop_callback=self._on_drop, **(self._log_kwargs() if slot.log_y else {}))
        y2_axis = None
        if any(c in slot.right for c in slot.signals):  # rechte Achse nur, wenn ein Signal sie nutzt
            y2_axis = self._add_y2_axis(plot, self._unit_label([c for c in slot.signals if c in slot.right]),
                                        log=slot.log_y)
            self.right_axes.add(y2_axis)
        for item in (plot, x_axis, y_axis, y2_axis):
            if item is not None:
                self.drop_targets[item] = slot
        ui = SlotUI(slot=slot, plot=plot, x_axis=x_axis, y_axis=y_axis, time_axis=time_axis, y2_axis=y2_axis,
                    fourier=self._is_fourier_slot(slot))
        labels = {}
        ui.labels = labels
        for col_index, channel in enumerate(slot.signals):
            label = f"{channel.label} - {Path(channel.source).name}" if multi_file else channel.label
            on_right = channel in slot.right and y2_axis is not None
            if on_right:
                label = t("{label} (rechts)", label=label)
            x, y = decimate(channel.x, channel.y)
            x = x + self._offset(ui, channel)
            labels[channel] = label
            if self._is_bar(channel):                     # Harmonische: senkrechte Balken je Ordnung
                series = dpg.add_bar_series(x.tolist(), y.tolist(), label=label,
                                            weight=float(getattr(channel, "bar_width", 0.6)),
                                            parent=y2_axis if on_right else y_axis)
            else:
                series = dpg.add_line_series(x.tolist(), y.tolist(), label=label,
                                             parent=y2_axis if on_right else y_axis)
            dpg.bind_item_theme(series, self._theme_for(slot, channel, col_index))
            ui.series[channel] = series
            ui.curve[channel] = (x.tolist(), y.tolist())
            ui.colors[channel] = col_index
            self._update_limit_lines(ui, channel)
            self._update_reg_line(ui, channel)
        span = self._data_range(ui)
        for k in (0, 1):
            col = (*themes.color(self.mode, "cross")[k], 255)
            # Startlage: gespeicherte Markerposition, sonst im Datenbereich. Nie bei 0: sichtbare Linien zählen beim
            # Einpassen mit, bei Datumsachse (X um 1,7e9 s) schrumpften die Kurven sonst auf einen Strich
            if slot.cross[k] is not None:
                start = float(slot.cross[k])
            elif span is not None:
                start = span[0] + (span[1] - span[0]) * (k + 1) / 3
            else:
                start = 0.0
            # nur senkrechte Marker: waagerechte Linien machten die Darstellung unübersichtlich
            ui.v_lines.append(dpg.add_drag_line(label=f"M{k + 1}", color=col, default_value=start, vertical=True,
                                                thickness=1.5, show=self.cross_on and not ui.fourier, parent=plot))
        if slot.cross3 is not None:
            start3 = float(slot.cross3)
        elif span is not None:
            start3 = span[0] + (span[1] - span[0]) / 2
        else:
            start3 = 0.0
        ui.m3_line = dpg.add_drag_line(label="M3", color=(*themes.color(self.mode, "ok"), 255), default_value=start3,
                                       vertical=True, thickness=1.5, show=self.m3_on and not ui.fourier, parent=plot)
        ui.labels = labels
        self._log_gridlines(ui)                          # logarithmische Achsen: Hilfslinien 1..9 je Dekade
        key = slot.legend if slot.legend in LEGEND_LOCATIONS else LEGEND_DEFAULT
        ui.legend = dpg.add_plot_legend(parent=plot, location=getattr(dpg, LEGEND_LOCATIONS[key]))
        if zoom:
            self.zoom_ui = ui                    # Detailfenster: nicht Teil der Matrix, Export oder Kopplung
        else:
            self.slot_ui.append(ui)
        self._draw_comments(ui)
        dpg.fit_axis_data(x_axis)
        self._fit_y(ui)

    # ---------------------------------------------------------------- Berechnete Signale
    def _build_calc_window(self) -> None:
        heading, dim = themes.color(self.mode, "heading"), themes.color(self.mode, "text_dim")
        with dpg.window(tag="calc_window", label=t("Signal berechnen"), modal=True, show=False, width=720, height=640,
                        no_collapse=True):
            self.calc_heading = dpg.add_text("", color=heading)
            self._colour(self.calc_heading, "heading")
            self.calc_list = dpg.add_child_window(height=150, border=True)
            dpg.add_separator()
            self.calc_mode_text = dpg.add_text("", color=heading)
            self._colour(self.calc_mode_text, "heading")
            with dpg.group(horizontal=True):
                dpg.add_text(t("Name"))
                self.calc_name = dpg.add_input_text(width=220, hint=t("z. B. Leistung"))
                dpg.add_text(t("Einheit"))
                self.calc_unit = dpg.add_input_text(width=110, hint=t("automatisch"))
            with dpg.group(horizontal=True):
                dpg.add_text(t("Art"))
                self.calc_kind = dpg.add_radio_button(items=[t("Formel"), t("Fourier-Analyse")], horizontal=True,
                                                      default_value=t("Formel"), callback=lambda: self._calc_kind_show())
            with dpg.group() as self.calc_formula_group:
                dpg.add_text(t("Formel"))
                self.calc_formula = dpg.add_input_text(width=-1, hint="{Strom} * {Spannung}")
                with dpg.group(horizontal=True):
                    self.calc_signal = dpg.add_combo(width=330)
                    dpg.add_button(label=t("Signal einfügen"), callback=self._calc_insert_signal)
                    for op in ("+", "-", "*", "/", "(", ")"):
                        dpg.add_button(label=f" {op} ", callback=self._calc_insert, user_data=f" {op} ")
                self._colour(dpg.add_text(t("Signale in geschweiften Klammern, Zahlen direkt: ({U1} + {U2}) / 2, "
                                            "{Strom} * {Spannung} * 0.001. Verschiedene Zeitachsen werden auf die des "
                                            "ersten Signals interpoliert."), wrap=690, color=dim), "text_dim")
            with dpg.group(show=False) as self.calc_fft_group:
                with dpg.group(horizontal=True):
                    dpg.add_text(t("Signal"))
                    self.calc_fft_signal = dpg.add_combo(width=330, callback=lambda: self._calc_fft_preview())
                    dpg.add_text(t("Fenster"))
                    self.calc_fft_window = dpg.add_combo(items=[t("Automatisch"), t("Hann"), t("Rechteck")],
                                                         default_value=t("Automatisch"), width=130,
                                                         callback=lambda: self._calc_fft_preview())
                    self._tooltip(self.calc_fft_window, t("Automatisch: periodisches Signal -> nur ganze Perioden, "
                                                          "Rechteck (kein Leckeffekt); sonst Hann. Hann: weniger "
                                                          "Leckeffekt bei nicht ganzzahligen Perioden (Amplitude "
                                                          "korrigiert). Rechteck: ohne Fenster."))
                with dpg.group(horizontal=True):
                    self.calc_fft_mode = dpg.add_radio_button(items=[t("Harmonische"), t("Frequenzbereich")],
                                                              horizontal=True, default_value=t("Harmonische"),
                                                              callback=lambda: self._calc_fft_preview())
                    dpg.add_text(t("Anzeige"))
                    self.calc_fft_scale = dpg.add_combo(items=[t("Anteil [%]"), t("Dämpfung [dB]"), t("Amplitude")],
                                                        default_value=t("Anteil [%]"), width=150,
                                                        callback=lambda: self._calc_fft_preview())
                    self._tooltip(self.calc_fft_scale, t("Anteil [%]: Amplitude jeder Harmonischen in Prozent der "
                                                         "Summe aller Harmonischen (reiner Sinus: H1 = 100 %). "
                                                         "Dämpfung [dB]: 20*log10(A1/An) gegenüber der "
                                                         "Grundschwingung (H1 = 0 dB, 20 dB = 1/10, 40 dB = 1/100)."
                                                         " Amplitude: Spitzenwert in der Einheit des Signals. Beim "
                                                         "durchgehenden Spektrum: % bzw. dB bezogen auf die "
                                                         "Amplitude der Grundschwingung."))
                with dpg.group(horizontal=True):
                    dpg.add_text(t("Frequenz von"))
                    self.calc_fft_fmin = dpg.add_input_text(width=90, default_value="0",
                                                            callback=lambda: self._calc_fft_preview())
                    dpg.add_text(t("bis"))
                    self.calc_fft_fmax = dpg.add_input_text(width=90, hint=t("max"),
                                                            callback=lambda: self._calc_fft_preview())
                    self._tooltip(self.calc_fft_fmax, t("Leer = bis zur halben Abtastrate."))
                    dpg.add_text("Hz")
                    dpg.add_text(t("Darstellung"))
                    self.calc_fft_view = dpg.add_combo(items=[t("Balken an den Harmonischen"),
                                                              t("Spektrum (durchgehend)")],
                                                       default_value=t("Balken an den Harmonischen"), width=220,
                                                       callback=lambda: self._calc_fft_preview())
                    self._tooltip(self.calc_fft_view, t("Frequenzbereich wahlweise als einzelne Balken an den "
                                                        "Harmonischen n*f0 oder als durchgehendes Spektrum (Linie, "
                                                        "alle Frequenzlinien). Harmonische nach Nummer sind immer "
                                                        "Balken."))
                with dpg.group(horizontal=True):
                    orders = [str(n) for n in range(1, fourier.MAX_HARMONIC + 1)]
                    dpg.add_text(t("Harmonische von"))
                    self.calc_fft_hmin = dpg.add_combo(items=orders, default_value="1", width=60,
                                                       callback=lambda: self._calc_fft_preview())
                    dpg.add_text(t("bis"))
                    self.calc_fft_hmax = dpg.add_combo(items=orders, default_value=str(fourier.MAX_HARMONIC), width=60,
                                                       callback=lambda: self._calc_fft_preview())
                    dpg.add_text(t("Grundfrequenz f0"))
                    self.calc_fft_f0 = dpg.add_input_text(width=90, default_value="auto",
                                                          callback=lambda: self._calc_fft_preview())
                    self._tooltip(self.calc_fft_f0, t("auto = stärkste Frequenz im Signal (ohne Gleichanteil), "
                                                      "sonst fest in Hz, z. B. 50."))
                    dpg.add_text("Hz")
                self.calc_fft_text = dpg.add_text("")
                self._colour(dpg.add_text(t("Ergebnis: je Harmonische ein senkrechter Balken - H1 = Grundschwingung f0, "
                                            "Hn bei n*f0 (50 Hz: H3 = 150 Hz). X = Nummer (Harmonische 1..15) bzw. "
                                            "Frequenz [Hz] (alle Harmonischen im Frequenzbereich). Y = Anteil [%] oder "
                                            "Dämpfung [dB]. Welche Schwingung(en) ausgewertet werden, bestimmen die "
                                            "Marker im Graphen des Grundsignals (Perioden, deren Mitte zwischen M1 und "
                                            "M2 liegt; ohne Marker alle). Ergebnis frei benennen und in einen eigenen "
                                            "Graphen ziehen."), wrap=690, color=dim), "text_dim")
            with dpg.group(horizontal=True):
                dpg.add_text(t("Bemerkung"))
                self.calc_note = dpg.add_input_text(width=-1, hint=t("optional, wird in der Definition gespeichert"))
            self.calc_status = dpg.add_text("", wrap=690)
            with dpg.group(horizontal=True):
                self.calc_run = dpg.add_button(label=t("Berechnen und hinzufügen"), callback=self._calc_apply)
                dpg.add_button(label=t("Neu"), callback=lambda: self._calc_edit(None))
                dpg.add_button(label=t("Definition speichern..."), callback=self._open_def_window)
                dpg.add_button(label=t("Definition laden..."), callback=self._ask_load_definitions)
                dpg.add_button(label=t("Schließen"), callback=lambda: dpg.configure_item("calc_window", show=False))

    def _open_calc_window(self, _sender=None, _value=None, dataset: Dataset | None = None) -> None:
        if dataset is None or dataset not in self.datasets:
            return
        self.calc_dataset = dataset
        dpg.set_value(self.calc_heading, t("Signal berechnen: {name}", name=dataset.name))
        dpg.configure_item(self.calc_signal, items=[c.name for c in dataset.channels])
        if dataset.channels:
            dpg.set_value(self.calc_signal, dataset.channels[0].name)
            dpg.set_value(self.calc_fft_signal, dataset.channels[0].name)
        dpg.set_value(self.calc_status, "")
        self._calc_edit(None)
        width, height = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
        dpg.configure_item("calc_window", show=True, pos=[max(0, (width - 720) // 2), max(0, (height - 640) // 2)])

    def _calc_refresh_list(self) -> None:
        dpg.delete_item(self.calc_list, children_only=True)
        self.calc_fft_items = {}
        items = formula.computed(self.calc_dataset)
        dpg.add_text(t("Berechnete Signale: {count} von {max}", count=len(items), max=formula.MAX_COMPUTED),
                     parent=self.calc_list)
        for channel in items:
            with dpg.group(horizontal=True, parent=self.calc_list):
                dpg.add_button(label=t("Bearbeiten"), small=True, callback=lambda s, a, u: self._calc_edit(u),
                               user_data=channel)
                dpg.add_button(label=t("Löschen"), small=True, callback=lambda s, a, u: self._calc_delete(u),
                               user_data=channel)
                if getattr(channel, "fourier", None):
                    dpg.add_button(label=t("Tabelle..."), small=True, user_data=channel,
                                   callback=lambda s, a, u: self.open_fourier_window(u))
                item = dpg.add_text(f"{channel.label} = {channel.formula}" + (f"   ({channel.note})" if channel.note else ""))
                if getattr(channel, "fourier", None):
                    self._fourier_tooltip(item, channel)
                    self.calc_fft_items[item] = channel

    def _calc_edit(self, channel: Channel | None) -> None:
        self.calc_editing = channel
        dpg.set_value(self.calc_name, channel.name if channel else "")
        dpg.set_value(self.calc_unit, channel.unit if channel else "")
        dpg.set_value(self.calc_formula, channel.formula if channel else "")
        dpg.set_value(self.calc_note, channel.note if channel else "")
        dpg.set_value(self.calc_mode_text, t("Bearbeiten: {name}", name=channel.name) if channel else t("Neues Signal"))
        dpg.configure_item(self.calc_run, label=t("Übernehmen") if channel else t("Berechnen und hinzufügen"))
        names = [c.name for c in self.calc_dataset.channels if c is not channel]
        dpg.configure_item(self.calc_signal, items=names)
        dpg.configure_item(self.calc_fft_signal, items=[c.name for c in self.calc_dataset.channels
                                                        if c is not channel and c.plottable])
        if channel is not None and fourier.is_fft(channel.formula):
            self._calc_fft_load(channel.formula)
            source = self._fourier_source(channel)
            if channel.unit in ("%", "dB", "") or (source is not None and channel.unit == source.unit):
                dpg.set_value(self.calc_unit, "")              # Einheit folgt der Anzeige (%, dB, Signal)
        elif channel is not None:
            dpg.set_value(self.calc_kind, t("Formel"))
        self._calc_kind_show()
        self._calc_refresh_list()

    FOURIER_ROWS = 30   # Perioden im Tooltip (Rest zusammengefasst)

    @staticmethod
    def _fourier_period_text(info: dict) -> str:
        if info.get("periodic"):
            return t("Periodisch: ja, {count} ganze Perioden (Analyse nur über ganze Perioden, mittlere f0 = {f0} Hz).",
                     count=info["periods"], f0=f"{info['f0']:.6g}")
        return t("Periodisch: nein - {reason} (Analyse über das ganze Signal, Fenster {window}).",
                 reason=info.get("reason") or "-", window=info.get("window", "hann"))

    def _fourier_tooltip(self, item, channel: Channel) -> None:
        """Tooltip mit Tabelle: Anzahl Perioden, Ergebnis über alle Perioden, je Periode (Amplituden in der Einheit)."""
        info = channel.fourier
        table = info.get("table") or {}
        columns, rows = table.get("columns") or [], table.get("rows") or []

        def cell(value, column: int) -> str:
            if isinstance(value, str):
                return value
            if value is None or (isinstance(value, float) and not np.isfinite(value)):
                return "-"
            if column == 0:
                return str(int(value))
            return fmt(float(value))
        with dpg.tooltip(item):
            heading = themes.color(self.mode, "heading")
            dpg.add_text(t("Fourier-Analyse {label}: {formula}", label=channel.label, formula=channel.formula),
                         color=heading)
            dpg.add_text(t("Anzahl Perioden: {count}", count=info.get("periods", 0)))
            dpg.add_text(self._fourier_period_text(info), wrap=900)
            if not columns:
                return
            dpg.add_text(self._fourier_legend(channel))
            if info.get("selection_text"):
                dpg.add_text(info["selection_text"], color=heading)
            with dpg.table(header_row=True, borders_innerV=True, borders_outerH=True, borders_outerV=True,
                           row_background=True, policy=dpg.mvTable_SizingFixedFit):
                for name in columns:
                    dpg.add_table_column(label=name)
                shown = [table["all"]] + list(table.get("stats") or []) + rows[:self.FOURIER_ROWS]
                for number, row in enumerate(shown):
                    with dpg.table_row():
                        for column, value in enumerate(row):
                            text = dpg.add_text(cell(value, column))
                            if number == 0:
                                dpg.configure_item(text, color=heading)
            if len(rows) > self.FOURIER_ROWS:
                dpg.add_text(t("... {count} weitere Perioden", count=len(rows) - self.FOURIER_ROWS))
            dpg.add_text(t("Doppelklick auf das Signal: vollständige Tabelle in eigenem Fenster (scrollbar)."),
                         color=themes.color(self.mode, "text_dim"))

    @staticmethod
    def _is_fourier_slot(slot: GraphSlot) -> bool:
        """Graph zeigt Ergebnisse der Fourier-Analyse (X = Frequenz bzw. Nummer der Harmonischen)."""
        return bool(slot.signals) and all(getattr(c, "fourier", None) for c in slot.signals)

    def _fourier_legend(self, channel: Channel) -> str:
        source = self._fourier_source(channel)
        unit = (source.unit if source is not None else "") or "-"
        if (channel.fourier or {}).get("scale") == "amp":
            return t("H1 = Grundschwingung f0, Hn bei n*f0; Hn = Amplitude (Spitzenwert) in {unit}.", unit=unit)
        if (channel.fourier or {}).get("scale") == "db":
            return t("H1 = Grundschwingung f0, Hn bei n*f0; Hn = Dämpfung 20*log10(A1/An) in dB (H1 = 0 dB), "
                     "A1 = Amplitude der Grundschwingung in {unit}.", unit=unit)
        return t("H1 = Grundschwingung f0, Hn bei n*f0; Hn = Anteil der Amplitude an der Summe aller Harmonischen "
                 "in % (Summe 100 %), A1 = Amplitude der Grundschwingung in {unit}.", unit=unit)

    def _fourier_source(self, channel: Channel) -> Channel | None:
        """Grundsignal einer Fourier-Analyse (gleiche Datei)."""
        name = (getattr(channel, "fourier", None) or {}).get("signal")
        for dataset in self.datasets:
            if dataset.path == channel.source:
                return next((c for c in dataset.channels if c.name == name), None)
        return None

    def _update_harmonics(self) -> None:
        """Balken der Harmonischen nach den Markern im Graphen des Grundsignals: Perioden, deren Mitte zwischen M1
        und M2 liegt (ohne Marker alle). Die Werte werden aus den gespeicherten Energien je Periode summiert."""
        for channel in {c for ui in self._all_ui() for c in ui.slot.signals if getattr(c, "fourier", None)
                        and (c.fourier.get("harm") or {}).get("numbers")}:
            info = channel.fourier
            source = self._fourier_source(channel)
            lo = hi = None
            by_view = False
            base_ui = next((u for u in self.slot_ui if source is not None and source in u.slot.signals
                            and not u.fourier), None)
            if base_ui is not None:
                offset = self._offset(base_ui, source)
                if self.cross_on and base_ui.slot.cross[0] is not None and base_ui.slot.cross[1] is not None:
                    lo, hi = base_ui.slot.cross[0] - offset, base_ui.slot.cross[1] - offset
                elif base_ui.view is not None and self._view_cuts(base_ui, source):
                    lo, hi = base_ui.view[0] - offset, base_ui.view[1] - offset   # ohne Marker: sichtbarer Bereich
                    by_view = True
            energy, chosen = fourier.select(info, lo, hi)
            xs = channel.x
            if info.get("view") == "line":             # durchgehendes Spektrum der gewählten Perioden
                if lo is not None and not chosen and info.get("harm", {}).get("bounds"):
                    xs, values = channel.x, np.zeros_like(channel.x)
                else:
                    xs, values = fourier.line_spectrum(info, chosen or None)
            else:
                part = fourier.display(energy, info.get("scale", "pct"), max(1, len(chosen)))
                orders = info.get("orders") or info.get("shown") or []
                values = np.array([part[n - 1] if n - 1 < part.size else 0.0 for n in orders])
                if values.shape != channel.x.shape:
                    continue
            if not info.get("harm", {}).get("bounds"):
                text = t("Auswahl: ganzes Signal (nicht periodisch).")
            elif lo is None:
                text = t("Auswahl: alle {count} Perioden (ohne Marker im Graphen von {name}).",
                         count=len(chosen), name=source.label if source is not None else "-")
            elif by_view and chosen:
                text = t("Auswahl (sichtbarer Bereich): Perioden {span} ({count} von {total}).",
                         span=f"{chosen[0]}-{chosen[-1]}", count=len(chosen), total=len(info["harm"]["bounds"]))
            elif chosen:
                span = f"{chosen[0]}" if len(chosen) == 1 else f"{chosen[0]}-{chosen[-1]}"
                text = t("Auswahl (Marker): Periode {span} ({count} von {total}).", span=span, count=len(chosen),
                         total=len(info["harm"]["bounds"]))
            else:
                text = t("Auswahl (Marker): keine Periode, deren Mitte zwischen M1 und M2 liegt.")
            info["selection"], info["selection_text"] = chosen, text
            if channel.y is not None and channel.y.shape == values.shape and channel.x.shape == xs.shape \
                    and np.allclose(channel.y, values, equal_nan=True) and np.allclose(channel.x, xs):
                continue
            channel.x, channel.y = np.asarray(xs, dtype=np.float64), values
            for ui in self._all_ui():
                series = ui.series.get(channel)
                if series is not None and dpg.does_item_exist(series):
                    dpg.set_value(series, [channel.x.tolist(), np.nan_to_num(values).tolist()])

    @staticmethod
    def _view_cuts(ui: SlotUI, channel: Channel) -> bool:
        """Zeigt der Graph nur einen Teil des Signals (gezoomt)?"""
        if channel.x is None or not channel.x.size or ui.view is None:
            return False
        offset = channel.x_epoch if ui.time_axis else 0.0
        return ui.view[0] > float(np.nanmin(channel.x)) + offset or ui.view[1] < float(np.nanmax(channel.x)) + offset

    def _hovered_fourier(self) -> Channel | None:
        """Ergebnis der Fourier-Analyse unter der Maus (Signalliste oder Liste im Rechendialog)."""
        candidates = [(box, c) for c, box in self.checkboxes.items() if getattr(c, "fourier", None)]
        candidates += list(getattr(self, "calc_fft_items", {}).items())
        for item, channel in candidates:
            if dpg.does_item_exist(item) and dpg.is_item_hovered(item):
                return channel
        return None

    FOURIER_WINDOW_ROWS = 5000   # Zeilen im Fenster (sehr lange Messungen: Rest nur in der Zwischenablage)

    @staticmethod
    def _fourier_cell(value, column: int) -> str:
        if isinstance(value, str):
            return value
        if value is None or (isinstance(value, float) and not np.isfinite(value)):
            return "-"
        return str(int(value)) if column == 0 else fmt(float(value))

    def _fourier_lines(self, channel: Channel) -> list[list[str]]:
        """Kopf und alle Zeilen der Periodentabelle als Text (Alle, Mittel, Min, Max, je Periode)."""
        table = channel.fourier.get("table") or {}
        rows = [table.get("all") or []] + list(table.get("stats") or []) + list(table.get("rows") or [])
        return [list(table.get("columns") or [])] + [[self._fourier_cell(v, i) for i, v in enumerate(r)] for r in rows]

    def open_fourier_window(self, channel: Channel) -> None:
        """Eigenes Fenster mit allen Angaben der Fourier-Analyse und der vollständigen Periodentabelle."""
        info = getattr(channel, "fourier", None)
        if not info:
            return
        if dpg.does_item_exist("fourier_window"):
            dpg.delete_item("fourier_window")
        self.fourier_channel = channel
        width = min(1200, dpg.get_viewport_client_width() - 40)
        height = min(720, dpg.get_viewport_client_height() - 40)
        heading = themes.color(self.mode, "heading")
        table = info.get("table") or {}
        lines = self._fourier_lines(channel)
        with dpg.window(tag="fourier_window", label=t("Fourier-Analyse: {label}", label=channel.label),
                        width=width, height=height, no_collapse=True,
                        pos=[max(0, (dpg.get_viewport_client_width() - width) // 2),
                             max(0, (dpg.get_viewport_client_height() - height) // 2)]):
            dpg.add_text(t("Fourier-Analyse {label}: {formula}", label=channel.label, formula=channel.formula),
                         color=heading)
            dpg.add_text(t("Datei: {name}", name=Path(channel.source).name))
            dpg.add_text(t("Anzahl Perioden: {count}", count=info.get("periods", 0)))
            dpg.add_text(self._fourier_period_text(info), wrap=0)
            dpg.add_text(t("Abtastrate {fs} Hz, Auflösung {df} Hz, Fenster {window}, analysierte Dauer {dur} s.",
                           fs=f"{info.get('fs', 0):.6g}", df=f"{info.get('df', 0):.4g}",
                           window=info.get("window", "-"), dur=f"{info.get('duration', 0):.6g}"))
            dpg.add_text(self._fourier_legend(channel))
            if info.get("selection_text"):
                dpg.add_text(info["selection_text"], color=heading)
            with dpg.group(horizontal=True):
                dpg.add_button(label=t("Tabelle kopieren"), callback=lambda: self._fourier_copy(channel))
                self._tooltip(dpg.last_item(), t("Alle Zeilen tabulatorgetrennt in die Zwischenablage (z. B. für Excel)."))
                dpg.add_button(label=t("Schließen"), callback=lambda: dpg.delete_item("fourier_window"))
            if len(lines) > 1 and lines[0]:
                with dpg.table(header_row=True, borders_innerV=True, borders_outerH=True, borders_outerV=True,
                               row_background=True, scrollY=True, scrollX=True, freeze_rows=1, freeze_columns=1,
                               policy=dpg.mvTable_SizingFixedFit, height=-28) as self.fourier_table:
                    for name in lines[0]:
                        dpg.add_table_column(label=name)
                    summary = 1 + len(table.get("stats") or [])
                    for number, row in enumerate(lines[1:1 + self.FOURIER_WINDOW_ROWS]):
                        with dpg.table_row():
                            for value in row:
                                item = dpg.add_text(value)
                                if number < summary:
                                    dpg.configure_item(item, color=heading)
            rest = len(lines) - 1 - self.FOURIER_WINDOW_ROWS
            dpg.add_text(t("{count} Zeilen nur über Tabelle kopieren.", count=rest) if rest > 0 else
                         t("{count} Perioden, scrollbar.", count=len(table.get("rows") or [])))

    def _fourier_copy(self, channel: Channel) -> None:
        text = "\n".join("\t".join(row) for row in self._fourier_lines(channel))
        dpg.set_clipboard_text(text)
        self._message(t("Periodentabelle von {label} kopiert ({count} Zeilen).", label=channel.label,
                        count=len(self._fourier_lines(channel)) - 1))

    def _calc_is_fft(self) -> bool:
        return dpg.get_value(self.calc_kind) == t("Fourier-Analyse")

    def _calc_kind_show(self) -> None:
        fft = self._calc_is_fft()
        dpg.configure_item(self.calc_formula_group, show=not fft)
        dpg.configure_item(self.calc_fft_group, show=fft)
        if fft:
            self._calc_fft_preview()

    def _calc_fft_spec(self) -> fourier.Spec:
        """Eingaben der Fourier-Analyse -> Spec (FourierError bei ungültigen Werten)."""
        signal = dpg.get_value(self.calc_fft_signal)
        if not signal:
            raise fourier.FourierError(t("Fourier: bitte ein Signal wählen."))
        window = {t("Rechteck"): "rect", t("Hann"): "hann"}.get(dpg.get_value(self.calc_fft_window), "auto")
        scale = {t("Dämpfung [dB]"): "db", t("Amplitude"): "amp"}.get(dpg.get_value(self.calc_fft_scale), "pct")
        view = "; plot=line" if dpg.get_value(self.calc_fft_view) == t("Spektrum (durchgehend)") else ""
        f0 = dpg.get_value(self.calc_fft_f0).strip() or "auto"
        if dpg.get_value(self.calc_fft_mode) == t("Harmonische"):
            text = f"FFT({{{signal}}}; h={dpg.get_value(self.calc_fft_hmin)}..{dpg.get_value(self.calc_fft_hmax)}; " \
                   f"f0={f0}; y={scale}; win={window})"
        else:
            fmin = dpg.get_value(self.calc_fft_fmin).strip() or "0"
            fmax = dpg.get_value(self.calc_fft_fmax).strip() or "max"
            text = f"FFT({{{signal}}}; f={fmin}..{fmax}; f0={f0}; y={scale}{view}; win={window})"
        return fourier.parse(text)

    def _calc_fft_preview(self) -> None:
        try:
            dpg.set_value(self.calc_fft_text, t("Formel: {text}", text=self._calc_fft_spec().text()))
        except fourier.FourierError as exc:
            dpg.set_value(self.calc_fft_text, str(exc))

    def _calc_fft_load(self, text: str) -> None:
        """Gespeicherte Fourier-Formel in die Eingaben übernehmen (Bearbeiten)."""
        try:
            spec = fourier.parse(text)
        except fourier.FourierError:
            return
        dpg.set_value(self.calc_kind, t("Fourier-Analyse"))
        dpg.set_value(self.calc_fft_signal, spec.signal)
        dpg.set_value(self.calc_fft_window, {"rect": t("Rechteck"), "hann": t("Hann")}.get(spec.window, t("Automatisch")))
        dpg.set_value(self.calc_fft_mode, t("Harmonische") if spec.mode == "harm" else t("Frequenzbereich"))
        dpg.set_value(self.calc_fft_fmin, f"{spec.fmin:g}")
        dpg.set_value(self.calc_fft_fmax, "" if spec.fmax is None else f"{spec.fmax:g}")
        dpg.set_value(self.calc_fft_hmin, str(spec.hmin))
        dpg.set_value(self.calc_fft_hmax, str(spec.hmax))
        dpg.set_value(self.calc_fft_f0, "auto" if spec.f0 is None else f"{spec.f0:g}")
        dpg.set_value(self.calc_fft_scale, {"db": t("Dämpfung [dB]"), "amp": t("Amplitude")}.get(spec.scale,
                                                                                                    t("Anteil [%]")))
        dpg.set_value(self.calc_fft_view, t("Spektrum (durchgehend)") if spec.view == "line"
                      else t("Balken an den Harmonischen"))

    def _calc_insert(self, _sender, _value, text: str) -> None:
        dpg.set_value(self.calc_formula, (dpg.get_value(self.calc_formula).rstrip() + text).lstrip())

    def _calc_insert_signal(self, *_args) -> None:
        name = dpg.get_value(self.calc_signal)
        if name:
            current = dpg.get_value(self.calc_formula).rstrip()
            dpg.set_value(self.calc_formula, (current + " {" + name + "}").lstrip())

    def _calc_apply(self, *_args) -> None:
        dataset, previous = self.calc_dataset, self.calc_editing
        if previous is None and len(formula.computed(dataset)) >= formula.MAX_COMPUTED:
            dpg.set_value(self.calc_status, t("Höchstens {count} berechnete Signale je Datei.", count=formula.MAX_COMPUTED))
            return
        text = dpg.get_value(self.calc_formula)
        if self._calc_is_fft():
            try:
                text = self._calc_fft_spec().text()
            except fourier.FourierError as exc:
                dpg.set_value(self.calc_status, t("Fehler: {error}", error=exc))
                return
        args = (dataset, dpg.get_value(self.calc_name), dpg.get_value(self.calc_unit), text)
        try:
            formula.parse(args[3])   # Syntaxfehler sofort melden, Rechnen im Hintergrund (MF4 lädt nach)
        except formula.FormulaError as exc:
            dpg.set_value(self.calc_status, t("Fehler: {error}", error=exc))
            return
        dpg.set_value(self.calc_status, t("Wird berechnet..."))
        job = self._start_job(t("Berechnen")) if downsample.applies(dataset.path) else None
        self.pool.submit(self._calc_worker, args, previous, job, dpg.get_value(self.calc_note).strip())

    def _calc_worker(self, args, previous, job=None, note: str = "") -> None:
        try:
            with progress.track(job):
                progress.busy(t("Signale laden und rechnen..."))
                channel = formula.compute(*args, exclude=previous)
            channel.note = note
            self.results.put(("calc", args[0], channel, previous, None))
        except progress.Cancelled:
            self.results.put(("calc", args[0], None, previous, CANCELLED))
        except LoadError as exc:
            self.results.put(("calc", args[0], None, previous, str(exc)))
        except Exception as exc:
            log_exception(t("Berechnen"), exc)
            self.results.put(("calc", args[0], None, previous, f"{type(exc).__name__}: {exc}"))

    def _calc_done(self, dataset: Dataset, channel, previous, error) -> None:
        if error:
            text = t("Abgebrochen.") if error == CANCELLED else t("Fehler: {error}", error=error)
            if dpg.does_item_exist(self.calc_status):
                dpg.set_value(self.calc_status, text)
            return
        old_name = previous.name if previous is not None else None
        try:
            result = formula.add_or_replace(dataset, channel, previous)
            if old_name and old_name != result.name:   # umbenannt: Verweise in anderen Formeln mitziehen
                formula.rename_references(dataset, old_name, result.name)
        except formula.FormulaError as exc:
            dpg.set_value(self.calc_status, t("Fehler: {error}", error=exc))
            return
        note = t(" Auf die Zeitachse von {name} interpoliert: {names}.", name=formula.references(
            formula.parse(result.formula))[0], names=", ".join(result.interpolated)) if result.interpolated else ""
        info = getattr(result, "fourier", None)
        if info:
            note += t(" Spektrum: Abtastrate {fs} Hz, Auflösung {df} Hz", fs=f"{info['fs']:.6g}", df=f"{info['df']:.4g}")
            note += t(", Eigenfrequenz f0 = {f0} Hz.", f0=f"{info['f0']:.6g}") if "f0" in info else "."
            note += " " + self._fourier_period_text(info) + " " + t("Tabelle: Maus über das Signal in der Liste.")
        self._refresh_channel_list()
        if previous is not None:
            self._layout_changed()   # angezeigte Kurven mit neuen Werten zeichnen
        if dpg.does_item_exist("calc_window") and getattr(self, "calc_dataset", None) is dataset:
            self._calc_edit(None)
            dpg.set_value(self.calc_status, t("{label} berechnet ({count} Werte).", label=result.label,
                                              count=f"{result.y.size:,}".replace(",", ".")) + note)
        self._message(t("{label} berechnet ({count} Werte).", label=result.label,
                        count=f"{result.y.size:,}".replace(",", ".")) + note)

    def _calc_delete(self, channel: Channel) -> None:
        dataset = self.calc_dataset
        users = formula.dependents(dataset, channel.name)
        if users:
            dpg.set_value(self.calc_status, t("{name} wird noch verwendet von: {users}. Erst diese löschen oder ändern.",
                                              name=channel.name, users=", ".join(c.name for c in users)))
            return
        if channel in dataset.channels:
            dataset.channels.remove(channel)
            self.layout.remove(channel)
            self._layout_changed()
            self._refresh_channel_list()
        self._calc_edit(None)
        dpg.set_value(self.calc_status, t("{name} gelöscht.", name=channel.name))

    # ---------------------------------------------------------------- Definitionsdateien (*.def)
    def _build_def_window(self) -> None:
        heading = themes.color(self.mode, "heading")
        with dpg.window(tag="def_window", label=t("Berechnungen speichern"), modal=True, show=False, width=640,
                        height=380, no_collapse=True):
            self.def_info = dpg.add_text("", wrap=610, color=heading)
            self._colour(self.def_info, "heading")
            with dpg.group(horizontal=True):
                dpg.add_text(t("Titel"))
                self.def_title = dpg.add_input_text(width=-1)
            with dpg.group(horizontal=True):
                dpg.add_text(t("Erstellt von"))
                self.def_author = dpg.add_input_text(width=-1)
            dpg.add_text(t("Bemerkung"))
            self.def_comment = dpg.add_input_text(multiline=True, width=-1, height=80)
            with dpg.group(horizontal=True):
                dpg.add_text(t("Datei"))
                self.def_path = dpg.add_input_text(width=-1)
            self.def_status = dpg.add_text("", wrap=610)
            with dpg.group(horizontal=True):
                dpg.add_button(label=t("Speichern"), callback=self._save_definitions)
                dpg.add_button(label=t("Abbrechen"), callback=lambda: dpg.configure_item("def_window", show=False))

    def _open_def_window(self, *_args) -> None:
        with_calc = [d for d in self.datasets if formula.computed(d)]
        if not with_calc:
            self._message(t("Es gibt noch keine berechneten Signale."))
            if dpg.does_item_exist("calc_window") and dpg.get_item_configuration("calc_window").get("show"):
                dpg.set_value(self.calc_status, t("Es gibt noch keine berechneten Signale."))
            return
        if dpg.get_item_configuration("calc_window").get("show"):   # aus dem Rechendialog: erst schließen
            dpg.configure_item("calc_window", show=False)
            self._later(self._open_def_window)
            return
        count = sum(len(formula.computed(d)) for d in with_calc)
        dpg.set_value(self.def_info, t("{count} berechnete Signale aus {files} Datei(en): Messdatei mit Pfad, Formeln, "
                                       "Einheiten und Bemerkungen.", count=count, files=len(with_calc)))
        meta = self.settings.get("definition", {})
        dpg.set_value(self.def_title, meta.get("title", ""))
        dpg.set_value(self.def_author, meta.get("author", self.settings.get("export", {}).get("author", "")))
        dpg.set_value(self.def_comment, meta.get("comment", ""))
        default = meta.get("path") or str(Path(with_calc[0].path).with_name("MessGraph_Berechnungen.def"))
        dpg.set_value(self.def_path, default)
        dpg.set_value(self.def_status, "")
        width, height = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
        dpg.configure_item("def_window", show=True, pos=[max(0, (width - 640) // 2), max(0, (height - 380) // 2)])

    def _save_definitions(self, *_args) -> None:
        path = os.path.expanduser(dpg.get_value(self.def_path).strip())
        if not path:
            dpg.set_value(self.def_status, t("Bitte einen Dateinamen angeben."))
            return
        title, author = dpg.get_value(self.def_title).strip(), dpg.get_value(self.def_author).strip()
        comment = dpg.get_value(self.def_comment).strip()
        target = path if path.lower().endswith(definitions.SUFFIX) else path + definitions.SUFFIX
        data = definitions.build(self.datasets, title, comment, author, os.path.dirname(os.path.abspath(target)))
        try:
            written = definitions.write(target, data)
        except LoadError as exc:
            dpg.set_value(self.def_status, str(exc))
            return
        self.settings["definition"] = {"title": title, "author": author, "comment": comment, "path": written}
        self._save_settings()
        dpg.configure_item("def_window", show=False)
        self._message(t("Berechnungen gespeichert: {path}", path=written))

    def _ask_load_definitions(self, *_args) -> None:
        if dpg.does_item_exist("calc_window") and dpg.get_item_configuration("calc_window").get("show"):
            dpg.configure_item("calc_window", show=False)
            self._later(lambda: self._show_file_browser("definition", self._load_definitions,
                                                        "Berechnungen laden (*.def)..."))
            return
        self._show_file_browser("definition", self._load_definitions, "Berechnungen laden (*.def)...")

    def _load_definitions(self, paths: list[str]) -> None:
        """Definitionen lesen, Ziele vorschlagen; gibt es eine Wahl, erst den Auswahldialog zeigen."""
        plans, problems = [], []
        for path in [p for p in paths if p]:
            try:
                data, targets = definitions.plan(path, self.datasets)
            except LoadError as exc:
                problems.append(f"{Path(path).name}: {exc}")
                continue
            plans.append((path, data, targets))
        if not plans:
            self._message(t("Berechnungen nicht geladen: {error}", error="; ".join(problems) or "-"))
            return
        self.def_plans, self.def_problems = plans, problems
        if any(target.matches for _p, _d, targets in plans for target in targets):
            self._open_def_load_window()
        else:
            self._run_definitions()

    def _build_def_load_window(self) -> None:
        with dpg.window(tag="def_load_window", label=t("Berechnungen laden"), modal=True, show=False, width=700,
                        height=460, no_collapse=True):
            dpg.add_text(t("Auf welche Dateien sollen die Formeln angewendet werden?"))
            self.def_load_area = dpg.add_child_window(height=-40, border=True)
            with dpg.group(horizontal=True):
                dpg.add_button(label=t("Übernehmen"), callback=lambda: (dpg.configure_item("def_load_window", show=False),
                                                                          self._run_definitions()))
                dpg.add_button(label=t("Abbrechen"), callback=lambda: dpg.configure_item("def_load_window", show=False))

    def _open_def_load_window(self) -> None:
        heading, dim = themes.color(self.mode, "heading"), themes.color(self.mode, "text_dim")
        dpg.delete_item(self.def_load_area, children_only=True)
        area = self.def_load_area
        for path, data, targets in self.def_plans:
            self._colour(dpg.add_text(data.get("title") or Path(path).name, color=heading, parent=area), "heading")
            if data.get("comment"):
                self._colour(dpg.add_text(data["comment"], color=dim, wrap=640, parent=area), "text_dim")
            entries = data.get("files", [])
            for target in targets:
                count = len(entries[target.index].get("computed", []))
                dpg.add_text(t("Formeln für {name} ({count} Signale):", name=target.stored_name, count=count), parent=area)
                if target.stored_path:
                    label = (t("{name} (gespeicherte Datei, geöffnet)", name=target.stored_open.name)
                             if target.stored_open else
                             t("{path} (gespeicherte Datei, wird geöffnet)", path=target.stored_path))
                    dpg.add_checkbox(label=label, default_value=target.use_stored, parent=area,
                                     callback=lambda s_, v, u: setattr(u, "use_stored", bool(v)), user_data=target)
                else:
                    self._colour(dpg.add_text(t("{name}: gespeicherte Datei nicht gefunden", name=target.stored_name),
                                              color=dim, parent=area), "text_dim")
                for dataset in target.matches:
                    dpg.add_checkbox(label=t("{name} (geöffnet, passende Signale)", name=dataset.name),
                                     default_value=dataset in target.use, parent=area,
                                     callback=self._def_toggle_target, user_data=(target, dataset))
                dpg.add_spacer(height=4, parent=area)
        width, height = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
        dpg.configure_item("def_load_window", show=True, pos=[max(0, (width - 700) // 2), max(0, (height - 460) // 2)])

    def _def_toggle_target(self, _sender, value, user_data) -> None:
        target, dataset = user_data
        if value and dataset not in target.use:
            target.use.append(dataset)
        elif not value and dataset in target.use:
            target.use.remove(dataset)

    def _run_definitions(self) -> None:
        self.pending += 1
        self._message(t("Berechnungen werden geladen..."))
        self.pool.submit(self._def_worker, list(self.def_plans), list(self.datasets),
                         self._start_job(t("Berechnungen laden")))

    def _def_worker(self, plans, loaded, job=None) -> None:
        results, problems = [], list(getattr(self, "def_problems", []))
        try:
            with progress.track(job):
                for number, (path, _data, targets) in enumerate(plans):
                    with progress.section(number / len(plans), (number + 1) / len(plans)):
                        try:
                            result = definitions.apply(path, loaded, load_file, targets)
                        except progress.Cancelled:
                            raise
                        except LoadError as exc:
                            problems.append(f"{Path(path).name}: {exc}")
                            continue
                        loaded += result.new_datasets
                        results.append((path, result))
            self.results.put(("definitions", results, problems, None))
        except progress.Cancelled:
            self.results.put(("definitions", results, problems, CANCELLED))
        except Exception as exc:
            log_exception(t("Berechnungen laden"), exc)
            self.results.put(("definitions", results, problems, f"{type(exc).__name__}: {exc}"))

    def _definitions_done(self, results, problems, error) -> None:
        self.pending -= 1
        if error == CANCELLED:
            for _path, result in results:
                for dataset in result.new_datasets:
                    dataset.close()
            self._message(t("Laden der Berechnungen abgebrochen."))
            return
        if error:
            self._message(t("Berechnungen nicht geladen: {error}", error=error))
            return
        count, titles = 0, []
        for path, result in results:
            for dataset in result.new_datasets:
                twin = next((d for d in self.datasets if definitions.same_path(d.path, dataset.path)), None)
                if twin is not None:   # inzwischen anders geöffnet: Formeln dorthin, Datei nicht doppelt
                    result.assignments = [(twin if d is dataset else d, c, {} if d is dataset else p)
                                          for d, c, p in result.assignments]
                    dataset.close()
                    continue
                self.datasets.append(dataset)
            count += definitions.install(result)
            problems += result.problems
            titles.append(result.title or Path(path).name)
            if result.title or result.comment:
                self.settings["definition"] = dict(self.settings.get("definition", {}), title=result.title,
                                                   comment=result.comment, path=path)
        self.datasets.sort(key=lambda d: d.name.lower())
        self._save_settings()
        self._refresh_channel_list()
        self._layout_changed()
        text = t("{count} berechnete Signale geladen ({names}).", count=count, names=", ".join(titles))
        if not count and not problems:
            problems = [t("Die Definition enthält keine Formeln.")]
        if problems:
            text += " " + t("Hinweis: {text}", text="; ".join(problems[:4]))
        self._message(text)

    # ---------------------------------------------------------------- Drucken, Export, Report
    def _build_export_window(self) -> None:
        heading = themes.color(self.mode, "heading")
        with dpg.window(tag="export_window", label=t("Drucken und Export"), modal=True, show=False, width=620,
                        height=470, no_collapse=True):
            self.exp_heading = dpg.add_text("", color=heading)
            self._colour(self.exp_heading, "heading")
            with dpg.group() as self.exp_print_group:
                dpg.add_text(t("Ausgabe"))
                self.exp_target = dpg.add_radio_button(items=[t(TARGET_NAMES[k]) for k in plotexport.TARGETS],
                                                       horizontal=True, callback=self._exp_target_changed)
                with dpg.group(horizontal=True):
                    dpg.add_text(t("Ausrichtung"))
                    self.exp_orient = dpg.add_combo(items=[t(ORIENT_NAMES[k]) for k in plotexport.ORIENTATIONS],
                                                    width=150)
            with dpg.group() as self.exp_report_group:
                with dpg.group(horizontal=True):
                    dpg.add_text(t("Report"))
                    self.exp_format = dpg.add_radio_button(items=[t(REPORT_FORMAT_NAMES[k]) for k in REPORT_FORMATS],
                                                           horizontal=True)
                self._tooltip(self.exp_format, t("Dynamisch: HTML-Datei für den Browser. Klick auf Kurve, Signalspiegel "
                                                 "oder Tabellenzeile hebt das Signal hervor, alles andere wird hellgrau."))
                with dpg.group(horizontal=True):
                    dpg.add_text(t("Titel"))
                    self.exp_title = dpg.add_input_text(width=-1)
                with dpg.group(horizontal=True):
                    dpg.add_text(t("Erstellt von"))
                    self.exp_author = dpg.add_input_text(width=-1)
                dpg.add_text(t("Werte in der Signaltabelle (keiner gewählt: keine Signaltabellen)"))
                with dpg.group(horizontal=True) as self.exp_stat_row:
                    self.exp_stats = {key: dpg.add_checkbox(label=t(label), default_value=True)
                                      for key, _head, label in REPORT_STATS}
                self._tooltip(self.exp_stat_row, t("Nur die gewählten Angaben erscheinen in den Signaltabellen des Reports."))
                dpg.add_text(t("Allgemeine Bemerkung"))
                self.exp_comment = dpg.add_input_text(multiline=True, width=-1, height=70,
                                                      callback=self._exp_comment_changed)
                dpg.add_text(t("Bemerkung je Graph"))
                self.exp_graph_notes = dpg.add_child_window(width=-1, height=200, border=True)
            with dpg.group(horizontal=True):
                dpg.add_text(t("Papier"))
                self.exp_paper = dpg.add_combo(items=list(plotexport.PAPER), width=80)
                self._tooltip(self.exp_paper, t("DIN-Format; die Graphen werden auf die Seite verteilt."))
            with dpg.group(horizontal=True) as self.exp_path_row:
                dpg.add_text(t("Datei"))
                self.exp_path = dpg.add_input_text(width=-1)
            self.exp_status = dpg.add_text("", wrap=590)
            with dpg.group(horizontal=True):
                self.exp_run_btn = dpg.add_button(label=t("Ausführen"), callback=self._exp_run)
                dpg.add_button(label=t("Abbrechen"), callback=lambda: dpg.configure_item("export_window", show=False))

    def _open_export(self, mode: str, slot: GraphSlot | None = None, zoom: bool = False) -> None:
        if dpg.get_item_configuration("ctx_menu").get("show"):   # aus dem Kontextmenü: erst schließen
            self._close_context_menu()
            self._later(lambda: self._open_export(mode, slot, zoom))
            return
        self.exp_zoom = zoom      # aus dem Detailfenster: dessen sichtbarer Ausschnitt
        if not any(s.signals for s in self.layout.slots):
            self._message(t("Kein Graph mit Signalen vorhanden."))
            return
        self.exp_mode, self.exp_slot = mode, slot
        cfg = self.settings.get("export", {})
        report = mode == "report"
        if mode == "one" and slot in self.layout.slots:
            name = slot.display_name(self.layout.slots.index(slot))
            dpg.set_value(self.exp_heading, t("Graph drucken / exportieren: {name}", name=name))
        elif mode == "all":
            dpg.set_value(self.exp_heading, t("Alle Graphen drucken / exportieren"))
        else:
            dpg.set_value(self.exp_heading, t("Report als PDF: Deckblatt, Inhaltsverzeichnis, je Graph Grafik und Messwerte"))
        dpg.configure_item(self.exp_print_group, show=not report)
        dpg.configure_item(self.exp_report_group, show=report)
        if report:
            fmt_key = cfg.get("report_format", "both")
            dpg.set_value(self.exp_format, t(REPORT_FORMAT_NAMES.get(fmt_key, REPORT_FORMAT_NAMES["both"])))
            chosen = set(cfg.get("report_stats", [k for k, _h, _l in REPORT_STATS]))
            for key, box in self.exp_stats.items():
                dpg.set_value(box, key in chosen)
            dpg.set_value(self.exp_comment, self.report_comment)
            dpg.delete_item(self.exp_graph_notes, children_only=True)
            for index, slot_ in enumerate(self.layout.slots):
                if slot_.signals:
                    dpg.add_text(slot_.display_name(index), parent=self.exp_graph_notes)
                    dpg.add_input_text(multiline=True, width=-1, height=46, default_value=slot_.note,
                                       parent=self.exp_graph_notes, callback=self._exp_note_changed, user_data=slot_)
        dpg.set_value(self.exp_target, t(TARGET_NAMES[cfg.get("target", "pdf")]))
        dpg.set_value(self.exp_orient, t(ORIENT_NAMES[cfg.get("orientation", "auto")]))
        dpg.set_value(self.exp_paper, cfg.get("paper", "A4"))
        dpg.set_value(self.exp_author, cfg.get("author", ""))
        if not dpg.get_value(self.exp_title):
            dpg.set_value(self.exp_title, t("Messbericht"))
        dpg.set_value(self.exp_status, "")
        dpg.configure_item(self.exp_run_btn, label=t("Report erstellen") if report else t("Ausführen"))
        self._exp_target_changed()
        width, height = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
        win_h = min(770 if report else 470, max(300, height - 20))
        dpg.configure_item("export_window", show=True, height=win_h,
                           pos=[max(0, (width - 620) // 2), max(0, (height - win_h) // 2)])

    def _exp_comment_changed(self, _sender, value) -> None:
        self.report_comment = str(value)

    def _exp_note_changed(self, _sender, value, slot: GraphSlot) -> None:
        slot.note = str(value)

    def _exp_choice(self) -> tuple[str, str]:
        targets = {t(TARGET_NAMES[k]): k for k in plotexport.TARGETS}
        orients = {t(ORIENT_NAMES[k]): k for k in plotexport.ORIENTATIONS}
        return targets.get(dpg.get_value(self.exp_target), "pdf"), orients.get(dpg.get_value(self.exp_orient), "auto")

    def _exp_target_changed(self, *_args) -> None:
        target, _ = self._exp_choice()
        report = self.exp_mode == "report"
        dpg.configure_item(self.exp_path_row, show=report or target != "printer")
        suffix = ".pdf" if report or target != "svg" else ".svg"
        base = self.datasets[0].path if self.datasets else str(Path.home() / "x")
        stem = {"one": "MessGraph_Graph", "all": "MessGraph_Graphen", "report": "MessGraph_Report"}[self.exp_mode]
        current = dpg.get_value(self.exp_path).strip()
        if current and Path(current).suffix.lower() in (".pdf", ".svg"):
            dpg.set_value(self.exp_path, str(Path(current).with_suffix(suffix)))
        else:
            dpg.set_value(self.exp_path, str(Path(base).with_name(stem + suffix)))

    def _plot_spec(self, ui: SlotUI, index: int) -> plotexport.PlotSpec:
        """Sichtbarer Ausschnitt eines Graphen als Vektorbeschreibung (Druckfarben der hellen Darstellung)."""
        slot = ui.slot

        def limits(axis, fallback):
            if axis is None:
                return None
            lo, hi = (float(v) for v in dpg.get_axis_limits(axis))
            return (lo, hi) if np.isfinite(lo) and np.isfinite(hi) and hi > lo else fallback
        span = self._data_range(ui) or (0.0, 1.0)
        ys = [c.y[np.isfinite(c.y)] for c in slot.signals if c.y is not None and c not in slot.right]
        yr = (min(float(v.min()) for v in ys if v.size), max(float(v.max()) for v in ys if v.size)) \
            if any(v.size for v in ys) else (0.0, 1.0)
        series = []
        for position, channel in enumerate(slot.signals):
            if channel.x is None:
                continue
            rgb = tuple(slot.colors.get(channel) or themes.series_color(themes.LIGHT, position))
            label = ui.labels.get(channel, channel.label)
            series.append(plotexport.SeriesSpec(label, channel.x + self._offset(ui, channel), channel.y, rgb,
                                                channel in slot.right and ui.y2_axis is not None, key=f"s{position}",
                                                bars=getattr(channel, "plot_style", "line") == "bar"))
        markers = []
        if self.cross_on:
            for k, c in enumerate(slot.cross):
                if c is not None:
                    markers.append((float(c), f"M{k + 1}", themes.color(themes.LIGHT, "cross")[k]))
        lines = []
        for position, channel in enumerate(slot.signals):
            rgb = tuple(slot.colors.get(channel) or themes.series_color(themes.LIGHT, position))
            for value in self._limits_for(slot, channel):
                if value is not None and self.cross_on:
                    lines.append((value, rgb, channel in slot.right and ui.y2_axis is not None, f"s{position}"))
        x_label, y_label = self._axis_labels(slot, ui.time_axis)
        right = [c for c in slot.signals if c in slot.right]
        return plotexport.PlotSpec(
            title=slot.display_name(index), xlim=limits(ui.x_axis, span), ylim=limits(ui.y_axis, yr),
            y2lim=limits(ui.y2_axis, yr) if ui.y2_axis is not None else None, series=series, markers=markers,
            limits=lines, xlabel=x_label, ylabel=y_label, y2label=self._unit_label(right) if right else "",
            time_axis=ui.time_axis, legend=slot.legend if slot.legend in LEGEND_LOCATIONS else LEGEND_DEFAULT,
            comments=[(x + self._comment_base(ui), y, text) for x, y, text in slot.comments],
            alarm=any((self._violation(ui, c) or (False,))[0] for c in slot.signals),
            regressions=self._spec_regressions(ui), log_x=bool(slot.log_x and not ui.time_axis),
            log_y=bool(slot.log_y))

    def _export_font(self, texts) -> str | None:
        """Schrift für das PDF: Thai-Schrift auf Thai, sonst die Oberflächenschrift, wenn Helvetica nicht reicht."""
        if self.lang in i18n.SCRIPT_LANGUAGES and self._lang_font_path(self.lang) != self.ui_font_path:
            return self._lang_font_path(self.lang)
        try:
            "".join(texts).encode("cp1252")
        except UnicodeEncodeError:
            return self.ui_font_path
        return None

    def _export_header(self) -> str:
        names = ", ".join(d.name for d in self.datasets[:4]) + (" ..." if len(self.datasets) > 4 else "")
        return f"MessGraph  |  {names}  |  {time.strftime('%d.%m.%Y %H:%M')}"

    def _exp_run(self, *_args) -> None:
        target, orientation = self._exp_choice()
        paper = dpg.get_value(self.exp_paper) or "A4"
        cfg = dict(self.settings.get("export", {}), paper=paper, orientation=orientation,
                   author=dpg.get_value(self.exp_author).strip())
        if self.exp_mode != "report":
            cfg["target"] = target
        else:
            cfg["report_stats"] = self._exp_selected_stats()
            cfg["report_format"] = self._exp_report_format()
        self.settings["export"] = cfg
        self._save_settings()
        path = os.path.expanduser(dpg.get_value(self.exp_path).strip())
        try:
            if self.exp_mode == "report":
                text = self._write_report(path, paper)
            else:
                text = self._write_graphs(target, path, paper, orientation)
        except (OSError, ValueError, LoadError) as exc:
            log_exception(t("Drucken und Export"), exc)
            dpg.set_value(self.exp_status, t("Fehler: {error}", error=exc))
            return
        dpg.configure_item("export_window", show=False)
        self._message(text)

    def _export_specs(self) -> tuple[list, tuple]:
        self.exp_spans = None
        if self.exp_mode == "one":
            if self.exp_zoom and self.zoom_ui is not None and self.zoom_ui.slot is self.exp_slot:
                return [self._plot_spec(self.zoom_ui, self.layout.slots.index(self.exp_slot))], (1, 1)
            for index, ui in enumerate(self.slot_ui):
                if ui.slot is self.exp_slot:
                    return [self._plot_spec(ui, index)], (1, 1)
            raise ValueError(t("Der Graph ist nicht mehr vorhanden."))
        uis = [(i, ui) for i, ui in enumerate(self.slot_ui) if ui.slot.signals]
        rows, cols = self.layout.grid()
        complete = self.layout.matrix and len(uis) == len(self.slot_ui)
        cols = cols if complete else 1
        self.exp_spans = self.layout.spans if complete and self.layout.spans else None   # zusammengefasste Bereiche
        return [self._plot_spec(ui, i) for i, ui in uis], (-(-len(uis) // cols), cols)

    def _write_graphs(self, target: str, path: str, paper: str, orientation: str) -> str:
        specs, grid = self._export_specs()
        texts = [s.title for s in specs] + [x.label for s in specs for x in s.series] + [self._export_header()]
        if target == "svg":
            files = plotexport.write_svg(path, specs, grid, paper, orientation, self._export_header(),
                                         spans=getattr(self, "exp_spans", None))
            return t("SVG gespeichert: {path}", path=", ".join(files))
        if target == "pdf":
            written = plotexport.write_pdf(path, specs, grid, paper, orientation, "MessGraph", self._export_header(),
                                           font_path=self._export_font(texts), spans=getattr(self, "exp_spans", None))
            return t("PDF gespeichert: {path}", path=written)
        temp = os.path.join(tempfile.gettempdir(), "MessGraph_Druck.pdf")
        plotexport.write_pdf(temp, specs, grid, paper, orientation, "MessGraph", self._export_header(),
                             font_path=self._export_font(texts), spans=getattr(self, "exp_spans", None))
        try:
            way = plotexport.print_file(temp)
        except OSError as exc:
            raise OSError(t("Drucken nicht möglich ({error}). Das PDF liegt unter {path}.", error=exc, path=temp)) from exc
        return t("An den Drucker gesendet ({way}).", way=way)

    def _exp_report_format(self) -> str:
        names = {t(REPORT_FORMAT_NAMES[k]): k for k in REPORT_FORMATS}
        return names.get(dpg.get_value(self.exp_format), "both")

    def _exp_selected_stats(self) -> list[str]:
        return [key for key, _h, _l in REPORT_STATS if dpg.get_value(self.exp_stats[key])]

    def _write_report(self, path: str, paper: str) -> str:
        data = self._report_data(dpg.get_value(self.exp_title).strip() or t("Messbericht"),
                                 dpg.get_value(self.exp_author).strip(), dpg.get_value(self.exp_comment).strip(),
                                 self._exp_selected_stats())
        texts = [data.title, data.author, data.comment] + [g.title for g in data.graphs] + \
                [cell for g in data.graphs for _h, _c, rows in g.tables for row in rows for cell in row]
        kind = self._exp_report_format()
        base = path[:-len(Path(path).suffix)] if Path(path).suffix.lower() in (".pdf", ".html", ".htm") else path
        written = []
        if kind in ("both", "pdf"):
            written.append(report.build_report(base + ".pdf", data, paper, font_path=self._export_font(texts)))
        if kind in ("both", "html"):
            lang = {"English": "en", "Thai": "th", "Chinese": "zh"}.get(i18n.language(), "de")
            written.append(report_html.build_html_report(base + ".html", data, lang))
        return t("Report gespeichert: {path}", path=", ".join(written))

    def _report_data(self, title: str, author: str, comment: str, stats: list[str] | None = None) -> report.ReportData:
        """stats: Werte der Signaltabelle (min, max, avg, drift); leer = keine Signaltabellen."""
        stats = [k for k, _h, _l in REPORT_STATS] if stats is None else [k for k, _h, _l in REPORT_STATS if k in stats]
        files = []
        for ds in self.datasets:
            epoch = next((c.x_epoch for c in ds.channels if c.x_epoch is not None), None)
            files.append((ds.name, str(Path(ds.path).parent), len(ds.channels),
                          format_wallclock(epoch)[:19] if epoch is not None else "-", Path(ds.path).suffix[1:].upper()))
        yes, no = t("ein"), t("aus")
        settings = [(t("Downsampling"), downsample.config().describe().split(": ", 1)[-1]),
                    (t("Marker"), yes if self.cross_on else no),
                    (t("Datum/Uhrzeit-Achse"), yes if self.date_axis else no),
                    (t("X-Achsen koppeln"), yes if self.link_x else no)]
        settings.append((t("Drift-Regression"), f"({self._reg_number()}) " + t(REG_METHODS[self.reg_method])))
        if self.limit_cfg is not None:
            spec = self._mode_spec()
            steps = f", steps {spec.steps_text()}" if spec is not None and spec.steps_text() else ""
            settings.append((t("Grenzwert-Konfiguration"), f"{self.limit_cfg.name}, " + (
                t("Mode: {name}", name=self.cfg_mode) if self.cfg_mode else t("kein Mode (manuelle Werte)")) + steps))
        graphs = []
        for index, ui in enumerate(self.slot_ui):
            if not ui.slot.signals:
                continue
            # Report (PDF und HTML): Y-Achsen mit mindestens 10 % Abstand über/unter den dargestellten Werten
            spec = plotexport.with_report_margins(self._plot_spec(ui, index))
            signal_rows, marker_rows, limit_rows, notes = [], [], [], []
            signal_keys, marker_keys, limit_keys, alarm_keys = [], [], [], set()
            for position, channel in enumerate(ui.slot.signals):
                if channel.y is None:
                    continue
                key = f"s{position}"
                slope = self._regression(channel)
                xu = channel.x_unit if not ui.time_axis else "s"
                if stats:
                    values = compare.statistics(channel.y)
                    row = [channel.label, Path(channel.source).name, channel.unit or "-"]
                    for stat in stats:
                        if stat == "drift":
                            row.append(fmt(slope, drift_unit(channel.unit, xu)) if np.isfinite(slope) else "-")
                        else:
                            row.append(fmt(values[stat], channel.unit) if values[stat] is not None else "-")
                    signal_rows.append(row)
                    signal_keys.append(key)
                if self.cross_on:
                    marker_rows.append([channel.label] + self._measure_values(ui, channel))
                    marker_keys.append(key)
                lo, hi = self._limits_for(ui.slot, channel)
                state = self._violation(ui, channel, slope)
                if state is not None and state[0]:
                    alarm_keys.add(key)
                if lo is not None or hi is not None:
                    status = "-" if state is None else (t("verletzt") if state[0] else t("eingehalten"))
                    limit_rows.append([channel.label, "-" if lo is None else fmt(lo, channel.unit),
                                       "-" if hi is None else fmt(hi, channel.unit),
                                       self._target_text(ui.slot, channel) or "-",
                                       self._prediction_text(ui, channel, slope), status])
                    limit_keys.append(key)
                if channel.ds_note:
                    notes.append(f"{channel.label}: {channel.ds_note}")
            heads = {k: h for k, h, _l in REPORT_STATS}
            heads["drift"] = self._drift_label()          # mit Nummer der gewählten Regression
            tables = [(t("Signale"), [t("Signal"), t("Datei"), t("Einheit")] + [t(heads[k]) for k in stats],
                       signal_rows)] if stats else []
            row_keys = [signal_keys] if stats else []
            tables += [(t("Marker-Messung"), [t("Signal"), "X1", "X2", t("Wert 1"), t("Wert 2"), t("Delta X"),
                                             t("Delta Y"), t("Drift")], marker_rows),
                      (t("Grenzen und Prognose"), [t("Signal"), t("Y min"), t("Y max"), t("Zielzeit"), t("Prognose"),
                                                    t("Zielzeit-Status")], limit_rows)]
            row_keys += [marker_keys, limit_keys]
            graphs.append(report.GraphSection(spec.title, spec, tables, notes, ui.slot.note, row_keys, alarm_keys))
        return report.ReportData(title, author, comment, time.strftime("%d.%m.%Y %H:%M"), files, settings, graphs)

    # ---------------------------------------------------------------- Legendenposition (rechte Maustaste)
    def _legend_hovered(self, slot: GraphSlot) -> bool:
        ui = self._ui_for(slot)
        if ui is None or ui.legend is None:
            return False
        try:
            return bool(dpg.is_item_hovered(ui.legend))
        except Exception:  # Legende meldet bei manchen Versionen keinen Hover-Zustand
            return False

    def _add_legend_choices(self, slot: GraphSlot, menu) -> None:
        current = slot.legend if slot.legend in LEGEND_LOCATIONS else LEGEND_DEFAULT
        self.ctx_legend_items = {}
        for row in (LEGEND_ORDER[:3], LEGEND_ORDER[3:]):
            with dpg.group(horizontal=True, parent=menu):
                for key in row:
                    mark = "» " if key == current else "   "
                    self.ctx_legend_items[key] = dpg.add_selectable(
                        label=mark + t(LEGEND_NAMES[key]), width=(MENU_WIDTH - 30) // 3,
                        callback=lambda s_, a_, u_: self._set_legend(*u_), user_data=(slot, key))

    def _open_legend_menu(self, slot: GraphSlot, pos) -> None:
        """Rechtsklick auf die Legende: nur die Wahl der Position."""
        menu = "ctx_menu"
        dpg.delete_item(menu, children_only=True)
        self.ctx_slot = slot
        index = self.layout.slots.index(slot)
        heading = themes.color(self.mode, "heading")
        dpg.add_text(t("Legende: {name}", name=slot.display_name(index)), parent=menu, color=heading)
        dpg.add_separator(parent=menu)
        self._add_legend_choices(slot, menu)
        dpg.add_separator(parent=menu)
        dpg.add_selectable(label=t("Schließen"), parent=menu, callback=self._close_context_menu)
        width, height = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
        dpg.configure_item(menu, show=True, pos=[int(min(pos[0], width - MENU_WIDTH - 10)), int(min(pos[1], height - 160))])

    def _set_legend(self, slot: GraphSlot, key: str) -> None:
        slot.legend = key
        for ui in self._all_ui():
            if ui.slot is slot and ui.legend is not None and dpg.does_item_exist(ui.legend):
                dpg.configure_item(ui.legend, location=getattr(dpg, LEGEND_LOCATIONS[key]))
        self._close_context_menu()

    def _add_y2_axis(self, plot, label: str, log: bool = False):
        """Sekundäre Y-Achse am rechten Rand (Dear PyGui 2.x: mvYAxis2; 1.x: zweite mvYAxis liegt rechts)."""
        axis_type = getattr(dpg, "mvYAxis2", dpg.mvYAxis)
        kwargs = dict(label=label, parent=plot, payload_type=PAYLOAD, drop_callback=self._on_drop)
        if log:
            kwargs.update(self._log_kwargs())
        if hasattr(dpg, "mvYAxis2"):
            kwargs["opposite"] = True
        try:
            return dpg.add_plot_axis(axis_type, **kwargs)
        except Exception:  # ältere Versionen ohne "opposite"
            kwargs.pop("opposite", None)
            return dpg.add_plot_axis(axis_type, **kwargs)

    @staticmethod
    def _unit_label(channels) -> str:
        units = {c.unit for c in channels}
        unit = units.pop() if len(units) == 1 else ""
        return f"[{unit}]" if unit else ""

    def _axis_labels(self, slot: GraphSlot, time_axis: bool = False) -> tuple[str, str]:
        if not slot.signals:
            return "", ""
        first = slot.signals[0]
        if time_axis:
            x_label = t("Datum/Uhrzeit")
        else:
            x_label = f"{first.x_name} [{first.x_unit}]" if first.x_unit else first.x_name
        left = [c for c in slot.signals if c not in slot.right] or slot.signals
        return x_label, self._unit_label(left)

    def _poll_link(self) -> None:
        """X-Achsen über die Zeilen koppeln, wenn Bereiche zusammengefasst sind (je Zeile eigene Subplots).

        Ändert sich der sichtbare Bereich eines Graphen (Zoom, Verschieben), übernehmen die anderen Graphen mit
        gleicher Achsenart diesen Bereich; im nächsten Bild werden ihre Achsen wieder freigegeben.
        """
        if not (self.link_x and ((self.row_subplots and len(self.row_subplots) > 1) or getattr(self, "manual_link", False))):
            return
        for axis in self.link_release:
            if dpg.does_item_exist(axis):
                dpg.set_axis_limits_auto(axis)
        self.link_release = []
        current = {}
        for ui in self.slot_ui:
            if ui.fourier:                                 # Fourier-Graphen: eigene X-Achse, nie gekoppelt
                continue
            limits = tuple(float(v) for v in dpg.get_axis_limits(ui.x_axis))
            if len(limits) == 2 and all(np.isfinite(limits)) and limits[1] > limits[0]:
                current[ui] = limits
        if self.link_settle > 0:        # Graphen bauen sich auf, Achsen passen sich noch an
            self.link_settle -= 1
            self.link_last = {ui.x_axis: lim for ui, lim in current.items()}
            return
        changed = [ui for ui, lim in current.items()
                   if ui.x_axis in self.link_last and lim != self.link_last[ui.x_axis]]
        if changed:
            source = changed[0]
            limits = current[source]
            for ui in self.slot_ui:
                if ui is source or ui.fourier or ui.time_axis != source.time_axis or current.get(ui) == limits:
                    continue
                dpg.set_axis_limits(ui.x_axis, limits[0], limits[1])
                self.link_release.append(ui.x_axis)
                current[ui] = limits
        self.link_last = {ui.x_axis: lim for ui, lim in current.items()}

    def _fit_all(self) -> None:
        for ui in self.slot_ui:
            dpg.fit_axis_data(ui.x_axis)
            self._fit_y(ui)

    # ---------------------------------------------------------------- Y-Achse mit Rand (wie im Report)
    Y_HOLD_FRAMES = 3                 # so viele Bilder bleibt der Bereich fest, danach ist die Achse wieder frei

    def _y_extent(self, ui: SlotUI, right: bool) -> tuple[float, float] | None:
        """Kleinster und größter Wert der Signale einer Y-Achse (sichtbare Grenzlinien zählen mit)."""
        lo, hi = np.inf, -np.inf
        for channel in ui.slot.signals:
            if (channel in ui.slot.right and ui.y2_axis is not None) != right or channel.y is None:
                continue
            y = np.asarray(channel.y, dtype=np.float64)
            y = y[np.isfinite(y)]
            if y.size:
                lo, hi = min(lo, float(y.min())), max(hi, float(y.max()))
            if self.cross_on:
                for value in self._limits_for(ui.slot, channel):
                    if value is not None and np.isfinite(value):
                        lo, hi = min(lo, float(value)), max(hi, float(value))
        return (lo, hi) if np.isfinite(lo) and np.isfinite(hi) else None

    def _fit_y(self, ui: SlotUI) -> None:
        """Y max = größter Wert + 10 % (bei positiven Werten max * 1,1), Y min = kleinster Wert - 10 %
        (bei positiven Werten min * 0,9); je Achse über alle Signale des Graphen. Ist ein Wert 0, gelten 10 %
        der Spannweite. Der Bereich wird gesetzt und nach wenigen Bildern freigegeben (Zoomen bleibt möglich)."""
        if not hasattr(self, "y_release"):
            self.y_release = {}
        for axis, right in ((ui.y_axis, False), (ui.y2_axis, True)):
            if axis is None:
                continue
            extent = self._y_extent(ui, right)
            if extent is None:
                dpg.fit_axis_data(axis)
                continue
            lo, hi = plotexport.value_margin(*extent)
            dpg.set_axis_limits(axis, lo, hi)
            self.y_release[axis] = self.Y_HOLD_FRAMES

    # ---------------------------------------------------------------- Mausrad an der rechten Y-Achse
    Y2_ZOOM_RATE = 0.1                # wie ImPlot: je Rastung 10 % enger bzw. weiter

    def _snapshot_y2(self) -> None:
        """Bereich der rechten Y-Achsen vor dem nächsten Bild merken (erkennt, ob ImPlot selbst gezoomt hat)."""
        self.y2_seen = {}
        for ui in self._all_ui():
            if ui.y2_axis is not None and dpg.does_item_exist(ui.y2_axis):
                try:
                    self.y2_seen[ui.y2_axis] = tuple(float(v) for v in dpg.get_axis_limits(ui.y2_axis))
                except Exception:
                    pass

    def _wheel_region(self, ui: SlotUI) -> str | None:
        """Wo steht die Maus im Graphen: "plot" (Zeichenfläche), "y2" (rechte Achse), "y" (linke Achse), "x"."""
        try:
            mx, my = (float(v) for v in dpg.get_mouse_pos(local=False))
            (x0, y0), (x1, y1) = dpg.get_item_rect_min(ui.plot), dpg.get_item_rect_max(ui.plot)
        except Exception:
            return None
        font = float(self.graph_font_size)
        if not (x0 <= mx <= x1 and y0 <= my <= y1):
            return None
        if mx >= x1 - font * 4.2:
            return "y2"
        if mx <= x0 + font * 4.2:
            return "y"
        if my >= y1 - font * 2.8:
            return "x"
        return "plot"

    def _on_wheel(self, _sender, delta, _user_data=None) -> None:
        """Mausrad über der Zeichenfläche oder der rechten Achse zoomt auch die rechte (sekundäre) Y-Achse.

        Manche Dear-PyGui-Versionen zoomen mit dem Mausrad nur die erste Y-Achse. Hat ImPlot die rechte Achse in
        diesem Bild nicht verändert, zoomt MessGraph sie selbst um die Mausposition (sonst nichts, kein Doppelzoom)."""
        ui = self._hovered_ui()
        if ui is None or ui.y2_axis is None or not dpg.does_item_exist(ui.y2_axis):
            return
        try:
            delta = float(delta)
        except (TypeError, ValueError):
            return
        if not delta or self._wheel_region(ui) not in ("plot", "y2"):
            return
        try:
            lo, hi = (float(v) for v in dpg.get_axis_limits(ui.y2_axis))
            y_lo, y_hi = (float(v) for v in dpg.get_axis_limits(ui.y_axis))
        except Exception:
            return
        if hi <= lo or not (np.isfinite(lo) and np.isfinite(hi)):
            return
        seen = getattr(self, "y2_seen", {}).get(ui.y2_axis)
        if seen is not None and (abs(seen[0] - lo) > 1e-12 * max(1.0, abs(lo)) or
                                 abs(seen[1] - hi) > 1e-12 * max(1.0, abs(hi))):
            return                                         # ImPlot hat die Achse schon gezoomt
        center = (lo + hi) / 2
        mouse = self._plot_mouse()
        if mouse is not None and y_hi > y_lo:
            center = lo + (mouse[1] - y_lo) / (y_hi - y_lo) * (hi - lo)
            center = min(max(center, lo), hi)
        factor = (1 - self.Y2_ZOOM_RATE) ** delta         # nach oben drehen: hineinzoomen
        new_lo, new_hi = center - (center - lo) * factor, center + (hi - center) * factor
        if not (np.isfinite(new_lo) and np.isfinite(new_hi)) or new_hi - new_lo <= 1e-12 * max(1.0, abs(center)):
            return
        dpg.set_axis_limits(ui.y2_axis, new_lo, new_hi)
        if not hasattr(self, "y_release"):
            self.y_release = {}
        self.y_release[ui.y2_axis] = 1                     # im übernächsten Bild wieder frei (Ziehen, weiteres Zoomen)
        self.y2_seen[ui.y2_axis] = (new_lo, new_hi)

    def _poll_y2_pan(self) -> None:
        """Verschieben mit gedrückter linker Maustaste auch für die rechte (sekundäre) Y-Achse.

        Über der Zeichenfläche verschiebt ImPlot X und die linke Y-Achse; die rechte folgt um denselben Anteil
        ihres Bereichs. Über der rechten Achse folgt sie der Maus (Pixel -> Achseneinheiten). Verschiebt ImPlot die
        rechte Achse selbst (je nach Dear-PyGui-Version), greift MessGraph für diesen Zug nicht ein. Marker- und
        Kommentarziehen verändern die linke Achse nicht und verschieben daher auch die rechte nicht."""
        pan = getattr(self, "y2_pan", None)
        if not dpg.is_mouse_button_down(dpg.mvMouseButton_Left):
            self.y2_pan = None
            return
        try:
            my = float(dpg.get_mouse_pos(local=False)[1])
        except Exception:
            return
        if pan is None:
            ui = self._hovered_ui()
            if ui is None or ui.y2_axis is None or getattr(self, "comment_drag", None) is not None:
                self.y2_pan = False                       # dieser Zug betrifft die rechte Achse nicht
                return
            region = self._wheel_region(ui)
            if region not in ("plot", "y2"):
                self.y2_pan = False
                return
            try:
                y1 = tuple(float(v) for v in dpg.get_axis_limits(ui.y_axis))
                y2 = tuple(float(v) for v in dpg.get_axis_limits(ui.y2_axis))
            except Exception:
                return
            self.y2_pan = {"ui": ui, "region": region, "y1": y1, "y2": y2, "mouse": my, "own": None}
            return
        if pan is False:
            return
        ui = pan["ui"]
        if ui not in self._all_ui() or not dpg.does_item_exist(ui.y2_axis):
            self.y2_pan = False
            return
        try:
            y1 = tuple(float(v) for v in dpg.get_axis_limits(ui.y_axis))
            y2 = tuple(float(v) for v in dpg.get_axis_limits(ui.y2_axis))
        except Exception:
            return
        if pan["own"] is None and y2 != pan["y2"]:        # ImPlot verschiebt die rechte Achse selbst
            pan["own"] = False
        if pan["own"] is False:
            return
        span1, span2 = pan["y1"][1] - pan["y1"][0], y2[1] - y2[0]
        shift = 0.0
        if pan["region"] == "plot":
            same_span = abs((y1[1] - y1[0]) - span1) <= 1e-9 * max(abs(span1), 1e-300)
            if span1 > 0 and same_span and y1 != pan["y1"]:   # verschoben, nicht gezoomt
                shift = (y1[0] - pan["y1"][0]) / span1 * span2
        else:
            scale = self._px_per_unit(ui)
            if scale is not None and span1 > 0:
                inner_h = scale[1] * span1
                shift = (my - pan["mouse"]) / inner_h * span2   # Maus nach unten: Inhalt folgt nach unten
        if shift and np.isfinite(shift):
            y2 = (y2[0] + shift, y2[1] + shift)
            dpg.set_axis_limits(ui.y2_axis, *y2)
            if not hasattr(self, "y_release"):
                self.y_release = {}
            self.y_release[ui.y2_axis] = 1                # nach dem Loslassen wieder frei
            pan["own"] = True
        pan.update(y1=y1, y2=y2, mouse=my)

    def _poll_y_release(self) -> None:
        for axis, frames in list(getattr(self, "y_release", {}).items()):
            if frames > 0:
                self.y_release[axis] = frames - 1
                continue
            del self.y_release[axis]
            if dpg.does_item_exist(axis):
                dpg.set_axis_limits_auto(axis)

    def _on_double_click(self, *_args) -> None:
        """Doppelklick auf einen Graphen im Plotbereich öffnet ihn groß im Detailfenster; im Detailfenster passt
        der Doppelklick ihn ein (ImPlot), die Y-Achse bekommt danach den Rand. Doppelklick auf ein Ergebnis der
        Fourier-Analyse (Signalliste, Liste im Rechendialog) öffnet die vollständige Periodentabelle."""
        channel = self._hovered_fourier()
        if channel is not None:
            self.open_fourier_window(channel)
            return
        ui = self._hovered_ui()
        if ui is None:
            return
        if ui is self.zoom_ui:
            self._fit_y(ui)
        else:
            self.open_zoom(ui.slot)

    # ---------------------------------------------------------------- Detailfenster (Doppelklick auf einen Graphen)
    ZOOM_SHARE = 0.86                    # Anteil am Programmfenster

    # ---------------------------------------------------------------- Tooltip am Signal (Marker aktiv)
    TIP_PX = 10           # höchster Abstand Maus - Kurve in Pixeln
    TIP_LABELS = ("X1-Wert:", "X2-Wert:", "Y1-Wert:", "Y2-Wert:", "Delta X:", "Delta Y:", "Average Signal:",
                  "Drift-Signal:", "Drift-Regression:", "Regression f(x)=m*x+b:")

    def _build_marker_tip(self) -> None:
        """Kleines Fenster ohne Titel, folgt der Maus; zeigt die Messwerte des Signals unter der Mausspitze."""
        with dpg.window(tag="marker_tip", show=False, no_title_bar=True, no_resize=True, autosize=True,
                        no_scrollbar=True, no_collapse=True, no_focus_on_appearing=True, no_move=True) as self.marker_tip:
            self.tip_title = dpg.add_text("", color=themes.color(self.mode, "heading"))
            self._colour(self.tip_title, "heading")
            with dpg.group(horizontal=True):
                with dpg.group():
                    for label in self.TIP_LABELS:
                        dpg.add_text(t(label), color=themes.color(self.mode, "text_dim"))
                with dpg.group():
                    self.tip_values = [dpg.add_text("") for _ in self.TIP_LABELS]
        self.tip_key = None
        self.tip_shown = False

    M3_PX = 12            # so nah (waagerecht, Pixel) muss die Maus an M3 stehen, damit die Wertetabelle erscheint

    def _build_m3_tip(self) -> None:
        with dpg.window(tag="m3_tip", show=False, no_title_bar=True, no_resize=True, autosize=True,
                        no_scrollbar=True, no_collapse=True, no_focus_on_appearing=True, no_move=True) as self.m3_tip:
            self.m3_title = dpg.add_text("", color=themes.color(self.mode, "heading"))
            self._colour(self.m3_title, "heading")
            with dpg.table(header_row=True, borders_innerH=True, borders_outerH=True, borders_innerV=True,
                           policy=dpg.mvTable_SizingFixedFit) as self.m3_table:
                for label in ("Signal", "Wert an M3", "Min", "Max", "Average", "Drift"):
                    dpg.add_table_column(label=t(label))
            self.m3_range_text = dpg.add_text("", color=themes.color(self.mode, "text_dim"))
            self._colour(self.m3_range_text, "text_dim")
        self.m3_tip_key = None
        self.m3_tip_shown = False
        self.m3_drag = False
        self.m3_rows_items = []

    M3_RANGES = {"markers": "Zwischen M1 und M2", "all": "Gesamter Signalverlauf"}

    def _m3_bounds(self, ui: SlotUI) -> tuple[float, float] | None:
        """Bereich für Min/Max/Average/Drift in Plot-Koordinaten: M1..M2 oder None (= gesamter Verlauf).
        Zwischen M1 und M2 nur, wenn die Marker eingeschaltet und gesetzt sind."""
        c1, c2 = ui.slot.cross
        if self.m3_range == "markers" and self.cross_on and c1 is not None and c2 is not None and c1 != c2:
            return tuple(sorted((float(c1), float(c2))))
        return None

    def _range_stats(self, ui: SlotUI, channel: Channel, bounds) -> tuple[float, float, float, float]:
        """Min, Max, Mittelwert und Drift (Delta Y / Delta X) eines Signals im Bereich (None = alle Daten).
        Im Bereich M1..M2 ist die Drift wie in der Wertanzeige (Werte an M1 und M2 interpoliert), über den
        gesamten Verlauf vom ersten zum letzten gültigen Messpunkt."""
        x = np.asarray(channel.x, dtype=np.float64)
        y = np.asarray(channel.y, dtype=np.float64)
        if bounds is not None:
            off = self._offset(ui, channel)
            lo, hi = bounds[0] - off, bounds[1] - off
            i0, i1 = np.searchsorted(x, lo, side="left"), np.searchsorted(x, hi, side="right")
            part = y[i0:i1]
            v_lo, v_hi = value_at(x, y, lo), value_at(x, y, hi)
            part = np.concatenate([part, [v for v in (v_lo, v_hi) if np.isfinite(v)]])
            drift = (v_hi - v_lo) / (hi - lo) if np.isfinite(v_lo) and np.isfinite(v_hi) else NAN
        else:
            part = y
            ok = np.flatnonzero(np.isfinite(y) & np.isfinite(x))
            drift = (y[ok[-1]] - y[ok[0]]) / (x[ok[-1]] - x[ok[0]]) \
                if ok.size >= 2 and x[ok[-1]] != x[ok[0]] else NAN
        part = part[np.isfinite(part)]
        if not part.size:
            return NAN, NAN, NAN, float(drift)
        return float(part.min()), float(part.max()), float(part.mean()), float(drift)

    def _m3_rows(self, ui: SlotUI) -> list[tuple[str, ...]]:
        """Je Signal des Graphen: Name, Wert an M3 (mit Einheit, ggf. Wert->Text), Min, Max, Average, Drift
        im gewählten Bereich (zwischen M1 und M2 oder gesamter Signalverlauf)."""
        rows = []
        x3 = ui.slot.cross3
        bounds = self._m3_bounds(ui)
        for channel in ui.slot.signals:
            name = t("{label} (rechts)", label=channel.label) if channel in ui.slot.right else channel.label
            if not channel.loaded or channel.x is None or not channel.x.size:
                rows.append((name, "-", "-", "-", "-", "-"))
                continue
            value = value_at(channel.x, channel.y, x3 - self._offset(ui, channel)) if x3 is not None else NAN
            lo, hi, mean, drift = self._range_stats(ui, channel, bounds)
            unit = channel.unit
            rows.append((name, self._with_text(channel, value) if np.isfinite(value) else "-",
                         fmt(lo, unit), fmt(hi, unit), fmt(mean, unit),
                         fmt(drift, drift_unit(unit, channel.x_unit))))
        return rows

    def _m3_range_label(self, ui: SlotUI) -> str:
        bounds = self._m3_bounds(ui)
        if bounds is not None:
            fmt_x = format_wallclock if ui.time_axis else (
                lambda v: fmt(v, ui.slot.signals[0].x_unit if ui.slot.signals else ""))
            return t("Min/Max/Average/Drift: zwischen M1 und M2 ({x1} bis {x2})", x1=fmt_x(bounds[0]), x2=fmt_x(bounds[1]))
        if self.m3_range == "markers":
            return t("Min/Max/Average/Drift: gesamter Signalverlauf (M1/M2 nicht eingeschaltet)")
        return t("Min/Max/Average/Drift: gesamter Signalverlauf")

    def set_m3_range(self, value: str) -> None:
        """Bereich für Min/Max/Average/Drift in der M3-Tabelle: "markers" (M1..M2) oder "all"."""
        self.m3_range = value if value in self.M3_RANGES else "markers"
        self.settings["m3_range"] = self.m3_range
        self._save_settings()
        label = t(self.M3_RANGES[self.m3_range])
        if dpg.get_value(self.m3_range_combo) != label:
            dpg.set_value(self.m3_range_combo, label)
        self.m3_tip_key = None

    def _on_m3_range(self, _sender, label) -> None:
        for key, text in self.M3_RANGES.items():
            if t(text) == label:
                self.set_m3_range(key)
                return

    def _m3_x_text(self, ui: SlotUI) -> str:
        x3 = ui.slot.cross3
        if x3 is None:
            return "-"
        if ui.time_axis:
            return format_wallclock(x3)
        unit = ui.slot.signals[0].x_unit if ui.slot.signals else ""
        return fmt(x3, unit)

    def _m3_hit(self):
        """Graph, an dessen M3 die Maus steht (oder der gerade gezogen wird), sonst None."""
        if not self.m3_on:
            return None
        down = dpg.is_mouse_button_down(dpg.mvMouseButton_Left)
        if not down:
            self.m3_drag = False
        ui = self._hovered_ui()
        if ui is None or ui.slot.cross3 is None:
            return None
        mouse = self._plot_mouse()
        scale = self._px_per_unit(ui)
        if mouse is None or scale is None:
            return None
        near = abs(mouse[0] - ui.slot.cross3) * scale[0] <= self.M3_PX
        if near and down:
            self.m3_drag = True
        return ui if near or (down and self.m3_drag) else None

    def _poll_m3_tip(self) -> None:
        tip = getattr(self, "m3_tip", None)
        if tip is None or not dpg.does_item_exist(tip):
            return
        menu_open = dpg.does_item_exist("ctx_menu") and dpg.is_item_shown("ctx_menu")
        ui = None if menu_open else self._m3_hit()
        if ui is None:
            if self.m3_tip_shown:
                dpg.configure_item(tip, show=False)
                self.m3_tip_shown, self.m3_tip_key = False, None
            return
        key = (id(ui), ui.slot.cross3, self._m3_bounds(ui), self.m3_range, self.lang,
               tuple((id(c), id(c.x), c in ui.slot.right) for c in ui.slot.signals))
        if key != self.m3_tip_key:                     # nur bei Änderung rechnen (Min/Max über viele Punkte)
            dpg.set_value(self.m3_title, t("M3: {x}", x=self._m3_x_text(ui)))
            dpg.set_value(self.m3_range_text, self._m3_range_label(ui))
            for row in self.m3_rows_items:
                if dpg.does_item_exist(row):
                    dpg.delete_item(row)
            self.m3_rows_items = []
            for cells in self._m3_rows(ui):
                with dpg.table_row(parent=self.m3_table) as row:
                    for text in cells:
                        dpg.add_text(text)
                self.m3_rows_items.append(row)
            self.m3_tip_key = key
        mx, my = (float(v) for v in dpg.get_mouse_pos(local=False))
        width = float(dpg.get_item_rect_size(tip)[0] or 300)
        x = mx + 18 if mx + 18 + width < dpg.get_viewport_client_width() else mx - 18 - width
        dpg.set_item_pos(tip, [max(0.0, x), my + 18])
        if not self.m3_tip_shown:
            dpg.configure_item(tip, show=True)
            self.m3_tip_shown = True
            if ui is self.zoom_ui and hasattr(dpg, "focus_item"):
                dpg.focus_item(tip)

    def _signal_at(self, ui: SlotUI, mouse) -> Channel | None:
        """Signal, dessen Kurve der Mausspitze am nächsten liegt (senkrechter Abstand in Pixeln, höchstens TIP_PX);
        Signale an der rechten Y-Achse werden in deren Maßstab gemessen."""
        scale = self._px_per_unit(ui)
        if scale is None:
            return None
        mx, my = mouse
        try:
            y_lo, y_hi = (float(v) for v in dpg.get_axis_limits(ui.y_axis))
            y2 = tuple(float(v) for v in dpg.get_axis_limits(ui.y2_axis)) if ui.y2_axis is not None else None
        except Exception:
            return None
        best = None
        for channel in ui.series:
            if not channel.loaded or channel.x is None or not channel.x.size:
                continue
            yq, sy = my, scale[1]
            if channel in ui.slot.right and y2 is not None:
                if y_hi <= y_lo or y2[1] <= y2[0]:
                    continue
                yq = y2[0] + (my - y_lo) / (y_hi - y_lo) * (y2[1] - y2[0])
                sy = scale[1] * (y_hi - y_lo) / (y2[1] - y2[0])
            value = value_at(channel.x, channel.y, mx - self._offset(ui, channel))
            if not np.isfinite(value):
                continue
            distance = abs(value - yq) * sy
            if distance <= self.TIP_PX and (best is None or distance < best[0]):
                best = (distance, channel)
        return best[1] if best else None

    def _average_between(self, ui: SlotUI, channel: Channel) -> float:
        """Mittelwert des Signals zwischen M1 und M2 (ohne Marker: über alle Daten)."""
        c1, c2 = ui.slot.cross
        x, y = channel.x, channel.y
        if c1 is not None and c2 is not None:
            off = self._offset(ui, channel)
            lo, hi = sorted((c1 - off, c2 - off))
            i0, i1 = np.searchsorted(x, lo, side="left"), np.searchsorted(x, hi, side="right")
            y = y[i0:i1]
        y = np.asarray(y, dtype=np.float64)
        y = y[np.isfinite(y)]
        return float(y.mean()) if y.size else NAN

    def _tip_values(self, ui: SlotUI, channel: Channel) -> list[str]:
        x1, x2, v1, v2, dx, dy, drift = self._measure_values(ui, channel)
        m, b = self._regression_mb(channel)
        xu = channel.x_unit
        reg = "-"
        if np.isfinite(m) and np.isfinite(b):
            reg = f"f(x) = {fmt(m)} * x {'-' if b < 0 else '+'} {fmt(abs(b))}"
        return [x1, x2, v1, v2, dx, dy, fmt(self._average_between(ui, channel), channel.unit), drift,
                fmt(m, drift_unit(channel.unit, xu)) if np.isfinite(m) else "-", reg]

    def _poll_marker_tip(self) -> None:
        tip = getattr(self, "marker_tip", None)
        if tip is None or not dpg.does_item_exist(tip):
            return
        ui = channel = None
        menu_open = dpg.does_item_exist("ctx_menu") and dpg.is_item_shown("ctx_menu")
        if self.cross_on and not menu_open and getattr(self, "comment_drag", None) is None \
                and not getattr(self, "m3_tip_shown", False):
            ui = self._hovered_ui()
            mouse = self._plot_mouse() if ui is not None else None
            channel = self._signal_at(ui, mouse) if mouse is not None else None
        if channel is None:
            if self.tip_shown:
                dpg.configure_item(tip, show=False)
                self.tip_shown, self.tip_key = False, None
            return
        key = (id(ui), channel, tuple(ui.slot.cross), self.reg_method, id(channel.x))
        if key != self.tip_key:
            dpg.set_value(self.tip_title, t("{label} (rechts)", label=channel.label) if channel in ui.slot.right
                          else channel.label)
            for item, text in zip(self.tip_values, self._tip_values(ui, channel)):
                dpg.set_value(item, text)
            self.tip_key = key
        mx, my = (float(v) for v in dpg.get_mouse_pos(local=False))
        width = float(dpg.get_item_rect_size(tip)[0] or 280)
        x = mx + 18 if mx + 18 + width < dpg.get_viewport_client_width() else mx - 18 - width
        dpg.set_item_pos(tip, [max(0.0, x), my + 18])
        if not self.tip_shown:
            dpg.configure_item(tip, show=True)
            self.tip_shown = True
            if ui is self.zoom_ui and hasattr(dpg, "focus_item"):   # sonst läge der Tooltip hinter dem Detailfenster
                dpg.focus_item(tip)

    def _build_zoom_window(self) -> None:
        dim = themes.color(self.mode, "text_dim")
        with dpg.window(tag="zoom_window", label=t("Graph im Detail"), show=False, width=1100, height=700,
                        no_collapse=True, on_close=lambda: self.close_zoom()):
            with dpg.group(horizontal=True):
                self.zoom_title = dpg.add_text("")
                self._colour(self.zoom_title, "heading")
                dpg.add_button(label=t("Alles anzeigen"), callback=lambda: self._zoom_fit())
                self.zoom_cross = dpg.add_checkbox(label=t("Marker"), default_value=self.cross_on,
                                                   callback=lambda _s, v: self._set_cross(v))
                self.zoom_sync = dpg.add_checkbox(label=t("Marker synchron"), default_value=self.cross_sync,
                                                  callback=lambda _s, v: self._set_cross_sync(v))
                self._tooltip(self.zoom_sync, t("Marker dieses Graphen mit den Graphen im Plotbereich gleich führen."))
                self.zoom_reg = dpg.add_checkbox(label=t("Regressionslinien"), default_value=self.reg_on,
                                                 callback=lambda _s, v: self._set_regression(v))
                dpg.add_button(label=t("Drucken / exportieren..."),
                               callback=lambda: self._open_export("one", self.zoom_slot, zoom=True))
                dpg.add_button(label=t("Report..."), callback=lambda: self._open_export("report"))
                dpg.add_button(label=t("Schließen"), callback=lambda: self.close_zoom())
            item = dpg.add_text(t("Derselbe Graph wie im Plotbereich: Änderungen gelten in beiden. Doppelklick: "
                                  "einpassen; Rechtsklick: Kontextmenü (Name, Signale, Farben, Achse, Legende, "
                                  "Kommentare, Drucken); Kommentare mit der linken Maustaste verschieben; Signale "
                                  "hierher ziehen."), wrap=0, color=dim)
            self._colour(item, "text_dim")
            self.zoom_plot_area = dpg.add_child_window(height=-1, border=False)
            self.zoom_table_area = dpg.add_child_window(height=self.table_h, border=False, show=False)

    def open_zoom(self, slot: GraphSlot) -> None:
        if slot not in self.layout.slots or not slot.signals:
            return
        self.zoom_slot = slot
        self._show_zoom_window()
        self._build_zoom()
        self._rebuild_table()
        self._apply_graph_font()
        try:
            dpg.focus_item("zoom_window")
        except Exception:
            pass
        self._message(t("{name} im Detailfenster.", name=slot.display_name(self.layout.slots.index(slot))))

    def _show_zoom_window(self) -> None:
        if dpg.get_item_configuration("zoom_window").get("show"):
            return                                 # bleibt, wo der Nutzer es hingeschoben hat
        vw, vh = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
        w, h = int(vw * self.ZOOM_SHARE), int(vh * self.ZOOM_SHARE)
        dpg.configure_item("zoom_window", show=True, width=w, height=h,
                           pos=[max(0, (vw - w) // 2), max(0, (vh - h) // 2)])

    def _build_zoom(self) -> None:
        """Graph des Detailfensters (neu) aufbauen; dieselbe Aufbaufunktion und dasselbe GraphSlot-Objekt wie im
        Plotbereich, daher gelten Signale, Farben, Achsen, Grenzen, Marker, Legende und Kommentare in beiden."""
        if not dpg.does_item_exist("zoom_window"):
            return
        dpg.delete_item(self.zoom_plot_area, children_only=True)
        self.zoom_ui = None
        slot = self.zoom_slot
        if slot is None:
            return
        if slot not in self.layout.slots or not slot.signals or not self.datasets:
            self.close_zoom()
            return
        self._show_zoom_window()                   # z. B. nach dem Sprachwechsel neu angelegt
        index = self.layout.slots.index(slot)
        multi_file = len({c.source for c in self.layout.signals()}) > 1
        self.alarm_plots.discard(getattr(self.zoom_ui, "plot", None))
        self._build_plot(index, slot, multi_file, parent=self.zoom_plot_area, zoom=True)
        if self.cross_on:                          # Marker an der Stelle wie im Plotbereich
            self._init_cross_positions()
            self._sync_lines_to_state()
        name = slot.display_name(index)
        dpg.configure_item("zoom_window", label=t("Graph im Detail: {name}", name=name))
        dpg.set_value(self.zoom_title, name)
        dpg.set_value(self.zoom_cross, self.cross_on)
        dpg.set_value(self.zoom_sync, self.cross_sync)
        dpg.set_value(self.zoom_reg, self.reg_on)
        self._zoom_heights()

    def _zoom_heights(self) -> None:
        if dpg.does_item_exist(self.zoom_table_area):
            dpg.configure_item(self.zoom_table_area, show=self.cross_on, height=self.table_h)
            dpg.configure_item(self.zoom_plot_area, height=-(self.table_h + 8) if self.cross_on else -1)

    def _zoom_fit(self) -> None:
        if self.zoom_ui is not None:
            dpg.fit_axis_data(self.zoom_ui.x_axis)
            self._fit_y(self.zoom_ui)

    def close_zoom(self) -> None:
        had = self.zoom_ui is not None or self.zoom_slot is not None
        self.zoom_ui, self.zoom_slot = None, None
        if self.comment_drag is not None and self.comment_drag["ui"] not in self.slot_ui:
            self.comment_drag = None
        if dpg.does_item_exist("zoom_window"):
            dpg.delete_item(self.zoom_plot_area, children_only=True)
            dpg.configure_item("zoom_window", show=False)
        if had:
            self._rebuild_table()

    def _set_cross(self, value: bool) -> None:
        """Marker ein/aus aus dem Detailfenster: wie das Häkchen in der Werkzeugleiste."""
        dpg.set_value(self.cross_box, value)
        self._on_cross_toggle(None, value)

    def _set_cross_sync(self, value: bool) -> None:
        dpg.set_value(self.sync_box, value)
        self._on_cross_sync(None, value)

    # ---------------------------------------------------------------- Marker (senkrecht, M1 und M2)
    def _data_range(self, ui: SlotUI):
        """Datenbereich in Plot-Koordinaten."""
        spans = [(c.x[0] + self._offset(ui, c), c.x[-1] + self._offset(ui, c)) for c in ui.slot.signals if c.x.size]
        if not spans:
            return None
        return min(s[0] for s in spans), max(s[1] for s in spans)

    def _init_cross_positions(self) -> None:
        """Neue Linien starten bei 1/3 und 2/3 des Datenbereichs.

        Synchron werden nur Graphen gleicher Achsenart geführt (Datum oder Sekunden).
        """
        shared: dict[bool, list] = {}
        if self.cross_sync:
            for ui in self._all_ui():
                if ui.slot.cross[0] is not None and ui.time_axis not in shared and not ui.fourier:
                    shared[ui.time_axis] = list(ui.slot.cross)
        for ui in self._all_ui():
            if ui.slot.cross[0] is not None:
                continue
            if ui.time_axis in shared and not ui.fourier:
                ui.slot.cross = list(shared[ui.time_axis])
                continue
            span = self._data_range(ui)
            if span is None:
                continue
            lo, hi = span
            ui.slot.cross = [lo + (hi - lo) / 3, lo + (hi - lo) * 2 / 3]
            if self.cross_sync:
                shared[ui.time_axis] = list(ui.slot.cross)
        for ui in self._all_ui():  # Graphen ohne Daten wurden vor dem ersten Treffer übersprungen
            if ui.slot.cross[0] is None and ui.time_axis in shared and not ui.fourier:
                ui.slot.cross = list(shared[ui.time_axis])

    def _sync_lines_to_state(self) -> None:
        for ui in self._all_ui():
            for k in (0, 1):
                x = ui.slot.cross[k]
                if x is None:
                    continue
                dpg.set_value(ui.v_lines[k], x)
                ui.v_read[k] = _scalar(dpg.get_value(ui.v_lines[k]))

    def _poll_crosslines(self) -> None:
        if not self.cross_on:
            return
        changed = False
        for ui in self._all_ui():
            for k in (0, 1):
                current = _scalar(dpg.get_value(ui.v_lines[k]))
                if ui.v_read[k] is None:  # Graph ohne Daten: noch keine Position
                    ui.v_read[k] = current
                elif current != ui.v_read[k]:
                    ui.slot.cross[k] = current
                    ui.v_read[k] = current
                    changed = True
                    for other in self._all_ui():      # derselbe Graph im Detailfenster läuft immer mit
                        if self._peer(ui, other):
                            other.slot.cross[k] = current
                            dpg.set_value(other.v_lines[k], current)
                            other.v_read[k] = _scalar(dpg.get_value(other.v_lines[k]))
        if changed:
            self._update_measurements()

    def _poll_view(self) -> None:
        """Nach Zoom/Unzoom (Mausrad, Rechteck, Doppelklick, "Alles anzeigen", Kopplung) M1 auf 10 % und M2 auf
        90 % der neuen Ansicht; beim Verschieben nur, wenn ein Marker aus dem Bild fällt. Ändern mehrere Graphen
        im selben Bild ihre Ansicht, gilt der Graph unter der Maus zuerst (er ist der gezoomte). M3 wird nur in
        die Mitte gesetzt, wenn er aus dem Bild fällt."""
        changed = []
        for ui in self._all_ui():
            limits = tuple(float(v) for v in dpg.get_axis_limits(ui.x_axis))
            if len(limits) != 2 or not all(np.isfinite(limits)) or limits[1] <= limits[0]:
                continue
            previous, ui.view = ui.view, limits
            if ui.settle > 0:          # Graph gerade aufgebaut, Achsen passen sich noch an
                ui.settle -= 1
                continue
            if previous is None or limits == previous:
                continue
            changed.append((ui, previous, limits))
        if not changed:
            return
        hovered = self._hovered_ui()
        changed.sort(key=lambda item: item[0] is not hovered)
        moved, placed = False, set()
        for ui, previous, limits in changed:
            span, before = limits[1] - limits[0], previous[1] - previous[0]
            if self.m3_on and ui.slot.cross3 is not None and not limits[0] <= ui.slot.cross3 <= limits[1]:
                self._place_m3(ui, limits[0] + 0.5 * span)
            if not self.cross_on or ui.slot.cross[0] is None or id(ui) in placed:
                continue
            zoomed = abs(span - before) > 1e-9 * max(span, before)
            outside = any(c is not None and not limits[0] <= c <= limits[1] for c in ui.slot.cross)
            if zoomed or outside:
                for target in self._place_markers(ui, [limits[0] + 0.1 * span, limits[0] + 0.9 * span]):
                    if target.view is not None and target.view != limits:
                        placed.add(id(target))   # mitgeführter Graph mit anderer Ansicht: hier nicht erneut setzen
                moved = True
        if moved:
            self._update_measurements()
        elif any(not ui.fourier for ui, _p, _l in changed):
            self._update_harmonics()                       # Zoom am Grundsignal: Fourier-Analyse neu bewerten

    def _markers_into_view(self) -> None:
        """Beim Einschalten: Marker außerhalb der aktuellen Ansicht auf 10 % und 90 % der Ansicht setzen."""
        for ui in self._all_ui():
            view = ui.view                       # erst nach dem Einpassen bekannt (frisch aufgebaute Graphen: nichts tun)
            if view is None or ui.settle > 0:
                continue
            if len(view) != 2 or not all(np.isfinite(view)) or view[1] <= view[0]:
                continue
            if any(c is None or not view[0] <= c <= view[1] for c in ui.slot.cross):
                span = view[1] - view[0]
                self._place_markers(ui, [view[0] + 0.1 * span, view[0] + 0.9 * span])

    def _peer(self, ui: SlotUI, other: SlotUI) -> bool:
        """Marker mitführen: derselbe Graph (Detailfenster) oder synchron bei gleicher Achsenart - nie in Graphen der
        Fourier-Analyse (andere X-Achse: Frequenz bzw. Nummer der Harmonischen)."""
        if other is ui:
            return False
        if other.slot is ui.slot:
            return True
        return self.cross_sync and other.time_axis == ui.time_axis and not ui.fourier and not other.fourier

    def _place_markers(self, ui: SlotUI, positions: list) -> list:
        targets = [ui] + [o for o in self._all_ui() if self._peer(ui, o)]
        for target in targets:
            target.slot.cross = list(positions)
            for k in (0, 1):
                dpg.set_value(target.v_lines[k], positions[k])
                target.v_read[k] = _scalar(dpg.get_value(target.v_lines[k]))
        return targets

    # ---------------------------------------------------------------- Marker 3 (Wertetabelle)
    def _m3_targets(self, ui: SlotUI) -> list:
        return [ui] + [o for o in self._all_ui() if self._peer(ui, o)]

    def _place_m3(self, ui: SlotUI, position: float) -> None:
        for target in self._m3_targets(ui):
            target.slot.cross3 = float(position)
            if target.m3_line is not None and dpg.does_item_exist(target.m3_line):
                dpg.set_value(target.m3_line, float(position))
                target.m3_read = _scalar(dpg.get_value(target.m3_line))

    def set_marker3(self, value: bool) -> None:
        """Marker 3 ein/aus. Beim Einschalten steht er in der Mitte der Ansicht (oder bleibt, wo er im Bild war)."""
        self.m3_on = bool(value)
        if dpg.get_value(self.m3_box) != self.m3_on:
            dpg.set_value(self.m3_box, self.m3_on)
        if self.m3_on:
            done = set()
            for ui in self._all_ui():
                if id(ui) in done:
                    continue
                view = ui.view if ui.view is not None and ui.settle == 0 else None
                if view is None or not all(np.isfinite(view)) or view[1] <= view[0]:
                    view = self._data_range(ui)
                if view is None:
                    continue
                c3 = ui.slot.cross3
                if c3 is None or not view[0] <= c3 <= view[1]:
                    self._place_m3(ui, view[0] + 0.5 * (view[1] - view[0]))
                    done.update(id(o) for o in self._m3_targets(ui))
                else:
                    dpg.set_value(ui.m3_line, float(c3))
                    ui.m3_read = _scalar(dpg.get_value(ui.m3_line))
        for ui in self._all_ui():
            if ui.m3_line is not None:
                dpg.configure_item(ui.m3_line, show=self.m3_on and not ui.fourier)
        if not self.m3_on and getattr(self, "m3_tip_shown", False):
            dpg.configure_item(self.m3_tip, show=False)
            self.m3_tip_shown, self.m3_tip_key = False, None

    def _poll_m3(self) -> None:
        if not self.m3_on:
            return
        for ui in self._all_ui():
            if ui.m3_line is None:
                continue
            current = _scalar(dpg.get_value(ui.m3_line))
            if ui.m3_read is None:
                ui.m3_read = current
            elif current != ui.m3_read:
                ui.m3_read = current
                for target in self._m3_targets(ui):
                    target.slot.cross3 = current
                    if target is not ui:
                        dpg.set_value(target.m3_line, current)
                        target.m3_read = _scalar(dpg.get_value(target.m3_line))

    # ---------------------------------------------------------------- Schriftgröße der Graphen
    def _size_font(self, size: int):
        """Schrift in der gewünschten Größe aus den beim Start angelegten; None ohne Schriftdatei."""
        path = self._lang_font_path(self.lang)
        if not path:
            return None
        return self.size_fonts.get((path, int(size)))

    def _apply_graph_font(self) -> None:
        """Graphen (Titel, Achsen, Legende, Marker-Beschriftung) und Wertanzeige in der eingestellten Größe."""
        font = self._size_font(self.graph_font_size)
        if font is None:
            return
        for ui in self._all_ui():
            if dpg.does_item_exist(ui.plot):
                dpg.bind_item_font(ui.plot, font)
        for area in (self.table_area, getattr(self, "zoom_table_area", None)):
            if area is not None and dpg.does_item_exist(area):
                dpg.bind_item_font(area, font)

    def _on_font_size(self, _sender, value) -> None:
        self.graph_font_size = max(FONT_MIN, min(FONT_MAX, int(value)))
        self.settings["graph_font_size"] = self.graph_font_size
        self._save_settings()
        self._apply_graph_font()

    def _rebuild_table(self) -> None:
        self.table_rows, self.table_preds = [], []
        self.limit_boxes = {}   # (Graph, Signal, 0/1) -> Eingabefeld; Detailfenster: ("zoom", Signal, 0/1)
        self.target_boxes, self.table_row_pos = {}, []
        self.limit_box_list, self.target_box_list = [], []   # (SlotUI, Signal, ..., Feld) für jede Tabellenzeile
        self._fill_table(self.table_holder, list(enumerate(self.slot_ui)))
        if dpg.does_item_exist(getattr(self, "zoom_table_area", 0) or 0):
            dpg.delete_item(self.zoom_table_area, children_only=True)
            if self.zoom_ui is not None and self.zoom_slot in self.layout.slots:
                self._fill_table(self.zoom_table_area, [(self.layout.slots.index(self.zoom_slot), self.zoom_ui)],
                                 key="zoom")
        self._update_measurements()

    def _fill_table(self, parent, entries: list, key=None) -> None:
        """Wertanzeige der Marker für die Graphen in entries [(Index, SlotUI)]."""
        dpg.delete_item(parent, children_only=True)
        labels = ["Graph", "Signal", "X1", "X2", "Wert 1", "Wert 2", "Delta X", "Delta Y", "Drift", "Y min", "Y max"]
        labels += ["Zielzeit", self._drift_label(), "Prognose"]
        with dpg.table(parent=parent, header_row=True, row_background=True, resizable=True,
                       borders_innerH=True, borders_innerV=True, borders_outerH=True, borders_outerV=True,
                       policy=dpg.mvTable_SizingStretchProp, scrollY=True, height=-1) as table:
            for label in labels:
                dpg.add_table_column(label=t(label), init_width_or_weight={"Prognose": 2.4, "Zielzeit": 1.5}.get(label, 1.0))
            row_number = 0
            for index, ui in entries:
                for channel in ui.slot.signals:
                    self.table_row_pos.append((table, row_number))
                    row_number += 1
                    with dpg.table_row():
                        dpg.add_text(ui.slot.display_name(index))
                        dpg.add_text(t("{label} (rechts)", label=channel.label) if channel in ui.slot.right
                                     else channel.label)
                        cells = [dpg.add_text("-") for _ in range(7)]
                        from_config = self._config_limits(channel) is not None
                        limits = self._limits_for(ui.slot, channel)
                        for k in (0, 1):
                            box = dpg.add_input_text(width=-1, hint=t("Min") if k == 0 else t("Max"),
                                                     default_value="" if limits[k] is None else f"{limits[k]:g}",
                                                     callback=self._on_limit, user_data=(ui, channel, k))
                            self.limit_boxes[(index if key is None else key, channel.name, k)] = box
                            self.limit_box_list.append((ui, channel, k, box))    # alle Felder, auch gleichnamige
                            self._tooltip(box, t("Grenze aus der Konfiguration (Mode {mode}). Änderungen gehen in die "
                                                 "Konfiguration; \"In YAML speichern\" schreibt sie in die Datei.",
                                                 mode=self.cfg_mode)
                                          if from_config else
                                          t("Grenze für dieses Signal. Die Spalte Prognose berechnet aus der "
                                            "Regressionsgeraden aller Daten und dem letzten Wert, wann sie "
                                            "erreicht wird. Leer = keine."))
                        target = self._target_for(ui.slot, channel)
                        target_yaml = target is not None and target[2] == "yaml"
                        manual = ui.slot.targets.get(channel)
                        with dpg.group(horizontal=True):
                            box = dpg.add_input_text(width=-44, hint=t("z. B. 2d 6h 30m"),
                                                     default_value=self._mode_spec().steps_text() if target_yaml
                                                     else (format_target(manual) if manual else ""),
                                                     callback=self._on_target, user_data=(ui, channel))
                            self.target_boxes[(index if key is None else key, channel.name)] = box
                            self.target_box_list.append((ui, channel, box))
                            self._tooltip(box, t("steps des Modes {mode} aus der Konfiguration: gilt für alle Signale "
                                                 "der Wertanzeige. Zahl = Schritte, mit Einheiten = Zeit, z. B. 7h 18m "
                                                 "26s. Änderungen gehen in die Konfiguration.", mode=self.cfg_mode)
                                          if target_yaml else
                                          t("Zielzeit in Tagen, Stunden, Minuten (z. B. 2d 6h 30m; ohne Einheit: "
                                            "eine Zahl = Stunden, zwei = h m, drei = d h m). Erreicht die Prognose "
                                            "die Grenze früher, wird die Zeile rot und der Graph schwach rot "
                                            "hinterlegt. Leer = keine."))
                            button = dpg.add_button(label=t("Alle"), small=True, callback=self._target_to_all,
                                                    user_data=(ui, channel), show=not target_yaml)
                            self._tooltip(button, t("Diese Zielzeit für alle Signale übernehmen."))
                        slope = dpg.add_text("-")
                        pred = dpg.add_text("-")
                    self.table_rows.append((ui, channel, cells))
                    self.table_preds.append((slope, pred))

    def _on_limit(self, _sender, value, user_data) -> None:
        ui, channel, k = user_data
        text = str(value).strip().replace(",", ".")
        if text:
            try:
                number = float(text)
            except ValueError:
                return  # unvollständige Eingabe ("-", "1e"): bisherige Grenze bleibt
            if not np.isfinite(number):
                return
        else:
            number = None
        if self._config_limits(channel) is not None:      # Grenze aus der YAML: dort ändern
            self._on_config_limit(_sender, ui, channel, k, number)
            return
        limits = list(ui.slot.limits.get(channel, [None, None]))
        limits[k] = number
        if limits == [None, None]:
            ui.slot.limits.pop(channel, None)
        else:
            ui.slot.limits[channel] = limits
        for other in self._all_ui():               # auch die andere Darstellung desselben Graphen
            if other.slot is ui.slot:
                self._update_limit_lines(other, channel)
        for other_ui, signal, k2, box in self.limit_box_list:   # dasselbe Signal im Detailfenster bzw. Plotbereich
            if box != _sender and signal is channel and other_ui.slot is ui.slot and k2 == k \
                    and dpg.does_item_exist(box):
                dpg.set_value(box, "" if limits[k] is None else f"{limits[k]:g}")
        self._update_measurements()

    def _on_config_limit(self, sender, ui: SlotUI, channel: Channel, k: int, number) -> None:
        """Grenze eines Signals aus der YAML in der Wertanzeige geändert: in den Mode schreiben (rückwärts)."""
        mode = self._mode_spec()
        key = mode.match_name(channel.name) if mode is not None else None
        if key is None:
            return
        limits = list(mode.signals[key])
        limits[k] = number
        mode.set_entry(key, True, limits[0], limits[1], order=False)
        self.limit_cfg.modified = True
        for other in self._all_ui():                  # alle Darstellungen von Signalen mit diesem Eintrag
            for signal in list(other.series):
                if mode.match_name(signal.name) == key:
                    self._update_limit_lines(other, signal)
        for _other, signal, k2, box in self.limit_box_list:    # jede Zeile mit diesem Eintrag (auch mehrere Dateien)
            if box != sender and k2 == k and mode.match_name(signal.name) == key and dpg.does_item_exist(box):
                dpg.set_value(box, "" if number is None else f"{number:g}")
        self._update_measurements()
        self._config_edited(key)
        if self._config_limits(channel) is None:      # beide Grenzen leer: ab jetzt wieder manuell
            self._later(self._rebuild_table)

    def _config_edited(self, key: str | None = None) -> None:
        """Nach einer Änderung aus der Wertanzeige: Kennzeichen * und offenen Konfigurator nachführen."""
        self._refresh_mode_combo()
        if dpg.does_item_exist("limit_editor") and dpg.get_item_configuration("limit_editor").get("show"):
            mode = self._le_mode()
            if key is not None and mode is not None and key in self.le_widgets and key in mode.entries:
                entry = mode.entries[key]
                _box, lower, upper = self.le_widgets[key]
                dpg.set_value(lower, "" if entry.lower is None else f"{entry.lower:g}")
                dpg.set_value(upper, "" if entry.upper is None else f"{entry.upper:g}")
            self._le_refresh(rows=False)

    def save_limit_config_back(self) -> None:
        """Änderungen in die geladene YAML zurückschreiben (neue Konfiguration: nach dem Namen fragen)."""
        if self.limit_cfg is None:
            self._message(t("Keine Grenzwert-Konfiguration geladen."), error=True)
            return
        self._le_save(ask=not self.limit_cfg.path)

    # ---------------------------------------------------------------- Grenzwert-Konfiguration (YAML, je Mode)
    def load_limit_config(self, path: str, mode: str | None = None, quiet: bool = False) -> bool:
        try:
            config = limitconfig.load(path)
        except LoadError as exc:
            self._message(str(exc), error=True)
            return False
        self.limit_cfg = config
        self.settings["limit_config"] = os.path.abspath(path)
        self._save_settings()
        keep = mode if mode in config.modes else (self.cfg_mode if self.cfg_mode in config.modes else None)
        self._refresh_mode_combo()
        self.set_limit_mode(keep, quiet=True)
        if dpg.does_item_exist("limit_editor") and dpg.get_item_configuration("limit_editor").get("show"):
            self.le_edit_mode = keep or next(iter(config.modes), None)
            self._le_refresh()
        if not quiet:
            self._message(limitconfig.describe(config) + " " + (t("Mode: {name}", name=keep) if keep
                          else t("Mode wählen (Werkzeugleiste), bis dahin gelten die manuellen Werte.")))
        return True

    # ---------------------------------------------------------------- Grenzwert-Konfigurator (Fenster)
    LE_FILTER_LIMIT = 600                    # höchstens so viele Zeilen auf einmal (sonst Suche eingrenzen)

    # ---------------------------------------------------------------- Auto-Auswertung
    AUTO_MIN_CYCLE = 5.0
    AUTO_PHASES = {"read": "Lese Dateien", "png": "Erzeuge Bilder", "json": "Schreibe Ergebnisdatei"}

    @staticmethod
    def parse_cycle(text) -> float:
        """Zykluszeit aus "60", "90s", "5m", "1h 30m"; ValueError bei ungültiger Eingabe."""
        steps, seconds = limitconfig.parse_steps(text)
        value = seconds if seconds is not None else steps
        if value is None:
            raise ValueError(text)
        return float(value)

    # ---- Auswertungen (je Quell- und Zielverzeichnis eine, mit eigenem Namen, Mode und eigener Zielzeit)
    def _auto_load_jobs(self) -> None:
        if getattr(self, "auto_evals_loaded", False):  # Neuaufbau (Sprache, Farbschema): Auswertungen und Engines bleiben
            return
        self.auto_evals_loaded = True
        data = self.settings.get("auto") or {}
        jobs = [dict(j) for j in data.get("jobs") or [] if isinstance(j, dict)]
        if not jobs and data.get("source"):            # ältere Einstellungen: eine Auswertung aus Quelle/Ziel
            jobs = [{"name": t("Auswertung_{n}", n=1), "source": data.get("source", ""), "target": data.get("target", ""),
                     "mode": data.get("mode", ""), "target_time": "24h", "enabled": True}]
        for number, job in enumerate(jobs, 1):
            job.setdefault("name", t("Auswertung_{n}", n=number))
            job.setdefault("source", "")
            job.setdefault("target", "")
            job.setdefault("mode", "")
            job.setdefault("target_time", "24h")
            job.setdefault("enabled", True)
        jobs = [j for j in jobs if j.get("source") or j.get("target") or j.get("folders")]   # leere Platzhalter weg
        evals = [dict(e) for e in data.get("evaluations") or [] if isinstance(e, dict) and e.get("name")]
        if not evals:                                  # ältere Einstellungen: je Regel bzw. je Quellordner eine Auswertung
            for job in jobs:
                name = job.get("rule") or job["name"]
                if not any(e["name"] == name for e in evals):
                    evals.append({"name": name, "rule": job.get("rule", "")})
                job["evaluation"] = name
        for job in jobs:
            if not job.get("evaluation") or not any(e["name"] == job["evaluation"] for e in evals):
                job["evaluation"] = job["name"]
                if not any(e["name"] == job["name"] for e in evals):
                    evals.append({"name": job["name"], "rule": job.get("rule", "")})
        self.auto_jobs = jobs
        self.auto_evals = evals
        self.auto_eval_name = data.get("evaluation") if any(e["name"] == data.get("evaluation") for e in evals) else \
            (evals[0]["name"] if evals else "")
        self.auto_sel = min(int(data.get("selected", 0) or 0), max(0, len(jobs) - 1))
        self._auto_dedupe()

    @staticmethod
    def _abs_dir(text: str) -> str:
        """Relativer Ordner (z. B. .\\Projekt_Daten\\DV_HTOE22kW) -> absoluter Pfad, damit Zielordner und Report nicht
        vom Startordner des Programms abhängen."""
        text = (text or "").strip()
        return os.path.abspath(os.path.expanduser(text)) if text else ""

    @staticmethod
    def _norm_path(path: str) -> str:
        return os.path.normcase(os.path.abspath(os.path.expanduser(path))) if path else ""

    def _auto_dedupe(self) -> int:
        """Doppelte Auswertungen (gleiche Quelle und gleiches Ziel) entfernen - die erste bleibt. Gibt die Anzahl der
        entfernten zurück."""
        seen, keep = set(), []
        current = self.auto_jobs[self.auto_sel] if 0 <= self.auto_sel < len(self.auto_jobs) else None
        for job in self.auto_jobs:
            key = (self._norm_path(job.get("source")), self._norm_path(job.get("target")))
            if key[0] and key in seen:
                self.auto_engines.pop(id(job), None) if hasattr(self, "auto_engines") else None
                continue
            seen.add(key)
            keep.append(job)
        removed = len(self.auto_jobs) - len(keep)
        if removed:
            self.auto_jobs = keep
            self.auto_sel = keep.index(current) if current in keep else 0
        return removed

    AUTO_BLANK = {"name": "", "source": "", "target": "", "mode": "", "target_time": "", "enabled": False, "rule": "",
                  "evaluation": ""}

    def _auto_job(self) -> dict:
        """Gewählter Teil: der gewählte bzw. erste Teil der gewählten Auswertung; ohne Teile ein leerer Eintrag."""
        jobs = self._auto_eval_jobs() if hasattr(self, "auto_evals") else self.auto_jobs
        if 0 <= self.auto_sel < len(self.auto_jobs) and self.auto_jobs[self.auto_sel] in jobs:
            return self.auto_jobs[self.auto_sel]
        if jobs:
            return jobs[0]
        if not hasattr(self, "auto_blank"):
            self.auto_blank = dict(self.AUTO_BLANK)
        return self.auto_blank

    def _auto_store(self) -> None:
        data = self.auto_settings.to_dict()
        for key in ("source", "target", "mode", "folders", "exclude", "files"):   # gehören zu den einzelnen Teilen
            data.pop(key, None)
        data.update(jobs=self.auto_jobs, selected=self.auto_sel, evaluations=getattr(self, "auto_evals", []),
                    evaluation=getattr(self, "auto_eval_name", ""))
        self.settings["auto"] = data

    def _auto_job_settings(self, job: dict) -> "auto.AutoSettings":
        """Einstellungen einer Auswertung: allgemeine Werte + Quelle/Ziel/Mode der Auswertung, gemeinsame Ergebnisdatei."""
        data = self.auto_settings.to_dict()
        data.update(source=job["source"], target=job["target"], mode=job.get("mode", ""), json_name=self._auto_json_path(job),
                    folders=list(job.get("folders") or []), exclude=list(job.get("exclude") or []),
                    files=list(job.get("files") or []))
        kind = job.get("goal_kind") or "time"
        ev = self._auto_eval_get(job.get("evaluation") or "") if job.get("evaluation") else None
        data.update(edge_count=kind == "edges", no_eval=kind == "ignore",
                    edges=list(((ev or {}).get("mode_edges") or {}).get(self._auto_mode_name(job), []))
                    if kind == "edges" else [],
                    edge_target=job.get("target_edges") if kind == "edges" else None)
        return auto.AutoSettings.from_dict(data)

    AUTO_JSON_DEFAULT = "Time_counter.json"

    def _auto_target_dir(self, job: dict | None = None) -> str:
        """Zielverzeichnis einer Auswertung: Basis-Zielordner ihrer Verzeichnisregel (nicht der erweiterte Ordner je
        Mode/DUT); ohne Regel der Zielordner des Teils."""
        job = job or self._auto_job()
        rule = self._auto_rule_get(job.get("rule") or "") if job.get("rule") else None
        if rule is not None and getattr(rule, "base", ""):
            return rule.base
        if job.get("target"):
            return job["target"]
        return next((j["target"] for j in self.auto_jobs if j.get("target")), "")

    def _auto_json_path(self, job: dict | None = None) -> str:
        """Ergebnisdatei (alle) = Zielverzeichnis\\<Dateiname> (Standard Time_counter.json, z. B. HTOE_time_counter.json).
        Alle Teile mit demselben Zielverzeichnis schreiben in dieselbe Datei. Ein voller Pfad (ältere Einstellung)
        gilt weiter für alle Auswertungen."""
        name = (self.auto_settings.json_name or "").strip() or self.AUTO_JSON_DEFAULT
        if job is not None and job.get("goal_kind") == "edges":     # Flanken: eigene Ergebnisdatei
            name = self._edge_json_name(name)
        if os.path.isabs(os.path.expanduser(name)):
            return os.path.expanduser(name)
        folder = self._auto_target_dir(job)
        return os.path.join(folder, name) if folder else name

    @staticmethod
    def _edge_json_name(name: str) -> str:
        """Ergebnisdatei der Modes mit Zähler Flanke neben der Zeit-Datei: Time_counter.json -> Flanken_counter.json,
        HTOE_time_counter.json -> HTOE_Flanken_counter.json, andere Namen -> <Name>_Flanken.json."""
        folder, base = os.path.split(name)
        if re.search(r"time_counter", base, flags=re.IGNORECASE):
            base = re.sub(r"time_counter", "Flanken_counter", base, flags=re.IGNORECASE)
        else:
            stem, ext = os.path.splitext(base)
            base = f"{stem}_Flanken{ext or '.json'}"
        return os.path.join(folder, base) if folder else base

    def _auto_json_paths(self) -> list[str]:
        """Alle Ergebnisdateien (je Zielverzeichnis eine), Reihenfolge der Auswertungen."""
        paths = []
        for job in self.auto_jobs or [self._auto_job()]:
            path = self._auto_json_path(job)
            if path not in paths:
                paths.append(path)
        return paths

    @classmethod
    def _auto_json_name(cls, text: str) -> str:
        """Eingabe prüfen: Dateiname (ohne Ordner) oder voller Pfad; .json wird ergänzt. ValueError bei ungültigem Namen."""
        name = (text or "").strip() or cls.AUTO_JSON_DEFAULT
        if not os.path.isabs(os.path.expanduser(name)):
            if re.search(r'[\\/:*?"<>|]', name) or name.strip(". ") == "":
                raise ValueError(name)
        if not name.lower().endswith(".json"):
            name += ".json"
        return name

    def _auto_json_show(self) -> None:
        if getattr(self, "auto_json_where", None) and dpg.does_item_exist(self.auto_json_where):
            dpg.set_value(self.auto_json_where, "= " + "\n= ".join(self._auto_json_paths()))

    # ---- Flanken je Mode (Zähler "Flanke" in Schritt 2): Signale über ein Werteband
    EDGE_FIELDS = ("signal", "upper", "lower", "n", "target")

    def _auto_edges(self, mode: str | None = None) -> list:
        """Flankendefinitionen eines Modes (in der Auswertung gespeichert, bearbeitbar)."""
        ev = self._auto_eval()
        mode = mode if mode is not None else getattr(self, "auto_edges_mode", "")
        if ev is None or not mode:
            return []
        return ev.setdefault("mode_edges", {}).setdefault(mode, [])

    def _auto_edges_valid(self, mode: str | None = None) -> list:
        return [e for e in (auto.normalize_edge(x) for x in self._auto_edges(mode))
                if e is not None and (e["upper"] is not None or e["lower"] is not None)]

    @staticmethod
    def _edge_text(edge: dict) -> str:
        parts = []
        if edge.get("upper") is not None:
            parts.append(f"> {fmt(edge['upper'])}")
        if edge.get("lower") is not None:
            parts.append(f"< {fmt(edge['lower'])}")
        return f"{edge['signal']} ({' / '.join(parts)}, n = {edge['n']})"

    def _auto_edges_summary(self, mode: str | None = None) -> str:
        valid = self._auto_edges_valid(mode)
        if not valid:
            return t("keine Flanken festgelegt")
        return ", ".join(self._edge_text(e) for e in valid)

    def _auto_signal_names(self, mode: str | None = None) -> list[str]:
        """Bekannte Signalnamen eines Modes (gelesene Gruppen seiner Teile), sonst aller Daten und der Analyse."""
        names = set()
        jobs = self._auto_eval_modes().get(mode, []) if mode else []
        engines = [self.auto_engines[id(j)] for j in jobs if id(j) in getattr(self, "auto_engines", {})] if jobs \
            else list(getattr(self, "auto_engines", {}).values())
        for engine in engines:
            for group in engine.groups.values():
                names.update(group.merged or {})
                for data in group.files.values():
                    names.update(data.signals)
        if not names:
            names = set(getattr(self, "auto_stats", {}) or {})
        return sorted(names, key=str.casefold)

    def _build_auto_edges_window(self) -> None:
        with dpg.window(tag="auto_edges_window", label=t("Flanken definieren"), show=False,
                        width=900, height=460, no_collapse=True):
            item = dpg.add_text(t("Eine Flanke über Wert1: Signal übersteigt Wert1, bleibt mindestens n Werte darüber und "
                                  "fällt danach für mindestens n Werte wieder darunter. Eine Flanke unter Wert2: Signal "
                                  "unterschreitet Wert2, bleibt mindestens n Werte darunter und steigt danach für "
                                  "mindestens n Werte wieder darüber. Kürzere Ausreißer zählen nicht. Gezählt wird über "
                                  "alle Daten-Files der Gruppe (zusammengefasst); Wert1 oder Wert2 darf leer bleiben. "
                                  "Ziel = gewünschte Anzahl Flanken (optional, für die Erfüllung)."), wrap=0)
            self._colour(item, "text_dim")
            with dpg.table(header_row=True, policy=dpg.mvTable_SizingStretchProp) as self.auto_edges_table:
                for label, weight in ((t("Signal"), 2.2), (t("Wert1 (oben)"), 0.9), (t("Wert2 (unten)"), 0.9),
                                      ("n", 0.6), (t("Ziel (Flanken)"), 0.8), ("", 1.2)):
                    dpg.add_table_column(label=label, init_width_or_weight=weight)
            with dpg.group(horizontal=True):
                dpg.add_button(label=t("Signal hinzufügen"), callback=lambda: self.auto_add_edge())
                dpg.add_button(label=t("Schließen"), width=110,
                               callback=lambda: dpg.configure_item("auto_edges_window", show=False))
            self.auto_edges_state = dpg.add_text("", wrap=0)
            self._colour(self.auto_edges_state, "heading")

    def open_auto_edges_window(self, mode: str) -> None:
        """Flanken eines Modes festlegen (aus Modes und Zielzeiten, Zähler Flanke)."""
        self.auto_edges_mode = mode
        dpg.configure_item("auto_edges_window", label=t("Flanken definieren - Mode {mode}", mode=mode))
        self._auto_edges_fill()
        vw, vh = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
        dpg.configure_item("auto_edges_window", show=True, pos=[max(0, (vw - 900) // 2), max(0, (vh - 460) // 3)])

    def _auto_edges_fill(self) -> None:
        if not dpg.does_item_exist("auto_edges_window"):
            return
        for row in dpg.get_item_children(self.auto_edges_table, 1) or []:
            dpg.delete_item(row)
        names = self._auto_signal_names(getattr(self, "auto_edges_mode", ""))
        self.auto_edge_rows = []
        for index, edge in enumerate(self._auto_edges()):
            with dpg.table_row(parent=self.auto_edges_table):
                with dpg.group(horizontal=True):
                    field = dpg.add_input_text(default_value=str(edge.get("signal") or ""), width=-130,
                                               hint=t("Signalname"), user_data=(index, "signal"),
                                               callback=lambda s, v, u: self._auto_edge_set(u[0], u[1], v))
                    dpg.add_combo(items=names, default_value="", width=120, user_data=index,
                                  callback=lambda s, v, u: self._auto_edge_pick(u, v))
                cells = [field]
                for key in ("upper", "lower", "n", "target"):
                    value = edge.get(key)
                    text = "" if value is None else (fmt(value) if key in ("upper", "lower") and
                                                     isinstance(value, (int, float)) else str(value))
                    cells.append(dpg.add_input_text(default_value=text, width=-1, user_data=(index, key),
                                                    hint={"upper": "Wert1", "lower": "Wert2", "n": "1",
                                                          "target": t("optional")}[key],
                                                    callback=lambda s, v, u: self._auto_edge_set(u[0], u[1], v)))
                with dpg.group(horizontal=True):
                    dpg.add_button(label=t("Entfernen"), small=True, user_data=index,
                                   callback=lambda s, a, u: self._auto_remove_edge(u))
                    note = dpg.add_text("")
                    self._colour(note, "error")
                self.auto_edge_rows.append((cells, note))
        self._auto_edges_check()

    def _auto_edge_problems_all(self) -> list:
        """Über alle Auswertungen: verarbeitete Modes mit Zähler Flanke ohne gültige Flanke."""
        out = []
        current = getattr(self, "auto_eval_name", "")
        for ev in getattr(self, "auto_evals", []):
            modes = {}
            for job in self._auto_eval_jobs(ev):
                modes.setdefault(self._auto_mode_name(job), []).append(job)
            for mode, jobs in modes.items():
                if any(j.get("enabled", True) for j in jobs) and self._mode_goal(jobs)["kind"] == "edges":
                    valid = [e for e in (auto.normalize_edge(x) for x in (ev.get("mode_edges") or {}).get(mode, []))
                             if e is not None and (e["upper"] is not None or e["lower"] is not None)]
                    if not valid:
                        out.append(mode if ev["name"] == current else f"{ev['name']}/{mode}")
        return out

    def _auto_edges_check(self) -> None:
        """Hinweise je Zeile und Zusammenfassung; die Zeile des Modes in Modes und Zielzeiten folgt."""
        for index, edge in enumerate(self._auto_edges()):
            if index >= len(getattr(self, "auto_edge_rows", [])):
                break
            note = self.auto_edge_rows[index][1]
            problem = ""
            if not str(edge.get("signal") or "").strip():
                problem = t("Signal fehlt")
            else:
                for key in ("upper", "lower", "target"):
                    raw = edge.get(key)
                    if raw not in (None, "") and auto._num(raw) is None:
                        problem = t("keine Zahl: {value}", value=raw)
                if not problem and auto._num(edge.get("upper")) is None and auto._num(edge.get("lower")) is None:
                    problem = t("Wert1 oder Wert2 angeben")
                raw = str(edge.get("n") or "1").replace(",", ".")
                try:
                    if float(raw) < 1 or not float(raw).is_integer():
                        raise ValueError(raw)
                except ValueError:
                    problem = t("n: ganze Zahl ab 1")
            dpg.set_value(note, problem)
        if getattr(self, "auto_edges_state", None):
            dpg.set_value(self.auto_edges_state, t("Flanken: {text}", text=self._auto_edges_summary()))
        mode = getattr(self, "auto_edges_mode", "")
        if mode:
            self._auto_goal_notes(mode)
            if dpg.does_item_exist(getattr(self, "auto_modes_text", 0) or 0):
                dpg.set_value(self.auto_modes_text, self._auto_modes_summary())

    def _auto_edge_set(self, index: int, key: str, value) -> None:
        edges = self._auto_edges()
        if not 0 <= index < len(edges):
            return
        value = str(value).strip()
        edges[index][key] = value if key == "signal" else (value or None)
        self._auto_edges_check()
        self._auto_store()

    def _auto_edge_pick(self, index: int, name: str) -> None:
        if not name:
            return
        self._auto_edge_set(index, "signal", name)
        cells = self.auto_edge_rows[index][0] if index < len(getattr(self, "auto_edge_rows", [])) else None
        if cells:
            dpg.set_value(cells[0], name)

    def auto_add_edge(self, signal: str = "", upper=None, lower=None, n: int = 1, target=None,
                      mode: str | None = None) -> dict:
        if mode is not None:
            self.auto_edges_mode = mode
        edge = {"signal": signal, "upper": upper, "lower": lower, "n": n, "target": target}
        self._auto_edges().append(edge)
        self._auto_store()
        self._auto_edges_fill()
        return edge

    def _auto_remove_edge(self, index: int) -> None:
        edges = self._auto_edges()
        if 0 <= index < len(edges):
            edges.pop(index)
        self._auto_store()
        self._auto_edges_fill()

    def _auto_engine_for(self, job: dict) -> "auto.AutoEngine":
        """Engine je Auswertung (gelesene Dateien bleiben, solange Quelle und Gruppierung gleich sind)."""
        settings = self._auto_job_settings(job)
        where = os.path.abspath(settings.target) if settings.folders or settings.files else os.path.abspath(settings.source)
        key = (where, settings.recursive, settings.group_regex, settings.one_group)   # Ordner/Ausschlüsse: nur neue Daten
        engine = self.auto_engines.get(id(job))
        if engine is None or getattr(engine, "form_key", None) != key:
            engine = auto.AutoEngine(settings)
            engine.form_key = key
            self.auto_engines[id(job)] = engine
        else:
            engine.settings = settings
        if job is self._auto_job():
            self.auto_engine = engine
        return engine

    def _build_auto_window(self) -> None:
        s = self.auto_settings
        self._auto_load_jobs()
        job = self._auto_job()
        self.auto_items = {1: [], 2: [], 3: [], 4: []}      # Bedienelemente je Schritt (Sperren/Freigeben)
        self.auto_step_state, self.auto_step_btn, self.auto_step_reset = {}, {}, {}

        def reg(step: int, item):
            self.auto_items[step].append(item)
            return item

        def tip(item, text: str):
            self._tooltip(item, t(text))
            return item

        def head(step: int, title: str, text: str) -> None:
            dpg.add_separator()
            with dpg.group(horizontal=True):
                item = dpg.add_text(t("Schritt {n}: {title}", n=step, title=t(title)))
                self._colour(item, "heading")
                self.auto_step_state[step] = dpg.add_text("")
                if step < 4:
                    self.auto_step_btn[step] = dpg.add_button(label=t("Schritt abschließen"), small=True,
                                                              callback=lambda: self.auto_finish_step(step))
                    tip(self.auto_step_btn[step], "Schritt abschließen: Die Einstellungen dieses Schritts werden "
                        "geprüft und gesperrt, der nächste Schritt wird freigegeben. Gesperrte Schritte werden mit "
                        "Start (Durchlauf gestartet) oder Zurücksetzen wieder freigegeben.")
                self.auto_step_reset[step] = dpg.add_button(label=t("Schritt zurücksetzen"), small=True,
                                                            callback=lambda: self.auto_reset_step(step))
                tip(self.auto_step_reset[step], "Diesen Schritt und alle folgenden zurücksetzen: sie sind wieder offen "
                    "und müssen neu abgeschlossen werden (Schritt 1 = alle Schritte). Ein laufender Zyklus wird "
                    "gestoppt. Einstellungen, Auswertungen und Ergebnisse bleiben erhalten.")
            item = dpg.add_text(t(text), wrap=0)
            self._colour(item, "text_dim")

        with dpg.window(tag="auto_window", label=t("Auto-Auswertung"), show=False, width=1080, height=820,
                        no_collapse=True):
            item = dpg.add_text(t("Ablauf: 1 Auswertungen festlegen -> 2 Modes und Zielzeiten -> 3 Analysieren und "
                                  "Grenzen prüfen -> 4 Zyklus starten. Danach Report über Auto > Report erstellen. Jede "
                                  "Auswertung ist ein Quellordner (ein DUT in einem Mode) mit eigenem Zielordner; "
                                  "einzelne Auswertungen trägt man von Hand ein, viele auf einmal über eine "
                                  "Verzeichnisregel. Abgeschlossene Schritte sind gesperrt, bis der Durchlauf gestartet "
                                  "oder Zurücksetzen gedrückt wird."), wrap=0)
            self._colour(item, "text_dim")
            with dpg.group(horizontal=True):
                self.auto_reset_btn = dpg.add_button(label=t("Zurücksetzen"), callback=lambda: self.auto_reset_steps())
                tip(self.auto_reset_btn, "Alle Schritte wieder freigeben und bei Schritt 1 beginnen. Einstellungen, "
                    "Auswertungen und Ergebnisse bleiben erhalten.")
                self.auto_step_info = dpg.add_text("")
                self._colour(self.auto_step_info, "heading")

            # ---- Schritt 1
            head(1, "Auswertung festlegen", "1. Name eingeben und mit Anlegen bestätigen - oder bei leerem Namen eine "
                 "vorhandene Auswertung wählen. 2. Verzeichnisregel wählen; gibt es noch keine (passende), mit "
                 "Verzeichnisregel verwalten... eine neue Regel anlegen (sie bekommt den Namen der Auswertung). Quelle, "
                 "Zielordner und ausgeschlossene Dateien kommen aus der Regel und stehen unten zur Information.")
            with dpg.table(header_row=False, policy=dpg.mvTable_SizingStretchProp):
                dpg.add_table_column(init_width_or_weight=0.2)
                dpg.add_table_column(init_width_or_weight=0.8)
                with dpg.table_row():
                    dpg.add_text(t("Name"))
                    with dpg.group(horizontal=True):
                        self.auto_name = reg(1, tip(dpg.add_input_text(default_value="", width=320, on_enter=True,
                                                                       hint=t("Name der neuen Auswertung"),
                                                                       callback=lambda: self.auto_create_eval()),
                                                    "Name einer neuen Auswertung (z. B. HTOE_22kW_DV). Mit Anlegen (oder "
                                                    "Eingabetaste) bestätigen. Leer lassen, um eine vorhandene Auswertung "
                                                    "unten zu wählen. Verzeichnisregel verwalten... übernimmt diesen Namen "
                                                    "als Namen der neuen Regel."))
                        reg(1, tip(dpg.add_button(label=t("Anlegen"), width=100, callback=lambda: self.auto_create_eval()),
                                   "Neue Auswertung mit dem eingegebenen Namen anlegen und wählen."))
                        self.auto_name_hint = dpg.add_text("")
                        self._colour(self.auto_name_hint, "error")
                with dpg.table_row():
                    dpg.add_text(t("Auswertung"))
                    with dpg.group(horizontal=True):
                        self.auto_eval_combo = reg(1, tip(dpg.add_combo(items=[], width=320,
                                                                        callback=lambda _s, v: self.auto_pick_eval(v)),
                                                          "Vorhandene Auswertung wählen (nur Auswahl; neue über Name und "
                                                          "Anlegen). Die Angaben darunter gehören zu ihr."))
                        reg(1, tip(dpg.add_button(label=t("Löschen"), callback=lambda: self.auto_delete_eval()),
                                   "Gewählte Auswertung mit allen ihren Zielordnern aus der Liste entfernen. Ergebnisse "
                                   "auf der Festplatte und die Verzeichnisregel bleiben."))
                        self.auto_eval_hint = dpg.add_text("")
                        self._colour(self.auto_eval_hint, "error")
                with dpg.table_row():
                    dpg.add_text(t("Verzeichnisregel"))
                    with dpg.group(horizontal=True):
                        self.auto_rule = reg(1, tip(dpg.add_combo(items=[], width=320,
                                                                  callback=lambda _s, v: self._auto_set_rule(v)),
                                                    "Regel aus dem Verzeichnisverwalter: Quellordner, Dateien, Zielordner. "
                                                    "Jeder Zielordner der Regel wird ein Teil der Auswertung (z. B. ein DUT "
                                                    "in einem Mode)."))
                        reg(1, tip(dpg.add_button(label=t("Verzeichnisregel verwalten..."), width=220,
                                                  callback=lambda: self.open_dir_window(from_auto=True)),
                                   "Verzeichnisverwalter öffnen: neue Regel mit dem Namen aus dem Feld Name (bzw. der "
                                   "gewählten Auswertung) anlegen - oder eine vorhandene Regel bearbeiten."))
                        self.auto_rule_hint = dpg.add_text("")
                        self._colour(self.auto_rule_hint, "error")
                with dpg.table_row():
                    dpg.add_text(t("Regel (Info)"))
                    self.auto_info = tip(dpg.add_text("", wrap=0),
                                         "Nur zur Information (keine Eingabe): Quellordner, Zielordner, eingelesene oder "
                                         "ausgeschlossene Dateien der gewählten Verzeichnisregel. Ändern im "
                                         "Verzeichnisverwalter.")
                    self._colour(self.auto_info, "text_dim")
            with dpg.collapsing_header(label=t("Erweitert: Gruppierung der Dateien"), default_open=False):
                with dpg.group(horizontal=True):
                    self.auto_one = reg(1, tip(dpg.add_checkbox(label=t("Alle Dateien eines Zielordners = eine Auswertung"),
                                                                default_value=s.one_group,
                                                                callback=lambda: self._auto_read_form()),
                                               "Alle Dateien werden nach ihrem Zeitstempel zu einer Messung "
                                               "aneinandergereiht (auch mit unterschiedlichen Signalen). Aus: Gruppen "
                                               "nach Dateiname (Gruppenmuster)."))
                    self.auto_regex = reg(1, tip(dpg.add_input_text(default_value=s.group_regex, width=-1,
                                                                    hint=t("Gruppenmuster, leer = Dateiname ohne angehängte Zähler/Zeitstempel"),
                                                                    callback=lambda: self._auto_read_form()),
                                                 "Nur ohne 'eine Auswertung': regulärer Ausdruck auf den Dateinamen ohne "
                                                 "Endung; Gruppe 1 (oder der ganze Treffer) ist der Gruppenname, z. B. "
                                                 "(DES\\d+_DUT\\d+)."))

            # ---- Schritt 2
            head(2, "Modes und Zielzeiten", "Modes und Zielzeiten... öffnet die Modes der Auswertung, nach ähnlichen Namen "
                 "gruppiert: Häkchen = Mode verarbeiten, dahinter der Zähler (Zeit, Flanke oder Ignorieren) und das "
                 "Ziel (gilt für alle DUTs des Modes). Die Zuordnung lässt sich jederzeit ändern und gilt sofort für "
                 "die gewählten Daten.")
            with dpg.group(horizontal=True):
                self.auto_modes_btn = tip(dpg.add_button(label=t("Modes und Zielzeiten..."), width=230,
                                                         callback=lambda: self.open_auto_modes()),
                                          "Liste der Modes öffnen: verarbeiten an/aus, Zähler (Zeit, Flanke, "
                                          "Ignorieren) und Ziel je Mode. Jederzeit änderbar, auch nach Abschluss "
                                          "von Schritt 2 und während des Zyklus; gilt sofort für die gewählten Daten.")
                self.auto_modes_state = dpg.add_text("")
                self._colour(self.auto_modes_state, "heading")
            self.auto_modes_text = dpg.add_text("", wrap=0)
            self._colour(self.auto_modes_text, "text_dim")

            # ---- Schritt 3
            head(3, "Analysieren und Grenzen prüfen", "Analysieren liest alle Dateien der aktiven Auswertungen (mit Regel: "
                 "alle gewählten Modes und DUTs) und schlägt je Mode Grenzen vor. Grenzen im Grenzwert-Konfigurator "
                 "prüfen und speichern; wo nötig Limiter-Regeln setzen und Grenzen neu vorschlagen lassen.")
            with dpg.group(horizontal=True):
                self.auto_analyze_btn = reg(3, tip(dpg.add_button(label=t("Analysieren"), width=120,
                                                                  callback=lambda: self.analyze_auto_source()),
                                                   "Alle Dateien lesen (Fortschritt unten) und die Signale im "
                                                   "Grenzwert-Konfigurator bereitstellen: neuer Mode mit Vorschlägen für "
                                                   "alle Signale, vorhandener Mode um fehlende Signale ergänzt."))
                reg(3, tip(dpg.add_button(label=t("Grenzwert-Konfigurator..."), callback=lambda: self.open_limit_editor()),
                           "Grenzen (Limit min/max), aktiv/inaktiv und Zielzeit je Mode und Signal bearbeiten und "
                           "speichern."))
                reg(3, tip(dpg.add_button(label=t("Limiter bearbeiten..."), callback=lambda: self.open_limiter_window()),
                           "Datenbereiche begrenzen (z. B. nur der obere Teil eines Rechtecksignals); gilt für alle Signale "
                           "der Datei bzw. Auswertung. Regeln lassen sich auf eine Auswahl von Dateien übertragen."))
                self.auto_readjust_btn = reg(3, tip(dpg.add_button(label=t("Grenzen neu vorschlagen"),
                                                                   callback=lambda: self.analyze_auto_source(readjust=True)),
                                                    "Grenzen des Modes der Auswertung neu aus den Daten vorschlagen - mit "
                                                    "Limiter nur aus den Abschnitten im Limit (ohne die weggeschnittenen "
                                                    "Spitzen). Aktiv/inaktiv und Zielzeit bleiben."))
            self.auto_analysis_text = dpg.add_text("", wrap=0)
            self._colour(self.auto_analysis_text, "text_dim")

            # ---- Schritt 4 (eigenes Fenster wegen der Informationsmenge)
            head(4, "Zyklus starten", "Zykluszeit, Ausgaben, Start/Stopp, Fortschritt, Zähler und Log stehen wegen der "
                 "Informationsmenge in einem eigenen Fenster. Es öffnet sich beim Abschließen von Schritt 3; dieses "
                 "Fenster bleibt offen.")
            with dpg.group(horizontal=True):
                self.auto_run_open_btn = tip(dpg.add_button(label=t("Fenster Schritt 4 öffnen..."), width=230,
                                                            callback=lambda: self.open_auto_run_window()),
                                             "Fenster für Schritt 4: Zykluszeit, PNG, Ergebnisdatei, Start, Stopp, Jetzt "
                                             "ausführen, Fortschritt, Zähler und Log.")
                self.auto_run_state = dpg.add_text("")
                self._colour(self.auto_run_state, "text_dim")
            with dpg.group(horizontal=True, show=False) as self.auto_progress_row:
                self.auto_progress = dpg.add_progress_bar(default_value=0.0, width=-110, overlay="")
                dpg.add_button(label=t("Abbrechen"), width=100, callback=lambda: self.cancel_auto())
            self.auto_hint = dpg.add_text("", wrap=0)
            self._colour(self.auto_hint, "error")

        with dpg.window(tag="auto_modes_window", label=t("Modes und Zielzeiten"), show=False, width=700, height=520,
                        no_collapse=True):
            item = dpg.add_text(t("Häkchen = verarbeiten. Zähler je Mode (jederzeit änderbar, gilt sofort für alle "
                                  "gewählten Daten des Modes): Zeit (Ziel hh:mm:ss), Flanke (Ziel Anzahl Flanken, "
                                  "Signale über Flanken...) oder Ignorieren (keine Bewertung: kein Zähler, keine "
                                  "Violation). Leeres Ziel = unendlich: keine Violation möglich."), wrap=0)
            self._colour(item, "text_dim")
            with dpg.group(horizontal=True):
                dpg.add_button(label=t("Alle"), small=True, callback=lambda: self._auto_modes_all(True))
                dpg.add_button(label=t("Keine"), small=True, callback=lambda: self._auto_modes_all(False))
                self.auto_modes_goal_all = dpg.add_input_text(width=110, hint="hh:mm:ss")
                self._tooltip(self.auto_modes_goal_all, t("Zielzeit für alle angehakten Modes"))
                dpg.add_button(label=t("für alle angehakten"), small=True, callback=lambda: self._auto_modes_goal_all())
            self.auto_modes_box = dpg.add_child_window(height=-40, border=True)
            with dpg.group(horizontal=True):
                dpg.add_button(label=t("Schließen"), width=110,
                               callback=lambda: dpg.configure_item("auto_modes_window", show=False))
                self.auto_modes_state2 = dpg.add_text("")
                self._colour(self.auto_modes_state2, "heading")

        vw = 1000
        with dpg.window(tag="auto_run_window", label=t("Auto-Auswertung - Schritt 4: Zyklus starten"), show=False,
                        width=vw, height=720, no_collapse=True):
            item = dpg.add_text(t("Erster Durchlauf: alle Dateien des Quellordners. Ab dem zweiten Durchlauf: nur neue "
                                  "und geänderte Dateien (gelöschte fallen heraus). Zykluszeit und Ausgaben festlegen, "
                                  "dann Start (zyklisch) oder Jetzt ausführen (ein Zyklus sofort, alle Bewertungen und "
                                  "Bilder neu). Start gibt alle Schritte wieder frei. Schritte 1 bis 3 bleiben im Fenster "
                                  "Auto-Auswertung."), wrap=0)
            self._colour(item, "text_dim")
            with dpg.group(horizontal=True):
                item = dpg.add_text(t("Schritt {n}: {title}", n=4, title=t("Zyklus starten")))
                self._colour(item, "heading")
                self.auto_run_step_state = dpg.add_text("")
            with dpg.table(header_row=False, policy=dpg.mvTable_SizingStretchProp):
                dpg.add_table_column(init_width_or_weight=0.2)
                dpg.add_table_column(init_width_or_weight=0.8)
                with dpg.table_row():
                    dpg.add_text(t("Zykluszeit"))
                    with dpg.group(horizontal=True):
                        self.auto_cycle = reg(4, tip(dpg.add_input_text(default_value=limitconfig.format_time(s.cycle_s),
                                                                        width=120, hint="60s, 5m, 1h",
                                                                        callback=lambda: self._auto_read_form()),
                                                     "Abstand der Zyklen. Jeder Zyklus liest nur neue oder geänderte "
                                                     "Dateien; große Mengen verteilen sich auf mehrere Zyklen."))
                        self.auto_png = reg(4, tip(dpg.add_checkbox(label=t("PNG je Signal"), default_value=s.png,
                                                                    callback=lambda: self._auto_read_form()),
                                                   "Je Signal ein Graph mit Grenzen, Trend und Text (Grundlage des "
                                                   "Reports)."))
                        self.auto_hits = reg(4, tip(dpg.add_checkbox(label=t("nur Modes mit Treffern"),
                                                                     default_value=s.only_hits,
                                                                     callback=lambda: self._auto_read_form()),
                                                    "Time_counter.json nur mit Modes, in denen mindestens ein Messpunkt in "
                                                    "den Grenzen lag (sonst alle Modes mit passenden Signalen, auch 0)."))
                with dpg.table_row():
                    dpg.add_text(t("Ergebnisdatei (alle)"))
                    with dpg.group(horizontal=True):
                        self.auto_json = reg(4, tip(dpg.add_input_text(default_value=s.json_name, width=-110,
                                                                       hint=self.AUTO_JSON_DEFAULT,
                                                                       callback=lambda: self._auto_read_form()),
                                                    "Dateiname der Ergebnisdatei, Standard Time_counter.json, andere Namen "
                                                    "möglich (z. B. HTOE_time_counter.json). Sie liegt im Zielverzeichnis "
                                                    "der Auswertung (Basis-Zielordner der Verzeichnisregel); alle Modes "
                                                    "und DUTs schreiben dort in dieselbe Datei."))
                        reg(4, tip(dpg.add_button(label=t("Standard"), width=100,
                                                  callback=lambda: self._auto_json_default()),
                                   "Dateinamen auf den Standard zurücksetzen (Time_counter.json bzw. im Flanken "
                                   "Counter Flanken_counter.json)."))
                with dpg.table_row():
                    dpg.add_text("")
                    with dpg.group():
                        self.auto_json_where = dpg.add_text("", wrap=0)
                        self.auto_json_note = dpg.add_text("")
                        self._colour(self.auto_json_note, "error")
            self.auto_sources = dpg.add_text("", wrap=0)
            with dpg.group(horizontal=True):
                self.auto_start_btn = reg(4, tip(dpg.add_button(label=t("Start"), width=110,
                                                                callback=lambda: self.start_auto()),
                                                 "Zyklische Auswertung starten (erster Zyklus sofort). Gibt alle Schritte "
                                                 "wieder frei."))
                self.auto_stop_btn = tip(dpg.add_button(label=t("Stopp"), width=110, callback=lambda: self.stop_auto()),
                                         "Zyklische Auswertung anhalten (ein laufender Zyklus wird zu Ende geführt).")
                reg(4, tip(dpg.add_button(label=t("Jetzt ausführen"), callback=lambda: self.run_auto_now()),
                           "Einen Zyklus sofort ausführen: neue und geänderte Dateien lesen (beim ersten Durchlauf alle), alle "
                           "Bewertungen, Bilder und Zähler neu."))
                tip(dpg.add_button(label=t("Log anzeigen"), callback=lambda: self._auto_show_log()),
                    "Log der gewählten Auswertung (Dateien, Zeitstempel, Fehler) anzeigen.")
                tip(dpg.add_button(label=t("Report erstellen..."), callback=lambda: self.open_report_window()),
                    "Report je Mode mit allen gewählten DUTs (Auto > Report erstellen). Fehlen Ausgaben, läuft vorher "
                    "automatisch ein Zyklus.")
            self.auto_state = dpg.add_text("", wrap=0)
            self._colour(self.auto_state, "heading")
            with dpg.group(horizontal=True, show=False) as self.auto_run_progress_row:
                self.auto_run_progress = dpg.add_progress_bar(default_value=0.0, width=-110, overlay="")
                dpg.add_button(label=t("Abbrechen"), width=100, callback=lambda: self.cancel_auto())
            with dpg.table(header_row=True, resizable=True, borders_innerH=True, borders_outerH=True,
                           row_background=True, scrollY=True, height=-170,
                           policy=dpg.mvTable_SizingStretchProp) as self.auto_table:
                self.auto_table_cols = []
                for label, weight, tip_text in (
                        (t("Auswertung"), 1.0, t("Auswertung (Schritt 1)")),
                        (t("DUT / Teil"), 1.3, t("Teil der Auswertung (je Zielordner einer)")),
                        (t("Mode"), 1.3, t("Mode der Grenzwert-Konfiguration")),
                        (t("Gruppe"), 1.5, t("Gruppe = Seriennummer/DUT der zusammengefassten Dateien; Bilder im "
                                             "gleichnamigen Ordner. Schlüssel der Ergebnisdatei im Tooltip der Zelle.")),
                        (t("Ist"), 0.8, t("Zeit bzw. Messpunkte, in denen alle Signale des Modes in den Grenzen liegen")),
                        (t("Ziel"), 0.7, t("Zielzeit bzw. Zielschritte des Modes")),
                        (t("Erfüllung"), 0.8, t("Ist / Ziel in Prozent; grün ab 100 %"))):
                    self.auto_table_cols.append(dpg.add_table_column(label=label, init_width_or_weight=weight))
            self.auto_log = dpg.add_input_text(multiline=True, readonly=True, width=-1, height=160, default_value="")
        self._build_auto_edges_window()
        self._auto_show_job()
        self._auto_steps_apply()

    # ---------------------------------------------------------------- Schritte (feste Reihenfolge, Sperren)
    STEP_TITLES = {1: "Auswertungen festlegen", 2: "Modes und Zielzeiten", 3: "Analysieren und Grenzen prüfen",
                   4: "Zyklus starten"}

    def _auto_step(self) -> int:
        """Aktueller Schritt 1..4; 0 = frei (Durchlauf gestartet, alles bedienbar)."""
        try:
            return int(self.settings.get("auto_step", 1))
        except (TypeError, ValueError):
            return 1

    def _auto_steps_apply(self) -> None:
        """Abgeschlossene und noch nicht erreichte Schritte sperren, den aktuellen freigeben."""
        if not dpg.does_item_exist("auto_window") or not hasattr(self, "auto_items"):
            return
        current = self._auto_step()
        for step, items in self.auto_items.items():
            open_ = current == 0 or step == current
            for item in items:
                if dpg.does_item_exist(item):
                    dpg.configure_item(item, enabled=open_)
            if current == 0:
                state = ""
            elif step < current:
                state = t("[erledigt - gesperrt]")
            elif step == current:
                state = t("[jetzt]")
            else:
                state = t("[folgt]")
            dpg.set_value(self.auto_step_state[step], state)
            if step in self.auto_step_btn:
                dpg.configure_item(self.auto_step_btn[step], show=current == step)
            if step in getattr(self, "auto_step_reset", {}):
                dpg.configure_item(self.auto_step_reset[step], show=current == 0 or step < current)
        if dpg.does_item_exist(getattr(self, "auto_run_step_state", 0) or 0):
            dpg.set_value(self.auto_run_step_state, dpg.get_value(self.auto_step_state[4]))
            ready = current in (0, 4)
            dpg.configure_item(self.auto_run_open_btn, enabled=ready)
            dpg.set_value(self.auto_run_state, "" if ready else t("erst nach Abschluss von Schritt 3"))
        if current == 0:
            info = t("Durchlauf gestartet - alle Schritte frei. Zurücksetzen beginnt wieder bei Schritt 1.")
        else:
            info = t("Aktuell: Schritt {n} - {title}", n=current, title=t(self.STEP_TITLES[current]))
        dpg.set_value(self.auto_step_info, info)

    def _auto_set_step(self, step: int) -> None:
        self.settings["auto_step"] = step
        self._save_settings()
        self._auto_steps_apply()

    def auto_finish_step(self, step: int) -> bool:
        """Schritt prüfen und abschließen: sperren, nächsten freigeben."""
        self._auto_read_form()
        if step == 1:
            ev = self._auto_eval()
            if ev is None:
                self._message(t("Schritt 1: zuerst einen Namen eingeben und Anlegen drücken (oder eine Auswertung "
                                "wählen)."), error=True)
                return False
            if not ev.get("rule") and not self._auto_eval_jobs(ev):
                self._message(t("Schritt 1: bitte eine Verzeichnisregel wählen (oder mit Verzeichnisregel verwalten... "
                                "erstellen)."), error=True)
                return False
            jobs = self._auto_eval_jobs(ev)
            ready = [j for j in jobs if not self._auto_problem(j)]
            if not ready:
                bad = [f"{j['name']}: {self._auto_problem(j)}" for j in jobs if self._auto_problem(j)]
                self._message(t("Schritt 1: die Verzeichnisregel liefert keine Zielordner mit Messdateien. {text}",
                                text="; ".join(bad)), error=True)
                return False
            text = t("Schritt 1 abgeschlossen: Auswertung {name} mit {count} Zielordnern.", name=ev["name"],
                     count=len(ready))
        elif step == 2:
            modes = self._auto_eval_modes()
            on = {m: jobs for m, jobs in modes.items() if any(j.get("enabled", True) for j in jobs)}
            if not on:
                self._message(t("Schritt 2: mindestens einen Mode zum Verarbeiten anhaken (Modes und Zielzeiten...)."),
                              error=True)
                return False
            missing_edges = self._auto_edge_problems(modes)
            if missing_edges:
                self._message(t("Schritt 2: Zähler Flanke ohne Flanken bei: {names} (Flanken... drücken).",
                                names=", ".join(missing_edges)), error=True)
                return False
            text = t("Schritt 2 abgeschlossen: {count} Modes werden verarbeitet.", count=len(on))
            endless = [m for m, jobs in on.items() if self._goal_infinite(jobs)]
            if endless:
                text += " " + t("Ohne Zielvorgabe (unendlich, keine Violation): {names}.", names=", ".join(endless))
            silent = [m for m, jobs in on.items() if self._mode_goal(jobs)["kind"] == "ignore"]
            if silent:
                text += " " + t("Ohne Bewertung: {names}.", names=", ".join(silent))
        elif step == 3:
            if self.limit_cfg is None:
                self._message(t("Schritt 3: bitte zuerst Analysieren (es gibt noch keine Grenzwert-Konfiguration)."),
                              error=True)
                return False
            missing = sorted({self._auto_mode(j) for j in self.auto_jobs if j.get("enabled", True)
                              and self._auto_mode(j) not in self.limit_cfg.modes})
            text = t("Schritt 3 abgeschlossen.")
            if missing:
                text += " " + t("Noch ohne Grenzen (Vorschlag beim ersten Zyklus): {names}", names=", ".join(missing))
        else:
            return False
        self._auto_set_step(step + 1)
        self._message(text)
        if step == 3:                                      # Schritt 4 im eigenen Fenster, Auto-Fenster bleibt offen
            self.open_auto_run_window()
        return True

    def auto_reset_steps(self) -> None:
        self.auto_reset_step(1)

    def auto_reset_step(self, step: int) -> None:
        """Schritt n und alle folgenden zurücksetzen (Schritt 1 = alle): wieder offen, laufender Zyklus stoppt."""
        if self.auto_running:
            self.stop_auto()
        self._auto_set_step(step)
        if step == 1:
            self._message(t("Auto: Schritte zurückgesetzt - weiter mit Schritt 1."))
        else:
            self._message(t("Auto: Schritt {n} und folgende zurückgesetzt - weiter mit Schritt {n}.", n=step))

    # ---------------------------------------------------------------- Auswertungen: Name -> Verzeichnisregel
    STAR = "****"

    def _auto_eval_get(self, name: str) -> dict | None:
        return next((e for e in getattr(self, "auto_evals", []) if e["name"] == name), None)

    def _auto_eval(self) -> dict | None:
        name = getattr(self, "auto_eval_name", "")
        return next((e for e in self.auto_evals if e["name"] == name), None)

    def _auto_eval_jobs(self, ev: dict | None = None) -> list[dict]:
        ev = ev if ev is not None else self._auto_eval()
        if ev is None:
            return []
        return [j for j in self.auto_jobs if j.get("evaluation") == ev["name"]]

    def _auto_select_eval(self, name: str) -> None:
        self.auto_eval_name = name
        jobs = self._auto_eval_jobs()
        if jobs:
            self.auto_sel = self.auto_jobs.index(jobs[0])
        self._auto_store()
        self._save_settings()

    def auto_create_eval(self) -> None:
        """Name aus dem Feld Name als neue Auswertung anlegen (oder die vorhandene gleichen Namens wählen)."""
        name = dpg.get_value(self.auto_name).strip()
        if not name:
            if not self.auto_evals:
                dpg.set_value(self.auto_name_hint, t("Ein Name ist notwendig: Namen eingeben und Anlegen drücken."))
            else:
                dpg.set_value(self.auto_name_hint, t("Name leer - vorhandene Auswertung unten wählen oder neuen Namen eingeben."))
            return
        name = re.sub(r'[\\/:*?"<>|]+', "_", name).strip(" ._") or name
        if any(e["name"] == name for e in self.auto_evals):
            self._auto_select_eval(name)
            self._auto_show_job()
            self._message(t("Auto: Auswertung {name} gibt es schon - gewählt.", name=name))
            return
        self.auto_evals.append({"name": name, "rule": ""})
        self._auto_select_eval(name)
        self._auto_show_job()
        self._message(t("Auto: Auswertung {name} angelegt. Jetzt die Verzeichnisregel wählen oder mit Verzeichnisregel "
                        "verwalten... anlegen.", name=name))

    def auto_pick_eval(self, name: str) -> None:
        if not any(e["name"] == name for e in self.auto_evals):
            return
        self._auto_select_eval(name)
        dpg.set_value(self.auto_name, name)
        self._auto_show_job()

    def auto_delete_eval(self) -> None:
        ev = self._auto_eval()
        if ev is None:
            return
        for job in self._auto_eval_jobs(ev):
            self.auto_jobs.remove(job)
            self.auto_engines.pop(id(job), None)
        self.auto_evals.remove(ev)
        self.auto_eval_name = self.auto_evals[0]["name"] if self.auto_evals else ""
        self.auto_sel, self.auto_engine = 0, None
        if not self.auto_jobs:
            self.auto_stats, self.auto_mode_stats = {}, {}
        self._auto_select_eval(self.auto_eval_name)
        dpg.set_value(self.auto_name, "")
        self._auto_show_job()
        self._message(t("Auto: Auswertung {name} entfernt (Ergebnisse und Verzeichnisregel bleiben).", name=ev["name"]))

    def auto_add_job(self, name: str, source: str, target: str, mode: str = "", target_time: str = "24h") -> dict:
        """Auswertung mit genau einem Quellordner ohne Verzeichnisregel (ältere Einstellungen, Skripte, Tests)."""
        name = self._auto_unique_eval(name)
        self.auto_evals.append({"name": name, "rule": ""})
        job = {"name": self._auto_unique(name), "source": source, "target": target, "mode": mode,
               "target_time": target_time, "enabled": True, "rule": "", "evaluation": name}
        self.auto_jobs.append(job)
        self._auto_select_eval(name)
        if dpg.does_item_exist("auto_window"):
            self._auto_show_job()
        return job

    def _auto_unique_eval(self, name: str) -> str:
        used = {e["name"] for e in self.auto_evals}
        candidate, number = name, 2
        while candidate in used:
            candidate = f"{name} ({number})"
            number += 1
        return candidate

    def _auto_rule_info(self, ev: dict | None) -> str:
        """Angaben der Verzeichnisregel zur Information (Quelle, Ziel, Einlesen, Auswertungen)."""
        if ev is None:
            return "-"
        jobs = self._auto_eval_jobs(ev)
        rule = self._auto_rule_get(ev.get("rule") or "") if ev.get("rule") else None
        if rule is None:
            if jobs:                                       # ohne Regel (ältere Einstellungen)
                lines = [t("Ohne Verzeichnisregel (ältere Einstellung):")]
                lines += [f"{j['source'] or '-'} -> {j['target'] or '-'}" for j in jobs[:6]]
                return "\n".join(lines)
            return t("Noch keine Verzeichnisregel gewählt.")
        if rule.version >= 2:
            target = os.path.join(rule.base or "-", rule.template or "")
            read = t("alle Dateien") if not rule.excluded else t("{count} Dateien ausgeschlossen", count=len(rule.excluded))
            off = t(", {count} Zielordner abgewählt", count=len(rule.deselected)) if rule.deselected else ""
        else:
            target = rule.base or "-"
            read = t("alle Dateien")
            off = ""
        modes = len({self._auto_mode_name(j) for j in jobs})
        active = sum(1 for j in jobs if j.get("enabled", True))
        return "\n".join([t("Quellverzeichnis: {path}", path=rule.root or "-"),
                          t("Zielverzeichnis: {path}", path=target),
                          t("Einlesen: {text}{off}", text=read, off=off),
                          t("{count} Zielordner ({active} aktiv), {modes} Modes", count=len(jobs), active=active,
                            modes=modes)])

    def _auto_show_job(self) -> None:
        """Schritt 1 und 2 der gewählten Auswertung anzeigen (Hinweise, Regel, Info, Modes)."""
        if not dpg.does_item_exist("auto_window"):
            return
        names = [e["name"] for e in self.auto_evals]
        ev = self._auto_eval()
        dpg.configure_item(self.auto_eval_combo, items=names)
        dpg.set_value(self.auto_eval_combo, ev["name"] if ev else "")
        dpg.set_value(self.auto_eval_hint, "" if names else t("Noch keine Auswertung - oben einen Namen eingeben und "
                                                              "Anlegen drücken."))
        if not names and not dpg.get_value(self.auto_name).strip():
            dpg.set_value(self.auto_name_hint, t("Ein Name ist notwendig."))
        else:
            dpg.set_value(self.auto_name_hint, "")
        rules = self._auto_rule_names()
        if ev is not None and ev.get("rule") and ev["rule"] not in rules:
            ev["rule"] = ""                                # Regel gelöscht
        dpg.configure_item(self.auto_rule, items=rules)
        dpg.set_value(self.auto_rule, ev.get("rule", "") if ev else "")
        if not rules:
            hint = t("Noch keine Verzeichnisregel - mit Verzeichnisregel verwalten... erstellen.")
        elif ev is not None and not ev.get("rule") and not self._auto_eval_jobs(ev):
            hint = t("Verzeichnisregel wählen (oder neue erstellen).")
        else:
            hint = ""
        dpg.set_value(self.auto_rule_hint, hint)
        dpg.set_value(self.auto_info, self._auto_rule_info(ev))
        dpg.set_value(self.auto_modes_text, self._auto_modes_summary())
        if dpg.does_item_exist("auto_modes_window") and dpg.is_item_shown("auto_modes_window"):
            self._auto_modes_fill()                       # andere Auswertung gewählt: Liste nachziehen
        job = self._auto_job()
        self.auto_engine = self.auto_engines.get(id(job))
        self._auto_refresh()

    # ---------------------------------------------------------------- Verzeichnisregel der Auswertung
    def _auto_rule_names(self) -> list[str]:
        return [r.get("name", "") for r in (self.settings.get("auto_dirrules") or {}).get("rules", []) if r.get("name")]

    def _auto_rule_get(self, name: str) -> "dirrules.Rule | None":
        data = next((r for r in (self.settings.get("auto_dirrules") or {}).get("rules", []) if r.get("name") == name), None)
        return dirrules.Rule.from_dict(data) if data else None

    def _auto_rule_matches(self, rule: "dirrules.Rule") -> list:
        if not rule.root or not os.path.isdir(rule.root):
            return []
        return [m for m in dirrules.apply(rule, count=False) if not m.error]

    def _auto_set_rule(self, value: str) -> None:
        """Verzeichnisregel der gewählten Auswertung: jeder Zielordner der Regel wird ein Teil der Auswertung."""
        ev = self._auto_eval()
        if ev is None:
            dpg.set_value(self.auto_rule, "")
            self._message(t("Auto: zuerst eine Auswertung anlegen oder wählen (Name, Anlegen)."), error=True)
            return
        rule = self._auto_rule_get(value)
        if rule is None:
            return
        ev["rule"] = rule.name
        self._auto_read_form()
        self._auto_rule_sync(rule, ev)

    def _auto_rule_sync(self, rule: "dirrules.Rule", ev: dict | None = None, quiet: bool = False) -> int:
        """Auswertung(en) mit dieser Regel nachziehen: je Zielordner (Regel v2) bzw. Quellordner (ältere Regel) ein
        Teil. Vorhandene Teile bleiben mit ihren gelesenen Daten (nur neue Daten werden gelesen), neue kommen hinzu,
        abgewählte oder verschwundene fallen heraus."""
        evs = [ev] if ev is not None else [e for e in self.auto_evals if e.get("rule") == rule.name]
        total = 0
        for e in evs:
            total += self._auto_rule_sync_one(rule, e, quiet)
        self._auto_dedupe()
        self._auto_store()
        self._save_settings()
        if dpg.does_item_exist("auto_window"):
            self._auto_show_job()
        return total

    def _auto_rule_units(self, rule: "dirrules.Rule", ev: dict) -> list[dict]:
        """Teile einer Auswertung aus der Regel: dicts mit name, source, folders, exclude, target, mode."""
        norm = os.path.normpath
        if rule.version >= 2:
            units = [u for u in dirrules.plan(rule, ev["name"]) if u.active and not u.error]
            out = []
            for u in units:
                folders = [norm(f) for f in u.folders]
                try:
                    common = os.path.commonpath(folders) if len(folders) > 1 else folders[0]
                except ValueError:
                    common = folders[0]
                out.append({"name": u.name, "source": common, "folders": folders, "exclude": [norm(x) for x in u.excluded],
                            "files": [norm(x) for x in u.paths] if u.split else [],   # Ordner auf mehrere Ziele verteilt
                            "target": u.target, "mode": u.mode, "key": u.target})
            return out
        matches = [m for m in self._auto_rule_matches(rule) if dirrules.count_files(m.source, limit=1)]
        return [{"name": m.name, "source": m.source, "folders": [], "exclude": [], "files": [],
                 "target": m.target or os.path.join(str(AUTO_BASE), m.name), "mode": m.mode, "key": m.source}
                for m in matches]

    def _auto_rule_sync_one(self, rule: "dirrules.Rule", ev: dict, quiet: bool) -> int:
        units = self._auto_rule_units(rule, ev)
        if not units:
            if not quiet:
                self._message(t("Auto: Regel {name} findet keine Ordner mit Messdateien unter {path}.", name=rule.name,
                                path=rule.root or "-"), error=True)
            return 0
        norm = lambda p: os.path.normcase(os.path.abspath(p)) if p else ""
        mine = self._auto_eval_jobs(ev)
        key_of = (lambda j: norm(j.get("target"))) if rule.version >= 2 else (lambda j: norm(j.get("source")))
        by_key = {key_of(j): j for j in mine}
        goals = {}
        for j in mine:                                     # Zielvorgabe und verarbeiten je Mode bleiben
            goals.setdefault(self._auto_mode_name(j), []).append(j)
        keep, created = [], 0
        for unit in units:
            job = by_key.pop(norm(unit["key"]), None)
            if job is None:
                goal = self._mode_goal(goals.get(unit["mode"]) or [])   # neuer DUT übernimmt Zähler/Ziel des Modes
                job = {"name": "", "target_time": goal["time"], "enabled": True, "mode": "", "goal_kind": goal["kind"],
                       "target_edges": goal["edges"]}
                self.auto_jobs.append(job)
                created += 1
                same_mode = [j for j in mine if self._auto_mode_name(j) == unit["mode"]]
                if same_mode:
                    job["enabled"] = any(j.get("enabled", True) for j in same_mode)
            job.update(source=unit["source"], folders=unit["folders"], exclude=unit["exclude"], files=unit["files"],
                       target=unit["target"],
                       rule=rule.name, rule_mode=unit["mode"], evaluation=ev["name"])
            job["name"] = self._auto_unique(unit["name"], skip=job)
            keep.append(job)
        for job in by_key.values():                        # abgewählt oder nicht mehr vorhanden
            self.auto_jobs.remove(job)
            self.auto_engines.pop(id(job), None)
        if keep and self._auto_eval() is ev:
            self.auto_sel = self.auto_jobs.index(keep[0])
        if not quiet:
            self._message(t("Auto: Auswertung {name}, Regel {rule}: {count} Zielordner ({new} neu, {gone} entfallen).",
                            name=ev["name"], rule=rule.name, count=len(keep), new=created, gone=len(by_key)))
        elif created:
            for job in keep[-created:]:
                engine = self.auto_engines.get(id(job))
                if engine is not None:
                    engine.log(t("Neuer Ordner aus Regel {rule}: {path}", rule=rule.name, path=job["source"]))
        return len(keep)

    def _auto_resync_rules(self) -> None:
        """Vor einem Zyklus: neue Ordner der Verzeichnisregeln aufnehmen (nur neue Daten werden gelesen)."""
        for ev in list(self.auto_evals):
            rule = self._auto_rule_get(ev.get("rule") or "") if ev.get("rule") else None
            if rule is not None and rule.version >= 2 and rule.root and os.path.isdir(rule.root):
                try:
                    self._auto_rule_sync_one(rule, ev, quiet=True)
                except OSError as exc:
                    log_exception("Verzeichnisregel", exc)
        self._auto_store()

    def _auto_unique(self, name: str, skip: dict | None = None) -> str:
        used = {j["name"] for j in self.auto_jobs if j is not skip}
        base, number, candidate = name, 2, name
        while candidate in used:
            candidate = f"{base} ({number})"
            number += 1
        return candidate

    @staticmethod
    def _auto_start_dir(current: str) -> str:
        """Ordnerauswahl: beim eingetragenen Ordner beginnen, sonst im Basisordner Programmordner\\Test."""
        if current and os.path.isdir(current):
            return current
        try:
            AUTO_BASE.mkdir(parents=True, exist_ok=True)
        except OSError:
            return str(Path.home())
        return str(AUTO_BASE)

    # ---------------------------------------------------------------- Schritt 2: Modes und Zielzeiten
    @staticmethod
    def _mode_group(mode: str) -> str:
        """Gruppe ähnlicher Modes: Name ohne die hinteren Teile mit Zahlen (AC_22kW_3ph_615V -> AC)."""
        parts = [p for p in re.split(r"[_\s]+", mode) if p]
        while len(parts) > 1 and re.search(r"\d", parts[-1]):
            parts.pop()
        return "_".join(parts) or mode

    def _auto_eval_modes(self) -> dict:
        """Mode -> Teile (DUTs) der gewählten Auswertung, sortiert."""
        modes = {}
        for job in sorted(self._auto_eval_jobs(), key=lambda j: (self._auto_mode_name(j).casefold(), j["name"].casefold())):
            modes.setdefault(self._auto_mode_name(job), []).append(job)
        return modes

    @staticmethod
    def _goal_hms(text: str) -> str:
        """Gespeicherte Zielzeit als hh:mm:ss (Schritte bleiben eine Zahl), leer = offen."""
        if not text:
            return ""
        try:
            steps, seconds = limitconfig.parse_steps(text)
        except ValueError:
            return text
        if seconds:
            total = int(round(seconds))
            return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"
        return f"{steps:g}" if steps else ""

    @staticmethod
    def _parse_goal(text: str) -> str:
        """Eingabe hh:mm:ss (auch 24h, 7h 18m oder Schritte) -> gespeicherte Zielzeit; ungültig -> ValueError."""
        text = (text or "").strip()
        if not text:
            return ""
        found = re.fullmatch(r"(\d+):([0-5]?\d):([0-5]?\d)", text)
        if found:
            seconds = int(found.group(1)) * 3600 + int(found.group(2)) * 60 + int(found.group(3))
            if seconds <= 0:
                raise ValueError(text)
            return limitconfig.format_time(seconds)
        steps, seconds = limitconfig.parse_steps(text)
        if not steps and not seconds:
            raise ValueError(text)
        return text

    def open_auto_modes(self) -> None:
        """Liste der Modes (Häkchen, Zielzeit hh:mm:ss) in einem eigenen Fenster neben dem Auto-Fenster öffnen."""
        self._auto_modes_fill()
        vw, vh = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
        w, h = min(700, int(vw * 0.6)), min(560, int(vh * 0.8))
        dpg.configure_item("auto_modes_window", show=True, width=w, height=h,
                           pos=[max(0, (vw - w) // 2 + 120), max(0, (vh - h) // 3)])
        if hasattr(dpg, "focus_item"):
            dpg.focus_item("auto_modes_window")

    def _auto_modes_fill(self) -> None:
        """Inhalt der Mode-Liste (Dropdown): Gruppen ähnlicher Modes, je Mode Häkchen, Zielzeit hh:mm:ss, DUTs."""
        if not dpg.does_item_exist(getattr(self, "auto_modes_box", 0) or 0):
            return
        dpg.delete_item(self.auto_modes_box, children_only=True)
        self.auto_mode_rows = {}
        modes = self._auto_eval_modes()
        if not modes:
            dpg.add_text(t("Noch keine Modes - zuerst in Schritt 1 die Verzeichnisregel wählen."), parent=self.auto_modes_box)
            return
        groups = {}
        for mode in modes:
            groups.setdefault(self._mode_group(mode), []).append(mode)
        for group in sorted(groups, key=str.casefold):
            members = groups[group]
            with dpg.tree_node(label=f"{group} ({len(members)})", default_open=True, parent=self.auto_modes_box):
                for mode in members:
                    jobs = modes[mode]
                    on = any(j.get("enabled", True) for j in jobs)
                    spec = self._mode_goal(jobs)
                    with dpg.group(horizontal=True):
                        box = dpg.add_checkbox(label=mode, default_value=on, user_data=mode,
                                               callback=lambda s, v, u: self._auto_mode_toggle(u, v))
                        kind = dpg.add_combo(items=self._goal_kind_labels(), width=110, user_data=mode,
                                             default_value=self._goal_kind_label(spec["kind"]),
                                             callback=lambda s, v, u: self._auto_mode_kind(u, v))
                        field = dpg.add_input_text(default_value=self._goal_text(spec), width=100,
                                                   hint=self._goal_hint(spec["kind"]), user_data=mode,
                                                   callback=lambda s, v, u: self._auto_mode_goal(u, v))
                        dpg.add_text(t("{count} DUT", count=len(jobs)))
                        edges = dpg.add_button(label=t("Flanken..."), small=True, user_data=mode,
                                               show=spec["kind"] == "edges",
                                               callback=lambda s, a, u: self.open_auto_edges_window(u))
                        self._tooltip(edges, t("Signale, Werteband (Wert1, Wert2) und Mindestanzahl n für den "
                                               "Flanken Counter dieses Modes festlegen."))
                        note = dpg.add_text("")
                        self._colour(note, "error")
                        info = dpg.add_text("")
                        self._colour(info, "text_dim")
                    self.auto_mode_rows[mode] = (box, field, note, kind, info, edges)
                    self._auto_goal_notes(mode)

    def _auto_mode_specs(self, mode: str) -> list:
        """Die Teile (DUTs) eines Modes: sie tragen verarbeiten, Zähler und Ziel."""
        return list(self._auto_eval_modes().get(mode, []))

    def _auto_mode_toggle(self, mode: str, value: bool) -> None:
        for spec in self._auto_mode_specs(mode):
            spec["enabled"] = bool(value)
        self._auto_goal_notes(mode)
        self._auto_modes_changed()

    def _auto_mode_kind(self, mode: str, label: str) -> None:
        """Zähler wählen: Zeit, Flanke oder Ignorieren (keine Bewertung). Gilt sofort für alle Teile des Modes."""
        key = self._goal_kind_key(label)
        for spec in self._auto_mode_specs(mode):
            spec["goal_kind"] = key
        specs = self._auto_mode_specs(mode)
        if specs:
            self._auto_row_sync(mode, specs[0])
        self._auto_goal_notes(mode)
        self._auto_modes_changed()
        if key == "edges" and not self._auto_edges_valid(mode) and dpg.does_item_exist("auto_edges_window"):
            self.open_auto_edges_window(mode)             # Flanken gleich festlegen

    def _auto_mode_goal(self, mode: str, text: str) -> None:
        row = getattr(self, "auto_mode_rows", {}).get(mode)
        specs = self._auto_mode_specs(mode)
        kind = self._mode_goal(specs)["kind"] if specs else "time"
        if kind == "ignore":
            return
        try:
            for spec in specs:
                self._goal_store(spec, kind, text)
        except ValueError:
            if row is not None:
                dpg.set_value(row[2], self._goal_error(kind))
            return
        self._auto_goal_notes(mode)
        self._auto_modes_changed()

    # ---- Zielvorgabe je Mode: Zeit, Flankenzahl oder Ignorieren; leer = unendlich (keine Violation)
    GOAL_KINDS = ("time", "edges", "ignore")

    @staticmethod
    def _goal_kind_labels() -> list:
        return [t("Zeit"), t("Flanke"), t("Ignorieren")]

    def _goal_kind_label(self, key: str) -> str:
        return dict(zip(self.GOAL_KINDS, self._goal_kind_labels())).get(key, t("Zeit"))

    def _goal_kind_key(self, label: str) -> str:
        if label in self.GOAL_KINDS:
            return label
        return dict(zip(self._goal_kind_labels(), self.GOAL_KINDS)).get(label, "time")

    @staticmethod
    def _goal_hint(kind: str) -> str:
        return {"edges": t("Anzahl"), "ignore": ""}.get(kind, "hh:mm:ss")

    @staticmethod
    def _goal_error(kind: str) -> str:
        return t("ganze Zahl ab 1 erwartet") if kind == "edges" else t("hh:mm:ss erwartet")

    @staticmethod
    def _parse_edges(text) -> str:
        """Flankenzahl: ganze Zahl ab 1 oder leer (unendlich); ungültig -> ValueError."""
        text = str(text or "").strip().replace(".", "")
        if not text:
            return ""
        number = int(text)
        if number < 1:
            raise ValueError(text)
        return str(number)

    def _goal_store(self, spec: dict, kind: str, text) -> None:
        """Eingabe zur Zielart speichern (Zeit oder Flankenzahl); ungültig -> ValueError, nichts geändert."""
        if kind == "edges":
            spec["target_edges"] = self._parse_edges(text)
        elif kind == "time":
            spec["target_time"] = self._parse_goal(text)
        spec["goal_kind"] = kind if kind in self.GOAL_KINDS else "time"

    @staticmethod
    def _mode_goal(specs) -> dict:
        """Zielvorgabe eines Modes aus seinen Teilen: {"kind", "time", "edges"}; ältere Einstellungen ohne Zielart
        = Zeit."""
        specs = list(specs)
        kind = next((x.get("goal_kind") for x in specs if x.get("goal_kind")), "time")
        return {"kind": kind, "time": next((x.get("target_time") for x in specs if x.get("target_time")), ""),
                "edges": next((str(x.get("target_edges")) for x in specs if x.get("target_edges")), "")}

    def _goal_text(self, goal: dict) -> str:
        return goal["edges"] if goal["kind"] == "edges" else (self._goal_hms(goal["time"]) if goal["kind"] == "time"
                                                              else "")

    def _goal_display(self, goal: dict) -> str:
        """Für Zusammenfassungen: 24:00:00, 25 Flanken, unendlich oder ignoriert."""
        if goal["kind"] == "ignore":
            return t("ignoriert")
        if goal["kind"] == "edges":
            return t("{count} Flanken", count=goal["edges"]) if goal["edges"] else t("unendlich (Flanken)")
        return self._goal_hms(goal["time"]) if goal["time"] else t("unendlich")

    def _auto_row_sync(self, mode: str, spec: dict) -> None:
        """Zähler, Eingabefeld und Flanken-Knopf einer Zeile an die gespeicherte Vorgabe anpassen."""
        row = getattr(self, "auto_mode_rows", {}).get(mode)
        if row is None or len(row) < 4:
            return
        goal = self._mode_goal([spec])
        kind = goal["kind"]
        dpg.set_value(row[0], bool(spec.get("enabled", True)))
        dpg.set_value(row[3], self._goal_kind_label(kind))
        dpg.set_value(row[1], self._goal_text(goal))
        dpg.configure_item(row[1], hint=self._goal_hint(kind), enabled=kind != "ignore")
        if len(row) > 5:
            dpg.configure_item(row[5], show=kind == "edges")

    def _auto_goal_notes(self, mode: str) -> None:
        """Hinweise einer Zeile: Fehler leeren, Info zu unendlich, Ignorieren und den Flanken des Modes."""
        row = getattr(self, "auto_mode_rows", {}).get(mode)
        if row is None:
            return
        specs = self._auto_mode_specs(mode)
        goal = self._mode_goal(specs)
        on = any(x.get("enabled", True) for x in specs) if specs else bool(dpg.get_value(row[0]))
        dpg.set_value(row[2], "")
        if len(row) < 5:
            return
        if not on:
            info = t("wird nicht verarbeitet")
        elif goal["kind"] == "ignore":
            info = t("keine Bewertung (kein Zähler, keine Violation)")
        elif goal["kind"] == "edges":
            if not self._auto_edges_valid(mode):
                info = ""
                dpg.set_value(row[2], t("Flanken fehlen - Flanken... drücken"))
            else:
                info = (t("Ziel unendlich - ") if not goal["edges"] and not self._edges_have_target(mode) else "") + \
                    self._auto_edges_summary(mode)
        else:
            info = "" if goal["time"] else t("unendlich - keine Violation möglich")
        dpg.set_value(row[4], info)

    def _edges_have_target(self, mode: str) -> bool:
        return any(e.get("target") for e in self._auto_edges_valid(mode))

    def _auto_edge_problems(self, modes: dict) -> list:
        """Verarbeitete Modes mit Zähler Flanke, aber ohne gültige Flanke."""
        return [m for m, jobs in modes.items() if any(j.get("enabled", True) for j in jobs)
                and self._mode_goal(jobs)["kind"] == "edges" and not self._auto_edges_valid(m)]

    def _auto_modes_all(self, value: bool) -> None:
        for mode in self._auto_eval_modes():
            self._auto_mode_toggle(mode, value)
            row = getattr(self, "auto_mode_rows", {}).get(mode)
            if row is not None:
                dpg.set_value(row[0], bool(value))

    def _auto_modes_goal_all(self) -> None:
        text = dpg.get_value(self.auto_modes_goal_all).strip()
        try:
            self._parse_goal(text)
        except ValueError:
            self._message(t("Zielzeit: hh:mm:ss erwartet, z. B. 24:00:00."), error=True)
            return
        for mode, jobs in self._auto_eval_modes().items():
            if any(j.get("enabled", True) for j in jobs) and self._mode_goal(jobs)["kind"] == "time":
                self._auto_mode_goal(mode, text)
                row = getattr(self, "auto_mode_rows", {}).get(mode)
                if row is not None:
                    dpg.set_value(row[1], self._goal_hms(self._parse_goal(text)))

    def _auto_modes_changed(self) -> None:
        self._auto_store()
        self._save_settings()
        dpg.set_value(self.auto_modes_text, self._auto_modes_summary())
        if dpg.does_item_exist(getattr(self, "auto_modes_state2", 0) or 0):
            dpg.set_value(self.auto_modes_state2, self._auto_modes_summary().split("\n")[0])
        self._auto_refresh()

    def _auto_modes_summary(self) -> str:
        modes = self._auto_eval_modes()
        if not modes:
            return ""
        on = {m: jobs for m, jobs in modes.items() if any(j.get("enabled", True) for j in jobs)}
        missing = [m for m, jobs in on.items() if self._goal_infinite(jobs)]
        parts = []
        for mode, jobs in modes.items():
            state = self._goal_display(self._mode_goal(jobs)) if mode in on else "-"
            parts.append(f"{mode}: {state}" + ("" if mode in on else " " + t("(nicht verarbeiten)")))
        head = t("{count} Modes, {on} verarbeiten, {missing} ohne Zielvorgabe (unendlich)", count=len(modes),
                 on=len(on), missing=len(missing))
        return head + "\n" + " | ".join(parts)

    def _auto_set_json_dir(self, folder: str) -> None:
        name = os.path.basename(self.auto_settings.json_name or "") or self.AUTO_JSON_DEFAULT
        dpg.set_value(self.auto_json, os.path.join(folder, name))
        self._auto_read_form()

    def _auto_json_default(self) -> None:
        dpg.set_value(self.auto_json, self.AUTO_JSON_DEFAULT)
        self._auto_read_form()

    def analyze_auto_source(self, readjust: bool = False) -> None:
        """Quellordner der gewählten Auswertung lesen (im Hintergrund) und die Signale im Konfigurator bereitstellen.
        Der Limiter gilt dabei: Grenzen werden aus den Abschnitten im Limit vorgeschlagen.
        readjust=True: Grenzen des Modes der Auswertung neu aus den (gekürzten) Daten vorschlagen.
        Mit Verzeichnisregel: alle zu verarbeitenden Auswertungen der Regel (alle Modes, alle DUTs) nacheinander."""
        self._auto_read_form()
        job = self._auto_job()
        if job.get("rule") and not getattr(self, "auto_batch", None):
            jobs = [j for j in self._auto_rule_jobs(job) if j.get("enabled", True) and j.get("source")]
            if not jobs:
                self._message(t("Auto: Kein Mode der Regel ist zum Verarbeiten gewählt."), error=True)
                return
            if self._auto_busy():
                self._message(t("Auto: Es läuft bereits ein Zyklus."))
                return
            self.auto_batch = {"jobs": jobs, "index": 0, "readjust": readjust, "back": job}
            self._auto_batch_next()
            return
        self._auto_analyze_job(job, readjust)

    def _auto_batch_next(self) -> None:
        batch = self.auto_batch
        if batch["index"] >= len(batch["jobs"]):
            self.auto_batch = None
            back = batch["back"]
            if back in self.auto_jobs:
                self.auto_sel = self.auto_jobs.index(back)
                self._auto_show_job()
            self._auto_batch_apply(batch)
            modes = len({self._auto_mode_name(j) for j in batch["jobs"]})
            if dpg.does_item_exist("auto_window"):
                dpg.set_value(self.auto_analysis_text, t("Analyse fertig: {count} Auswertungen, {modes} Modes.",
                                                         count=len(batch["jobs"]), modes=modes))
            self.le_edit_mode = self._auto_mode(back) if back in self.auto_jobs else self.le_edit_mode
            self.open_limit_editor()
            added, changed = batch.get("summary", ([], []))
            text = t("Auto: Analyse fertig - {count} Auswertungen in {modes} Modes; Grenzen im Grenzwert-Konfigurator "
                     "prüfen und speichern.", count=len(batch["jobs"]), modes=modes)
            if added:
                text += " " + t("Neue Modes mit Vorschlägen: {names}.", names=", ".join(added))
            if changed:
                text += " " + t("Ergänzt/neu vorgeschlagen: {names}.", names=", ".join(changed))
            if batch.get("failed"):
                text += " " + t("Übersprungen (Quelle fehlt): {names}.", names=", ".join(batch["failed"]))
            self._message(text, error=bool(batch.get("failed")))
            return
        job = batch["jobs"][batch["index"]]
        batch["index"] += 1
        if not self._auto_analyze_job(job, batch["readjust"]):
            batch.setdefault("failed", []).append(job["name"])
            self._auto_batch_next()                       # Quelle fehlt: nächste Auswertung
            return
        if dpg.does_item_exist("auto_window"):
            dpg.set_value(self.auto_analysis_text, t("Analysiere {n}/{total}: {name}", n=batch["index"],
                                                     total=len(batch["jobs"]), name=job["name"]))

    def _auto_batch_collect(self, job: dict, stats: dict) -> None:
        """Analyse einer Auswertung der Regel: Kennwerte je Mode über alle DUTs sammeln."""
        mode = self._auto_mode_name(job)
        merged = self.auto_batch.setdefault("stats", {}).setdefault(mode, {})
        for name, entry in stats.items():
            have = merged.get(name)
            if have is None:
                merged[name] = dict(entry, files=list(entry["files"]))
                continue
            have["files"] += entry["files"]
            values = [v for v in (have.get("values"), entry.get("values")) if v is not None and len(v)]
            have["values"] = np.concatenate(values) if values else have.get("values")
            for key, pick in (("min", min), ("max", max)):
                both = [v for v in (have.get(key), entry.get(key)) if v is not None]
                have[key] = pick(both) if both else None
        job["mode"] = ""

    def _auto_keep_mode_stats(self, mode: str, stats: dict) -> None:
        """Datenbereich je Signal für den Mode merken (Grenzen aus Daten für alle Modes vorschlagen)."""
        kept = {}
        for name, entry in stats.items():
            label = entry.get("label", name)
            unit = label[len(name):].strip(" []") if label.startswith(name) else ""
            kept[name] = (unit, list(entry.get("files", [])), entry.get("min"), entry.get("max"))
        self.auto_mode_stats[mode] = kept

    def _auto_batch_apply(self, batch: dict) -> None:
        """Nach der Analyse aller Auswertungen der Regel: je Mode Vorschläge aus den Daten aller DUTs
        (neuer Mode: alle Signale mit Grenzen; vorhandener Mode: fehlende Signale ergänzen bzw. bei Grenzen neu
        vorschlagen alle Grenzen neu, aktiv/inaktiv bleibt). Zielzeit je Mode aus der Auto-Auswertung (sonst 24h)."""
        added, changed = [], []
        for mode, stats in (batch.get("stats") or {}).items():
            jobs = [j for j in batch["jobs"] if self._auto_mode_name(j) == mode]
            goal = self._goal_target(jobs[0]) if jobs else ""
            if self.limit_cfg is None:
                self.limit_cfg = auto.AutoEngine.propose_from_stats(stats, mode, goal)
                added.append(mode)
                continue
            if mode not in self.limit_cfg.modes:
                self.limit_cfg.modes[mode] = auto.AutoEngine.propose_from_stats(stats, mode, goal).modes[mode]
                self.limit_cfg.modified = True
                added.append(mode)
                continue
            spec = self.limit_cfg.modes[mode]
            for name, entry in stats.items():
                old = spec.entries.get(name)
                if old is not None and not batch.get("readjust"):
                    continue
                lo, hi = auto.AutoEngine.suggest_limits(entry.get("values"))
                if lo is None:
                    continue
                spec.set_entry(name, old.enabled if old is not None else True, lo, hi)
                self.limit_cfg.modified = True
                if mode not in changed:
                    changed.append(mode)
        if added or changed:
            self._refresh_mode_combo()
        for mode, stats in (batch.get("stats") or {}).items():
            self._auto_keep_mode_stats(mode, stats)
        back = batch["back"]
        own = self._auto_mode_name(back)
        self.auto_stats = {}
        for name, entry in (batch.get("stats") or {}).get(own, {}).items():
            label = entry["label"]
            unit = label[len(name):].strip(" []") if label.startswith(name) else ""
            self.auto_stats[name] = (unit, entry["files"], entry["min"], entry["max"], entry["values"])
        batch["summary"] = (added, changed)
        self._auto_store()

    def _auto_analyze_job(self, job: dict, readjust: bool = False) -> bool:
        if not job["source"] or not os.path.isdir(job["source"]):
            self._message(t("Auto: Quellverzeichnis nicht gefunden: {path}", path=job["source"] or "-"), error=True)
            return False
        if self._auto_busy():
            self._message(t("Auto: Es läuft bereits ein Zyklus."))
            return False
        if self.auto_pool is None:
            self.auto_pool = ThreadPoolExecutor(max_workers=1)
        engine = self._auto_engine_for(job)
        self.auto_running_engine = engine
        self.auto_analysis_job = job
        self.auto_readjust = bool(readjust)
        import copy
        lim = copy.deepcopy(self.limiter) if self.limiter is not None else None
        self.auto_analysis = self.auto_pool.submit(engine.analyze, lim)
        if dpg.does_item_exist("auto_window"):
            dpg.set_value(self.auto_analysis_text, t("Analysiere Quellordner..."))
        self._message(t("Auto: Analysiere {path}...", path=job["source"]))
        return True

    # ---------------------------------------------------------------- Modes einer Verzeichnisregel
    def _auto_rule_jobs(self, job: dict | None = None, mode: str | None = None) -> list[dict]:
        """Teile derselben Auswertung (optional nur eines Modes), sortiert nach Mode und Name."""
        job = job or self._auto_job()
        if job.get("evaluation"):
            jobs = [j for j in self.auto_jobs if j.get("evaluation") == job["evaluation"]]
        elif job.get("rule"):
            jobs = [j for j in self.auto_jobs if j.get("rule") == job["rule"]]
        else:
            return [job]
        jobs = [j for j in jobs if mode is None or self._auto_mode_name(j) == mode]
        return sorted(jobs, key=lambda j: (self._auto_mode_name(j).casefold(), j["name"].casefold()))

    def _auto_rule_modes(self, job: dict | None = None) -> dict:
        """Mode -> Teile (DUTs) der Auswertung."""
        modes = {}
        for j in self._auto_rule_jobs(job):
            modes.setdefault(self._auto_mode_name(j), []).append(j)
        return modes

    def _auto_mode(self, job: dict | None = None) -> str | None:
        """Mode der Auswertung (Grenzen für alle Dateien ihres Quellordners)."""
        job = job or self._auto_job()
        chosen = job.get("mode")
        if chosen and self.limit_cfg is not None and chosen in self.limit_cfg.modes:
            return chosen                                  # ausdrücklich anders gewählt
        return self._auto_mode_name(job)                   # Standard: Mode aus Regel bzw. Name

    @staticmethod
    def _auto_mode_name(job: dict) -> str:
        """Mode eines Teils: {Mode} der Verzeichnisregel; ohne Regel der Name ohne angehängtes _DUTn
        (AC_11_22kW_1ph_615V_DUT1 -> AC_11_22kW_1ph_615V). So teilen sich die DUTs eines Modes dessen Grenzen."""
        if job.get("rule_mode"):
            return re.sub(r"\s+", "_", job["rule_mode"].strip())
        name = re.sub(r"\s+", "_", (job.get("name") or "").strip())
        mode = re.sub(r"[_\-]?DUT\d+$", "", name, flags=re.IGNORECASE).strip("_-")
        return mode or name or "Auto"

    def _auto_goal(self, job: dict):
        """Zielzeit der Auswertung als (Schritte, Sekunden); (None, None) = keine Zielzeit = unendlich (keine
        Violation möglich). Bei Zielart Flankenzahl gibt es keine Zielzeit."""
        if job.get("goal_kind") in ("edges", "ignore"):
            return None, None
        try:
            return limitconfig.parse_steps(job.get("target_time") or None)
        except ValueError:
            return None, None

    def _goal_target(self, job: dict) -> str:
        """Zielzeit für Vorschläge aus den Daten; keine (unendlich, Flankenzahl) = leer."""
        steps, seconds = self._auto_goal(job)
        return job.get("target_time", "") if (steps or seconds) else ""

    def _goal_infinite(self, jobs) -> bool:
        """Mode ohne Zielvorgabe: Zeit bzw. Flankenzahl leer -> unendlich."""
        goal = self._mode_goal(jobs)
        return (goal["kind"] == "time" and not goal["time"]) or (goal["kind"] == "edges" and not goal["edges"])

    def _auto_analyzed(self, stats: dict, result) -> None:
        job = getattr(self, "auto_analysis_job", None) or self._auto_job()
        if getattr(self, "auto_batch", None):              # Regel: erst sammeln, Vorschläge am Ende je Mode
            self.auto_readjust = False
            self._auto_batch_collect(job, stats)
            if result.errors:
                self._message(t("Auto: [{name}] {count} Fehler (siehe Log).", name=job["name"],
                                count=len(result.errors)), error=True)
            return
        engine = self.auto_engines.get(id(job))
        self._auto_keep_mode_stats(self._auto_mode(job), stats)
        self.auto_stats = {}
        for name, entry in stats.items():
            label = entry["label"]
            unit = label[len(name):].strip(" []") if label.startswith(name) else ""
            self.auto_stats[name] = (unit, entry["files"], entry["min"], entry["max"], entry["values"])
        files = sum(len(g.files) for g in engine.groups.values()) if engine else 0
        groups = len(engine.groups) if engine else 0
        summary = t("{files} Dateien, {groups} Gruppen, {signals} Signale", files=files, groups=groups, signals=len(stats))
        if engine:
            sources = {}
            for group in engine.groups.values():
                for data in group.files.values():
                    key = getattr(data, "time_source", "")
                    sources[key] = sources.get(key, 0) + 1
            if sources:
                summary += " | " + t("Zeitstempel: {list}", list=", ".join(f"{n}x {k}" for k, n in sources.items()))
        if result.errors:
            summary += "  " + t("{count} Fehler (siehe Log).", count=len(result.errors))
        goal = self._goal_target(job)
        shares = sorted({e["limited"] for e in stats.values() if e.get("limited") is not None})
        if shares:
            summary += " | " + t("Limiter: {share} % der Messzeit im Limit", share=f"{shares[0] * 100:.1f}")
        mode_name = job.get("mode") if self.limit_cfg is not None and job.get("mode") in self.limit_cfg.modes else None
        readjust, self.auto_readjust = getattr(self, "auto_readjust", False), False
        if readjust and self.limit_cfg is not None and self._auto_mode(job) in self.limit_cfg.modes:
            mode_name = self._auto_mode(job)
            mode = self.limit_cfg.modes[mode_name]
            count = 0
            for name, entry in stats.items():          # aktiv/inaktiv und Zielzeit bleiben, nur die Grenzen neu
                lo, hi = auto.AutoEngine.suggest_limits(entry.get("values"))
                if lo is None:
                    continue
                old = mode.entries.get(name)
                mode.set_entry(name, old.enabled if old is not None else True, lo, hi)
                count += 1
            self.limit_cfg.modified = True
            text = t("Auto: {summary}. Grenzen von {count} Signalen im Mode {mode} neu vorgeschlagen{lim}; bitte prüfen "
                     "und speichern.", summary=summary, count=count, mode=mode_name,
                     lim=t(" (mit Limiter)") if shares else "")
        elif self.limit_cfg is None:                    # keine Konfiguration: alle Signale mit Vorschlägen
            mode_name = self._auto_mode_name(job)
            self.limit_cfg = auto.AutoEngine.propose_from_stats(stats, mode_name, goal)
            self._refresh_mode_combo()
            self.set_limit_mode(mode_name, quiet=True)
            text = t("Auto: {summary}. Keine Grenzwert-Konfiguration geladen - Vorschläge (alle Signale aktiv, Zielzeit "
                     "{goal}) im Grenzwert-Konfigurator, Mode {mode}; bitte prüfen und speichern.", summary=summary,
                     goal=goal or t("unendlich"), mode=mode_name)
        elif mode_name is None:                       # Konfiguration da, aber noch kein Mode für diese Auswertung
            mode_name = self._auto_mode(job)
            if mode_name not in self.limit_cfg.modes:
                proposal = auto.AutoEngine.propose_from_stats(stats, mode_name, goal)
                self.limit_cfg.modes[mode_name] = proposal.modes[mode_name]
                self.limit_cfg.modified = True
                self._refresh_mode_combo()
                text = t("Auto: {summary}. Neuer Mode {mode} mit Vorschlägen (alle Signale aktiv, Zielzeit {goal}) im "
                         "Grenzwert-Konfigurator; bitte prüfen und speichern.", summary=summary, mode=mode_name,
                         goal=goal or t("unendlich"))
            else:
                mode = self.limit_cfg.modes[mode_name]
                missing = [n for n in stats if mode.lookup(n) is None]
                text = t("Auto: {summary}. Grenzwert-Konfiguration {name}, Mode {mode}; {missing} Signale ohne Eintrag.",
                         summary=summary, name=self.limit_cfg.name, mode=mode_name, missing=len(missing))
        else:
            mode = self.limit_cfg.modes[mode_name]
            missing = [n for n in stats if mode.lookup(n) is None]
            text = t("Auto: {summary}. Grenzwert-Konfiguration {name}, Mode {mode}; {missing} Signale ohne Eintrag.",
                     summary=summary, name=self.limit_cfg.name, mode=mode_name, missing=len(missing))
        job["mode"] = mode_name
        if job is self._auto_job():
            self.auto_settings.mode = mode_name
        self._auto_store()
        self.le_edit_mode = mode_name
        if dpg.does_item_exist("auto_window"):
            dpg.set_value(self.auto_analysis_text, summary)
        self.open_limit_editor()
        if dpg.does_item_exist("limiter_window") and dpg.is_item_shown("limiter_window"):
            self._lim_rows()                              # Signale der Analyse gleich im Limiter wählbar
        self._message(f"[{job['name']}] " + text, error=bool(result.errors))
        self._auto_refresh()

    def _auto_read_form(self) -> bool:
        """Allgemeine Eingaben übernehmen (Gruppierung, Schritt 4); ungültige Zykluszeit -> Hinweis."""
        if not dpg.does_item_exist("auto_window"):
            return True
        s, job = self.auto_settings, self._auto_job()
        ok = True
        s.source, s.target, s.mode = job.get("source", ""), job.get("target", ""), job.get("mode", "")
        s.png = bool(dpg.get_value(self.auto_png))
        s.only_hits = bool(dpg.get_value(self.auto_hits))
        s.one_group = bool(dpg.get_value(self.auto_one))
        try:
            s.json_name = self._auto_json_name(dpg.get_value(self.auto_json))
            dpg.set_value(self.auto_json_note, "")
        except ValueError:
            dpg.set_value(self.auto_json_note, t("Dateiname ungültig (keine Zeichen \\ / : * ? \" < > |); es gilt weiter "
                                                 "{value}.", value=s.json_name))
            ok = False
        s.group_regex = dpg.get_value(self.auto_regex).strip()
        try:
            s.cycle_s = max(self.AUTO_MIN_CYCLE, self.parse_cycle(dpg.get_value(self.auto_cycle)))
            dpg.set_value(self.auto_hint, "")
        except ValueError:
            dpg.set_value(self.auto_hint, t("Zykluszeit ungültig (z. B. 60s, 5m, 1h); es gilt weiter {value}.",
                                            value=limitconfig.format_time(s.cycle_s)))
            ok = False
        self._auto_store()
        self._auto_refresh()
        return ok

    def open_auto_window(self, show_log: bool = False) -> None:
        vw, vh = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
        w, h = min(1120, int(vw * 0.9)), min(820, int(vh * 0.9))
        dpg.configure_item("auto_window", show=True, width=w, height=h, pos=[max(0, (vw - w) // 2), max(0, (vh - h) // 4)])
        self._auto_refresh()
        if show_log:                                       # Log steht im Fenster für Schritt 4
            self.open_auto_run_window()
            self._auto_show_log()

    def open_auto_run_window(self) -> None:
        """Fenster für Schritt 4 (Zyklus, Fortschritt, Zähler, Log) neben dem Auto-Fenster öffnen."""
        if not dpg.does_item_exist("auto_run_window"):
            return
        vw, vh = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
        w, h = min(1000, int(vw * 0.8)), min(720, int(vh * 0.85))
        dpg.configure_item("auto_run_window", show=True, width=w, height=h,
                           pos=[max(0, vw - w - 20), max(0, (vh - h) // 3)])
        if hasattr(dpg, "focus_item"):
            dpg.focus_item("auto_run_window")
        self._auto_refresh()

    def _auto_show_log(self) -> None:
        job = self._auto_job()
        engine = self.auto_engines.get(id(job)) or auto.AutoEngine(self._auto_job_settings(job))
        try:
            lines = engine.log_path().read_text(encoding="utf-8").splitlines()[-300:]
            text = f"[{job['name']}]\n" + "\n".join(lines)
        except OSError:
            text = t("Noch kein Log: {path}", path=engine.log_path())
        dpg.set_value(self.auto_log, text)
        if not dpg.is_item_shown("auto_window"):
            self.open_auto_window()

    def _auto_sources_text(self) -> str:
        if self.limit_cfg is not None:
            cfg = t("Grenzwert-Konfiguration: {name} ({count} Modes)", name=self.limit_cfg.name,
                    count=len(self.limit_cfg.modes))
        else:
            cfg = t("Grenzwert-Konfiguration: keine - nach dem ersten Zyklus wird eine aus den Daten vorgeschlagen.")
        if self.limiter and self.limiter.active and any(r.usable for r in self.limiter.rules):
            lim = t("Limiter: aktiv, {count} Regeln", count=sum(1 for r in self.limiter.rules if r.usable))
        else:
            lim = t("Limiter: aus")
        text = f"{cfg}   |   {lim}   |   " + t("Ergebnisdatei: {path}", path=", ".join(self._auto_json_paths()))
        self._auto_json_show()
        if getattr(self, "report_next_due", None) is not None:
            text += "   |   " + getattr(self, "report_plan_text", "")
        return text

    def _auto_refresh(self) -> None:
        if not dpg.does_item_exist("auto_window"):
            return
        dpg.set_value(self.auto_sources, self._auto_sources_text())
        modes = self._auto_eval_modes()
        missing = sum(1 for jobs in modes.values() if any(j.get("enabled", True) for j in jobs)
                      and self._goal_infinite(jobs))
        dpg.set_value(self.auto_modes_state, t("{count} Modes, {missing} ohne Zielvorgabe (unendlich)",
                                               count=len(modes), missing=missing) if modes else "")
        if self.auto_running:
            wait = max(0.0, self.auto_next - time.monotonic())
            busy = self.auto_future is not None and not self.auto_future.done()
            state = t("Läuft - Zyklus wird ausgeführt...") if busy else t("Läuft - nächster Zyklus in {sec} s",
                                                                            sec=f"{wait:.0f}")
        else:
            state = t("Gestoppt.")
        r = self.auto_last
        if r is not None:
            state += "   " + t("Letzter Zyklus: {files} Dateien neu, {png} Bilder, {count} Zähler, {sec} s",
                               files=len(r.new_files), png=r.png_written, count=len(r.counters), sec=f"{r.seconds:.1f}")
        dpg.set_value(self.auto_state, state)
        dpg.configure_item(self.auto_start_btn, enabled=not self.auto_running)
        dpg.configure_item(self.auto_stop_btn, enabled=self.auto_running)

    @staticmethod
    def _hms(seconds) -> str:
        """Sekunden -> h:mm:ss (Stunden ohne Obergrenze, z. B. 180:51:08)."""
        total = int(round(float(seconds)))
        return f"{total // 3600}:{total % 3600 // 60:02d}:{total % 60:02d}"

    def _auto_split_key(self, job: dict, key: str) -> tuple[str, str]:
        """count_<Mode>_<Gruppe> -> (Mode, Gruppe); Mode aus der Konfiguration bzw. dem Teil (längster Treffer)."""
        if key.startswith("edges_"):                       # Flanken Counter: edges_<Signal>_<Gruppe>
            body = key[6:]
            ev = self._auto_eval_get(job.get("evaluation") or "") if job.get("evaluation") else self._auto_eval()
            signals = {str(e.get("signal") or "") for edges in ((ev or {}).get("mode_edges") or {}).values()
                       for e in edges}
            for name in sorted(signals, key=len, reverse=True):
                if name and body.startswith(name + "_"):
                    return name, body[len(name) + 1:]
            return "", body
        body = key[6:] if key.startswith("count_") else key
        modes = set(self.limit_cfg.modes) if self.limit_cfg is not None else set()
        modes.add(self._auto_mode(job) or "")
        for mode in sorted((m for m in modes if m), key=len, reverse=True):
            if body.startswith(mode + "_"):
                return mode, body[len(mode) + 1:]
        return "", body

    def _auto_cell_values(self, job: dict, key: str, entry: dict) -> list[str]:
        """Anzeige einer Zeile: Auswertung, Teil, Mode, Gruppe, Ist, Ziel, Erfüllung (Zeit als h:mm:ss)."""
        mode, group = self._auto_split_key(job, key)
        if key.startswith("edges_"):
            actual, steps, pct = entry.get("actual"), entry.get("steps"), entry.get("fulfillment_percent")
            ist = f"{int(actual):,}".replace(",", ".") if isinstance(actual, (int, float)) else "-"
            if entry.get("pending"):
                ist += " (+1 " + t("offen") + ")"
            ziel = f"{int(steps):,}".replace(",", ".") if isinstance(steps, (int, float)) else "-"
            done = f"{pct:.1f} %" if isinstance(pct, (int, float)) else "-"
            if entry.get("violation"):
                done += " - " + t("Violation")
            return [job.get("evaluation") or "-", job.get("name", ""), mode or "-", group or "-", ist, ziel, done]
        spec = self.limit_cfg.modes.get(mode) if self.limit_cfg is not None else None
        timed = bool(spec is not None and spec.target and spec.target[0] == "s")
        actual, steps, pct = entry.get("actual"), entry.get("steps"), entry.get("fulfillment_percent")
        if timed:
            ist = self._hms(actual) if actual is not None else "-"
            ziel = self._hms(steps) if steps is not None else "-"
        else:
            ist = f"{int(actual):,}".replace(",", ".") if isinstance(actual, (int, float)) else "-"
            ziel = f"{int(steps):,}".replace(",", ".") if isinstance(steps, (int, float)) else "-"
        return [job.get("evaluation") or "-", job.get("name", ""), mode or "-", group or "-", ist, ziel,
                f"{pct:.1f} %" if isinstance(pct, (int, float)) else "-"]

    @staticmethod
    def _edge_tip(entry: dict) -> str:
        lines = []
        if entry.get("upper") is not None:
            lines.append(t("über Wert1 = {value}: {count} Flanken", value=fmt(entry["upper"]),
                           count=entry.get("edges_upper", 0)))
        if entry.get("lower") is not None:
            lines.append(t("unter Wert2 = {value}: {count} Flanken", value=fmt(entry["lower"]),
                           count=entry.get("edges_lower", 0)))
        lines.append(t("mindestens n = {n} Werte je Abschnitt", n=entry.get("n", 1)))
        if entry.get("pending"):
            lines.append(t("Signal steht am Ende jenseits der Schwelle: diese Flanke zählt erst nach der Rückkehr."))
        if entry.get("steps"):
            at = entry.get("edges_to_violation")
            lines.append(t("Flanken bis Violation: {count}", count=t("unendlich") if at is None else f"{at:.0f}") +
                         (f" ({entry['violation_signal']})" if entry.get("violation_signal") else ""))
            lines.append(t("Violation vor Ziel-Flankenzahl!") if entry.get("violation") else
                         t("Keine Violation vor Ziel-Flankenzahl (OK)"))
        return "\n".join(lines)

    def _auto_fill_table(self, rows: list) -> None:
        for row in dpg.get_item_children(self.auto_table, 1) or []:
            dpg.delete_item(row)
        self.coloured_text = [(i, r) for i, r in self.coloured_text if dpg.does_item_exist(i)]
        rows = sorted(rows, key=lambda r: (str(r[0].get("evaluation", "")).casefold(), r[0].get("name", "").casefold(),
                                           r[1].casefold()))
        for job, key, entry in rows:
            cells = self._auto_cell_values(job, key, entry)
            with dpg.table_row(parent=self.auto_table):
                for column, value in enumerate(cells):
                    item = dpg.add_text(value)
                    if column == 3:
                        self._tooltip(item, t("Schlüssel: {key}", key=key))
                    elif column == 4 and key.startswith("edges_"):
                        self._tooltip(item, self._edge_tip(entry))
                    elif column == 6 and value != "-":
                        role = "ok" if float(entry.get("fulfillment_percent") or 0) >= 100 else "error"
                        if entry.get("violation"):
                            role = "error"
                            self._tooltip(item, self._edge_tip(entry))
                        self._colour(item, role)
                        dpg.configure_item(item, color=themes.color(self.mode, role))

    def _auto_problem(self, job: dict) -> str | None:
        if not job["source"] or not os.path.isdir(job["source"]):
            return t("Quellverzeichnis nicht gefunden: {path}", path=job["source"] or "-")
        if not job["target"]:
            return t("Bitte ein Zielverzeichnis wählen.")
        if os.path.abspath(job["target"]) == os.path.abspath(job["source"]):
            return t("Ziel- und Quellverzeichnis müssen verschieden sein.")
        return None

    def _auto_check(self) -> bool:
        """Mindestens eine aktive, vollständige Auswertung; fehlerhafte werden gemeldet und ausgelassen."""
        if not self._auto_read_form():
            return False
        active = [j for j in self.auto_jobs if j["enabled"]]
        if not active:
            self._message(t("Auto: Keine aktive Auswertung."), error=True)
            return False
        missing_edges = self._auto_edge_problems_all()
        if missing_edges:
            self._message(t("Zähler Flanke ohne Flanken bei: {names} (Modes und Zielzeiten..., Flanken...).",
                            names=", ".join(missing_edges)), error=True)
            return False
        problems = [(j, self._auto_problem(j)) for j in active]
        bad = [f"{j['name']}: {p}" for j, p in problems if p]
        if len(bad) == len(active):
            self._message(t("Auto: {text}", text="; ".join(bad)), error=True)
            return False
        for job, problem in problems:
            if not problem:
                if not os.path.isdir(job["target"]):      # fehlender Zielordner: anlegen
                    try:
                        os.makedirs(job["target"], exist_ok=True)
                        self._message(t("Auto: Zielordner angelegt: {path}", path=job["target"]))
                    except OSError as exc:
                        self._message(t("Auto: Zielordner nicht angelegt: {error}", error=exc), error=True)
                        continue
                self._auto_engine_for(job)
        if bad:                                       # zuletzt, damit der Hinweis in der Statuszeile stehen bleibt
            self._message(t("Auto: ausgelassen - {text}", text="; ".join(bad)), error=True)
        self._save_settings()
        return True

    def _auto_ready_jobs(self) -> list:
        return [j for j in self.auto_jobs if j["enabled"] and not self._auto_problem(j)]

    def start_auto(self) -> None:
        if not self._auto_check():
            return
        self.auto_running = True
        self.auto_next = time.monotonic()                 # erster Zyklus sofort
        self._auto_set_step(0)                            # Durchlauf gestartet: alle Schritte frei
        for job in self._auto_ready_jobs():
            self._auto_engine_for(job).log(t("Start: {src} -> {dst}, Zyklus {cycle}", src=job["source"], dst=job["target"],
                                             cycle=limitconfig.format_time(self.auto_settings.cycle_s)))
        self._message(t("Auto-Auswertung gestartet (Zyklus {cycle}).",
                        cycle=limitconfig.format_time(self.auto_settings.cycle_s)))
        self._auto_refresh()

    def stop_auto(self) -> None:
        if self.auto_running:
            for job in self.auto_jobs:
                engine = self.auto_engines.get(id(job))
                if engine is not None:
                    engine.log(t("Stopp."))
        self.auto_running = False
        self._message(t("Auto-Auswertung gestoppt."))
        self._auto_refresh()

    def run_auto_now(self) -> None:
        if self.auto_future is not None and not self.auto_future.done():
            self._message(t("Auto: Es läuft bereits ein Zyklus."))
            return
        if self._auto_check():
            self._auto_submit(force=True)
            self._message(t("Auto: Zyklus wird ausgeführt (alle Dateien, Bilder und Zähler neu)..."))

    def _auto_submit(self, force: bool = False, jobs: list | None = None) -> None:
        """Einen Zyklus für alle aktiven (oder die übergebenen) Auswertungen nacheinander im Hintergrund starten."""
        import copy
        if self.auto_pool is None:
            self.auto_pool = ThreadPoolExecutor(max_workers=1)
        if jobs is None:
            self._auto_resync_rules()                 # neue Ordner der Verzeichnisregeln (nur neue Daten werden gelesen)
            for job in self._auto_ready_jobs():
                if job.get("target") and not os.path.isdir(job["target"]):
                    try:
                        os.makedirs(job["target"], exist_ok=True)
                    except OSError as exc:
                        log_exception("Zielordner", exc)
        jobs = self._auto_ready_jobs() if jobs is None else jobs
        tasks = []
        for job in jobs:
            engine = self._auto_engine_for(job)
            engine.settings.budget_share = auto.AutoSettings.budget_share / max(1, len(jobs))
            mode = self._auto_mode(job)
            # Mode der Auswertung noch nicht in der Konfiguration: Vorschlag aus den Daten unter diesem Namen
            config = copy.deepcopy(self.limit_cfg) if self.limit_cfg is not None and mode in self.limit_cfg.modes else None
            steps, seconds = self._auto_goal(job)
            if config is not None and mode in config.modes:   # Zielzeit der Auswertung; keine = unendlich
                config.modes[mode].steps, config.modes[mode].steps_time = steps, seconds
            tasks.append((dict(job), engine, config, mode))
        lim = copy.deepcopy(self.limiter) if self.limiter is not None else None
        self.auto_future = self.auto_pool.submit(self._auto_run_jobs, tasks, lim, force, self.reg_method)
        self._auto_refresh()

    def _auto_run_jobs(self, tasks: list, lim, force: bool, reg_method: str) -> list:
        """Im Hintergrund: Auswertungen nacheinander (gemeinsame Ergebnisdatei wird so nie gleichzeitig geschrieben)."""
        out = []
        for job, engine, config, mode in tasks:
            self.auto_running_engine = engine
            self.auto_running_job = job["name"]
            try:
                result = engine.run_cycle(config, lim, mode, force=force, reg_method=reg_method,
                                          proposal_name=mode or self._auto_mode_name(job),
                                          proposal_target=self._goal_target(job))
            except Exception as exc:                      # eine Auswertung kaputt: die anderen laufen weiter
                engine.log(t("Fehler: {text}", text=exc))
                result = auto.CycleResult(started=time.time(), errors=[str(exc)])
                result.forced = force
            out.append((job, result))
            if engine.cancel:
                break
        self.auto_running_job = None
        return out

    def cancel_auto(self) -> None:
        """Laufende Analyse bzw. laufenden Zyklus abbrechen (der Rest folgt im nächsten Zyklus)."""
        if not self._auto_busy():
            return
        for engine in list(self.auto_engines.values()) + [self.auto_engine]:
            if engine is not None:
                engine.cancel = True
        self._message(t("Auto: Abbrechen..."))

    def _auto_busy(self) -> bool:
        return any(f is not None and not f.done() for f in (self.auto_analysis, self.auto_future))

    def _auto_progress(self) -> None:
        """Fortschritt von Analyse und Ausgaben: Balken im Auto-Fenster und in der Statuszeile des Hauptfensters."""
        engine = getattr(self, "auto_running_engine", None) or self.auto_engine
        busy = self._auto_busy() and engine is not None
        if dpg.does_item_exist("auto_window"):
            dpg.configure_item(self.auto_progress_row, show=busy)
            dpg.configure_item(self.auto_run_progress_row, show=busy)
        if not busy:
            if getattr(self, "auto_progress_shown", False):
                self.auto_progress_shown = False
                if not self.jobs:
                    dpg.configure_item(self.progress_row, show=False)
            return
        p = engine.progress
        dots = "." * (1 + int(time.monotonic() * 3) % 3)
        if p.get("phase") in self.AUTO_PHASES and p.get("total"):
            fraction = min(1.0, (p["done"] + 0.5) / p["total"])
            text = t("{what} {done}/{total}: {name}", what=t(self.AUTO_PHASES[p["phase"]]), done=p["done"] + 1,
                     total=p["total"], name=p.get("name", ""))
        else:
            what = t("Analysiere Quellordner") if self.auto_analysis is not None else t("Verarbeite Daten")
            fraction, text = (time.monotonic() % 2.0) / 2.0, what + dots    # unbekannte Dauer: Balken läuft
        job = getattr(self, "auto_running_job", None)
        if job and self.auto_analysis is None:
            text = f"[{job}] {text}"
        overlay = f"{int(fraction * 100)} % {dots}" if p.get("total") else dots
        if dpg.does_item_exist("auto_window"):
            for bar in (self.auto_progress, self.auto_run_progress):
                dpg.set_value(bar, fraction)
                dpg.configure_item(bar, overlay=text if len(text) < 90 else text[:87] + "...")
        if not self.jobs:                                  # Statuszeile des Hauptfensters mitnutzen
            self.auto_progress_shown = True
            dpg.set_value(self.progress_bar, fraction)
            dpg.configure_item(self.progress_bar, overlay=overlay)
            dpg.set_value(self.progress_text, t("Auto: {text}", text=text))
            dpg.configure_item(self.progress_row, show=True)

    # ---- Report über mehrere Auswertungen (je Auswertung ein DUT)
    # ---------------------------------------------------------------- Verzeichnisverwalter (Auto)
    def _dir_store(self) -> dict:
        return self.settings.setdefault("auto_dirrules", {"rules": [], "selected": ""})

    DIR_TREE_FILES = 3000             # mehr Dateien: im Baum nur Häkchen je Ordner

    def _build_dir_window(self) -> None:
        store = self._dir_store()
        names = [r.get("name", "") for r in store.get("rules", []) if r.get("name")]
        self.dir_dirs, self.dir_units, self.dir_unit_boxes = [], [], []
        self.dir_file_boxes, self.dir_folder_boxes, self.dir_value_inputs = {}, {}, {}
        self.dir_excluded, self.dir_deselected, self.dir_loaded = set(), set(), None
        self.dir_datetime = ""

        def tip(item, text: str):
            self._tooltip(item, t(text))
            return item

        def head(step: int, title: str, text: str = "") -> None:
            dpg.add_separator()
            item = dpg.add_text(t("Schritt {n}: {title}", n=step, title=t(title)))
            self._colour(item, "heading")
            if text:
                item = dpg.add_text(t(text), wrap=0)
                self._colour(item, "text_dim")

        with dpg.window(tag="dir_window", label=t("Verzeichnisverwalter"), show=False, width=1100, height=860,
                        no_collapse=True):
            item = dpg.add_text(t("Hier wird die Verzeichnisregel definiert: welche Messdateien (Quellordner, Auswahl) "
                                  "wohin ausgewertet werden (Zielordner aus Basis und Platzhaltern wie {Mode}, {DUTx}). "
                                  "Schritte 1 bis 6 der Reihe nach, dann Regel speichern. Die Regel wird in der "
                                  "Auto-Auswertung (Schritt 1) gewählt."), wrap=0)
            self._colour(item, "text_dim")
            with dpg.group(horizontal=True):
                dpg.add_text(t("Name der Regel"))
                self.dir_rule_name = tip(dpg.add_input_text(default_value="", width=260, hint=t("Name der Regel"),
                                                            callback=lambda: self._dir_name_state()),
                                         "Name der Regel. Aus der Auto-Auswertung kommend: der Name der Auswertung "
                                         "(neue Regel). Gibt es den Namen schon, wird diese Regel bearbeitet.")
                dpg.add_text(t("Vorhandene Regel bearbeiten"))
                self.dir_rule_combo = tip(dpg.add_combo(items=names, default_value="", width=240,
                                                        callback=lambda _s, v: self._dir_load_rule(v)),
                                          "Vorhandene Regel laden und bearbeiten. Beim Speichern wird sie geändert; "
                                          "Auswertungen, die sie nutzen, werden nachgezogen.")
                tip(dpg.add_button(label=t("Regel löschen"), callback=lambda: self._dir_delete_rule()),
                    "Regel löschen (Auswertungen, die sie nutzen, verlieren ihre Regel).")
            self.dir_mode_text = dpg.add_text("", wrap=0)
            self._colour(self.dir_mode_text, "heading")

            head(1, "Quellordner", "Ordner wählen und Struktur analysieren: Gesucht werden alle Unterordner mit "
                 "Messdateien (*.csv, *.asc, *.parquet); die Bezeichnungen der Unterordner je Ebene zeigt die Struktur.")
            with dpg.group(horizontal=True):
                self.dir_root = tip(dpg.add_input_text(default_value="", width=-330, on_enter=True,
                                                       callback=lambda: self.dir_analyze()),
                                    "Quellordner, z. B. Z:\\...\\Halle_D_Setup. Mit Eingabetaste analysieren.")
                dpg.add_button(label=t("Wählen..."), width=100, callback=lambda: self._show_file_browser(
                    "folder", lambda p: (dpg.set_value(self.dir_root, p[0]), self.dir_analyze()),
                    "Quellordner wählen", start_dir=dpg.get_value(self.dir_root) or None))
                tip(dpg.add_button(label=t("Struktur analysieren"), width=210, callback=lambda: self.dir_analyze()),
                    "Unterordner mit Messdateien suchen, Struktur anzeigen und Platzhalter erkennen.")
            self.dir_struct = dpg.add_text("", wrap=0)

            head(2, "Daten auswählen", "Gefundene Daten als Baum (Ordner auf- und zuklappbar). Standard: alle aktiv. "
                 "Dateien, die ignoriert werden sollen, abhaken (Häkchen je Datei bzw. je Ordner).")
            with dpg.group(horizontal=True):
                tip(dpg.add_button(label=t("Alle"), small=True, callback=lambda: self._dir_all_files(True)),
                    "Alle Dateien einlesen.")
                dpg.add_button(label=t("Keine"), small=True, callback=lambda: self._dir_all_files(False))
                self.dir_files_count = dpg.add_text("")
                self._colour(self.dir_files_count, "heading")
            self.dir_tree = dpg.add_child_window(height=200, border=True)

            head(3, "Basis Zielordner", "Ordner, unter dem die Zielordner entstehen (z. B. ...\\MessGraph\\_TestResult).")
            with dpg.group(horizontal=True):
                self.dir_base = tip(dpg.add_input_text(default_value=str(AUTO_BASE), width=-110, on_enter=True,
                                                       callback=lambda: self.dir_preview()),
                                    "Basis Zielordner. Fehlende Ordner werden beim Speichern angelegt.")
                dpg.add_button(label=t("Wählen..."), width=100, callback=lambda: self._show_file_browser(
                    "folder", lambda p: (dpg.set_value(self.dir_base, p[0]), self.dir_preview()),
                    "Basis Zielordner wählen", start_dir=self._auto_start_dir(dpg.get_value(self.dir_base))))

            head(4, "Platzhalter und erweiterter Zielordner", "Aus den Namen der Unterordner erkannt: {Mode} (z. B. "
                 "AC_22kW_3ph_615V), {Testlauf} (DV, PV), {Test-Variante} (HTOE_11kW, HTOE_Mix, PTCE_...), "
                 "{Seriennummer} (DES...), {DUTx}; dazu {Datetime} (Systemzeit beim ersten Speichern) und {Name} "
                 "(Name der Auswertung). Jedes Element lässt sich mit einem eigenen Wert belegen. Der erweiterte "
                 "Zielordner kombiniert sie frei, z. B. {Testlauf}_{Test-Variante}\\{Mode}\\{DUTx}.")
            with dpg.table(header_row=True, policy=dpg.mvTable_SizingStretchProp, borders_innerH=True) as self.dir_ph_table:
                for label, weight in ((t("Platzhalter"), 1.0), (t("erkannt"), 3.0), (t("eigener Wert (optional)"), 1.6),
                                      ("", 0.6)):
                    dpg.add_table_column(label=label, init_width_or_weight=weight)
                self.dir_ph_found = {}
                for label, key in dirrules.PLACEHOLDERS:
                    with dpg.table_row():
                        dpg.add_text("{" + label + "}")
                        self.dir_ph_found[key] = dpg.add_text("-")
                        self.dir_value_inputs[key] = dpg.add_input_text(width=-1, on_enter=True,
                                                                        callback=lambda: self.dir_preview())
                        dpg.add_button(label=t("einfügen"), small=True, user_data=label,
                                       callback=lambda s, a, u: self._dir_insert(u))
            with dpg.group(horizontal=True):
                dpg.add_text(t("Erw. Zielordner"))
                self.dir_template = tip(dpg.add_input_text(default_value="", width=-1, hint="{Mode}\\{DUTx}",
                                                           on_enter=True, callback=lambda: self.dir_preview()),
                                        "Erweiterter Zielordner relativ zum Basis Zielordner; \\ trennt Unterordner. "
                                        "Mit Eingabetaste Vorschau aktualisieren.")

            head(5, "Zielordner", "Zielordner = Basis Zielordner + Erw. Zielordner.")
            self.dir_target_text = dpg.add_text("", wrap=0)
            self._colour(self.dir_target_text, "heading")

            head(6, "Vorschau prüfen", "Je Zielordner: Mode, DUT/Seriennummer, Ordner, Dateien, Status. Abgehakte "
                 "Zielordner werden nicht ausgewertet; Ordner ohne Wert für einen Platzhalter (z. B. Logs ohne Mode) "
                 "sind gekennzeichnet und bleiben außen vor.")
            with dpg.group(horizontal=True):
                tip(dpg.add_button(label=t("Vorschau aktualisieren"), callback=lambda: self.dir_preview()),
                    "Regel mit den aktuellen Angaben erneut anwenden.")
                tip(dpg.add_button(label=t("Alle"), small=True, callback=lambda: self._dir_select(True)),
                    "Alle Zielordner wählen.")
                dpg.add_button(label=t("Keine"), small=True, callback=lambda: self._dir_select(False))
                self.dir_count = dpg.add_text("")
                self._colour(self.dir_count, "heading")
            self.dir_table = dpg.add_child_window(height=200, border=True)
            dpg.add_separator()
            item = dpg.add_text(t("Nur neue Daten werden synchronisiert und bearbeitet: Vorhandene Auswertungen behalten "
                                  "ihre gelesenen Daten, neue Ordner und Dateien kommen hinzu."), wrap=0)
            self._colour(item, "text_dim")
            with dpg.group(horizontal=True):
                tip(dpg.add_button(label=t("Regel speichern"), width=200, callback=lambda: self.dir_save_rule()),
                    "Alle Angaben in der Regel speichern und fehlende Zielordner anlegen. Die Auswertung (bzw. alle "
                    "Auswertungen mit dieser Regel) wird nachgezogen.")
                self.dir_state = dpg.add_text("")
        with dpg.window(tag="dir_error", label=t("Verzeichnisverwalter - Fehler"), modal=True, show=False, width=620,
                        height=260, no_collapse=True):
            self.dir_error_text = dpg.add_text("", wrap=580)
            self._colour(self.dir_error_text, "error")
            dpg.add_button(label=t("OK"), width=100, callback=lambda: dpg.configure_item("dir_error", show=False))

    def _dir_error(self, text: str) -> None:
        dpg.set_value(self.dir_error_text, text)
        vw, vh = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
        dpg.configure_item("dir_error", show=True, pos=[max(0, (vw - 620) // 2), max(0, (vh - 260) // 3)])
        self._message(text, error=True)

    def open_dir_window(self, from_auto: bool = False) -> None:
        """Verzeichnisverwalter öffnen. Aus der Auto-Auswertung: der Name (Feld Name bzw. gewählte Auswertung) ist
        der Name der Regel - neu oder, wenn es die Regel schon gibt, bearbeiten."""
        vw, vh = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
        w, h = min(1150, int(vw * 0.92)), min(880, int(vh * 0.94))
        dpg.configure_item("dir_window", show=True, width=w, height=h, pos=[max(0, (vw - w) // 2), max(0, (vh - h) // 6)])
        self.dir_from_auto = from_auto
        if from_auto and dpg.does_item_exist("auto_window"):
            ev = self._auto_eval()
            typed = dpg.get_value(self.auto_name).strip()
            name = typed or (ev["name"] if ev else "")
            if ev is not None and ev.get("rule") and typed in ("", ev["name"]):
                name = ev["rule"]                          # Auswertung hat schon eine Regel: diese bearbeiten
            if name and self._auto_rule_get(name) is not None:
                self._dir_load_rule(name)
            elif name:
                self._dir_new_rule(name)
        self._dir_name_state()

    def _dir_new_rule(self, name: str) -> None:
        dpg.set_value(self.dir_rule_name, name)
        dpg.set_value(self.dir_rule_combo, "")
        self.dir_loaded, self.dir_excluded, self.dir_deselected, self.dir_datetime = None, set(), set(), ""
        dpg.set_value(self.dir_template, "")
        for field in self.dir_value_inputs.values():
            dpg.set_value(field, "")
        if dpg.get_value(self.dir_root).strip():
            self.dir_analyze()

    def _dir_name_state(self) -> None:
        name = dpg.get_value(self.dir_rule_name).strip()
        if not name:
            text = t("Bitte einen Namen für die Regel eingeben.")
        elif self._auto_rule_get(name) is not None:
            text = t("BEARBEITEN: Die vorhandene Regel {name} wird beim Speichern geändert - Auswertungen, die sie "
                     "nutzen, werden nachgezogen.", name=name)
        else:
            text = t("NEUE Regel {name} wird definiert.", name=name)
        dpg.set_value(self.dir_mode_text, text)

    @staticmethod
    def _dir_rel(rel: tuple) -> str:
        return "\\".join(rel) if rel else "."

    def dir_analyze(self) -> None:
        """Schritt 1: Quellordner durchsuchen, Struktur zeigen, Baum (Schritt 2) und Platzhalter (Schritt 4) füllen."""
        root = os.path.expanduser(dpg.get_value(self.dir_root).strip())
        if not root or not os.path.isdir(root):
            self.dir_dirs = []
            dpg.set_value(self.dir_struct, t("Quellordner nicht gefunden: {path}", path=root or "-"))
            self._dir_build_tree()
            self.dir_preview()
            return
        self.dir_dirs = dirrules.scan(root)
        total = sum(len(d.files) for d in self.dir_dirs)
        if not self.dir_dirs:
            dpg.set_value(self.dir_struct, t("Keine Messdateien (*.csv, *.asc, *.parquet) unter {path}.", path=root))
        else:
            lines = [t("{folders} Ordner mit {files} Messdateien. Struktur der Unterordner:", folders=len(self.dir_dirs),
                       files=total)]
            names = dict((k, label) for label, k in dirrules.PLACEHOLDERS)
            for level, label, kinds in dirrules.structure(self.dir_dirs, root):
                found = ", ".join("{" + names.get(k, k) + "}" for k in kinds)
                lines.append(t("Ebene {n}: {names}", n=level, names=label) + (f"   -> {found}" if found else ""))
            from_files = dirrules.file_modes(self.dir_dirs, root)
            if from_files:
                more = f" (+{len(from_files) - 6})" if len(from_files) > 6 else ""
                lines.append(t("Dateinamen: {names}", names=", ".join(from_files[:6]) + more) + "   -> {Mode}")
            if total >= dirrules.MAX_FILES:
                lines.append(t("(nur die ersten {count} Dateien)", count=dirrules.MAX_FILES))
            dpg.set_value(self.dir_struct, "\n".join(lines))
        self._dir_build_tree()
        found = dirrules.detected_values(root, self.dir_dirs)
        for key, item in self.dir_ph_found.items():
            values = found.get(key, [])
            if key == "DATETIME":
                text = self.dir_datetime or t("Systemzeit beim ersten Speichern")
            elif key == "NAME":
                text = dpg.get_value(self.dir_rule_name).strip() or "-"
            else:
                text = ", ".join(values[:5]) + (f" (+{len(values) - 5})" if len(values) > 5 else "") if values else \
                    t("nicht erkannt")
            dpg.set_value(item, text)
        if not dpg.get_value(self.dir_template).strip():
            dpg.set_value(self.dir_template, dirrules.default_template(found))
        self.dir_preview()

    def _dir_build_tree(self) -> None:
        """Schritt 2: Ordnerbaum mit Häkchen je Datei (bei sehr vielen Dateien je Ordner)."""
        dpg.delete_item(self.dir_tree, children_only=True)
        self.dir_file_boxes, self.dir_folder_boxes = {}, {}
        total = sum(len(d.files) for d in self.dir_dirs)
        per_file = total <= self.DIR_TREE_FILES
        nodes = {(): self.dir_tree}
        for d in self.dir_dirs:
            for depth in range(len(d.rel)):                # Ordnerknoten anlegen (auf- und zuklappbar)
                key = d.rel[:depth + 1]
                if key not in nodes:
                    count = sum(len(x.files) for x in self.dir_dirs if x.rel[:depth + 1] == key)
                    nodes[key] = dpg.add_tree_node(label=f"{key[-1]}  ({count})", parent=nodes[key[:-1]],
                                                   default_open=depth < 1)
            parent = nodes[d.rel]
            files = [dirrules.rel_file(d.rel, f) for f in d.files]
            on = sum(1 for f in files if f not in self.dir_excluded)
            box = dpg.add_checkbox(label=t("alle Dateien dieses Ordners ({on}/{count})", on=on, count=len(files)),
                                   default_value=on > 0, parent=parent, user_data=d.rel,
                                   callback=lambda s, v, u: self._dir_folder_toggle(u, v))
            self.dir_folder_boxes[d.rel] = box
            if per_file:
                for name, rel in zip(d.files, files):
                    self.dir_file_boxes[rel] = dpg.add_checkbox(label=name, default_value=rel not in self.dir_excluded,
                                                                parent=parent, user_data=rel,
                                                                callback=lambda s, v, u: self._dir_file_toggle(u, v))
        self._dir_files_count()

    def _dir_files_count(self) -> None:
        total = sum(len(d.files) for d in self.dir_dirs)
        off = sum(1 for d in self.dir_dirs for f in d.files if dirrules.rel_file(d.rel, f) in self.dir_excluded)
        text = t("{count} Dateien, {off} ausgeschlossen", count=total, off=off)
        if total > self.DIR_TREE_FILES:
            text += "  " + t("(viele Dateien: Auswahl je Ordner)")
        dpg.set_value(self.dir_files_count, text)

    def _dir_file_toggle(self, rel: str, value: bool) -> None:
        (self.dir_excluded.discard if value else self.dir_excluded.add)(rel)
        self._dir_files_count()
        self._dir_folder_labels()
        self.dir_preview()

    def _dir_folder_toggle(self, rel: tuple, value: bool) -> None:
        d = next((x for x in self.dir_dirs if x.rel == rel), None)
        if d is None:
            return
        for name in d.files:
            path = dirrules.rel_file(d.rel, name)
            (self.dir_excluded.discard if value else self.dir_excluded.add)(path)
            if path in self.dir_file_boxes:
                dpg.set_value(self.dir_file_boxes[path], bool(value))
        self._dir_files_count()
        self._dir_folder_labels()
        self.dir_preview()

    def _dir_folder_labels(self) -> None:
        for d in self.dir_dirs:
            box = self.dir_folder_boxes.get(d.rel)
            if box is None:
                continue
            files = [dirrules.rel_file(d.rel, f) for f in d.files]
            on = sum(1 for f in files if f not in self.dir_excluded)
            dpg.configure_item(box, label=t("alle Dateien dieses Ordners ({on}/{count})", on=on, count=len(files)))
            dpg.set_value(box, on > 0)

    def _dir_all_files(self, value: bool) -> None:
        for d in self.dir_dirs:
            self._dir_folder_toggle(d.rel, value)

    def _dir_insert(self, label: str) -> None:
        text = dpg.get_value(self.dir_template).rstrip()
        joiner = "" if not text or text.endswith(("\\", "/", "_", "-")) else "_"
        dpg.set_value(self.dir_template, text + joiner + "{" + label + "}")
        self.dir_preview()

    def _dir_rule(self) -> "dirrules.Rule":
        values = {key: dpg.get_value(field).strip() for key, field in self.dir_value_inputs.items()
                  if dpg.get_value(field).strip()}
        return dirrules.Rule(name=dpg.get_value(self.dir_rule_name).strip(),
                             root=self._abs_dir(dpg.get_value(self.dir_root)),
                             base=self._abs_dir(dpg.get_value(self.dir_base)), template=dpg.get_value(self.dir_template).strip(),
                             pattern="", version=2, excluded=sorted(self.dir_excluded), values=values,
                             deselected=sorted(self.dir_deselected), datetime=self.dir_datetime)

    def dir_preview(self) -> None:
        """Schritt 5 (Zielordner) und 6 (Vorschau): Regel anwenden, je Zielordner eine Zeile mit Häkchen."""
        rule = self._dir_rule()
        name = rule.name or (self._auto_eval() or {}).get("name", "")
        now = self.dir_datetime or time.strftime("%Y%m%d_%H%M%S")
        self.dir_units = dirrules.plan(rule, name, dirs=self.dir_dirs, now=now) if self.dir_dirs else []
        example = next((u.target for u in self.dir_units if u.target and not u.error), "")
        dpg.set_value(self.dir_target_text, t("Zielordner = {base}\\{template}", base=rule.base or "-",
                                              template=rule.template or "-")
                      + ("\n" + t("Beispiel: {path}", path=example) if example else ""))
        dpg.delete_item(self.dir_table, children_only=True)
        self.dir_unit_boxes = []
        by_target = {os.path.normcase(os.path.abspath(j["target"])): j for j in self.auto_jobs if j.get("target")}
        with dpg.table(parent=self.dir_table, header_row=True, resizable=True, borders_innerH=True,
                       policy=dpg.mvTable_SizingStretchProp):
            for label, weight in (("", 0.3), (t("Zielordner"), 3.0), (t("Mode"), 1.6), (t("DUT / Seriennummer"), 1.4),
                                  (t("Ordner"), 0.6), (t("Dateien"), 0.8), (t("Status"), 1.8)):
                dpg.add_table_column(label=label, init_width_or_weight=weight)
            for u in self.dir_units:
                with dpg.table_row():
                    if u.error or u.files == 0:
                        dpg.add_text("-")
                    else:
                        box = dpg.add_checkbox(default_value=u.key.casefold() not in {x.casefold() for x in self.dir_deselected}
                                               and u.files > 0, user_data=u.key,
                                               callback=lambda s, v, k: self._dir_unit_toggle(k, v))
                        self.dir_unit_boxes.append((box, u))
                    dpg.add_text(u.target or u.key)
                    dpg.add_text(u.mode or "-")
                    dpg.add_text(u.values.get("DUT") or u.values.get("SERIENNUMMER") or "-")
                    dpg.add_text(str(len(u.folders)))
                    dpg.add_text(f"{u.files}" + (f" (-{len(u.excluded)})" if u.excluded else ""))
                    if u.error:
                        status = self._dir_text(u.error)
                    elif u.files == 0:
                        status = t("keine Dateien gewählt")
                    elif u.warning:
                        status = self._dir_text(u.warning)
                    elif u.target and os.path.normcase(os.path.abspath(u.target)) in by_target:
                        status = t("vorhanden ({name})", name=by_target[os.path.normcase(os.path.abspath(u.target))]["name"])
                    elif u.target and os.path.isdir(u.target):
                        status = t("Zielordner vorhanden")
                    else:
                        status = t("neu")
                    dpg.add_text(status)
        self._dir_count()

    @staticmethod
    def _dir_text(text: str) -> str:
        """Meldung aus dirrules (deutsch) in die eingestellte Sprache."""
        found = re.match(r"^(\{[^{}]+\}): kein Wert", text)
        if found:
            return t("{name}: kein Wert (weder in Ordner- noch Dateinamen erkannt - Datei abwählen oder eigenen Wert eintragen)", name=found.group(1))
        return t(text)

    def _dir_unit_toggle(self, key: str, value: bool) -> None:
        if value:
            self.dir_deselected = {x for x in self.dir_deselected if x.casefold() != key.casefold()}
        else:
            self.dir_deselected.add(key)
        self._dir_count()

    def _dir_count(self) -> None:
        chosen = sum(1 for box, _u in self.dir_unit_boxes if dpg.get_value(box))
        bad = sum(1 for u in self.dir_units if u.error)
        text = t("{count} Zielordner, {chosen} gewählt", count=len(self.dir_unit_boxes), chosen=chosen)
        if bad:
            text += "  " + t("{count} Ordner ohne Wert für einen Platzhalter", count=bad)
        dpg.set_value(self.dir_count, text)

    def _dir_select(self, value: bool) -> None:
        for box, u in self.dir_unit_boxes:
            on = bool(value) and u.files > 0
            dpg.set_value(box, on)
            self._dir_unit_toggle(u.key, on)

    def dir_save_rule(self) -> bool:
        """Regel speichern: alle Angaben übernehmen, fehlende Zielordner anlegen (Fehler im Fenster), Auswertungen
        mit dieser Regel nachziehen."""
        rule = self._dir_rule()
        problems = []
        if not rule.name:
            problems.append(t("Name der Regel fehlt."))
        if not rule.root or not os.path.isdir(rule.root):
            problems.append(t("Quellordner nicht gefunden: {path}", path=rule.root or "-"))
        if not rule.base:
            problems.append(t("Basis Zielordner fehlt."))
        if not rule.template:
            problems.append(t("Erweiterter Zielordner fehlt."))
        if problems:
            self._dir_error("\n".join(problems))
            return False
        if not rule.datetime and "DATETIME" in {dirrules.canon(k) for k in dirrules.PLACEHOLDER.findall(rule.template)}:
            rule.datetime = self.dir_datetime = time.strftime("%Y%m%d_%H%M%S")
        if not self.dir_dirs:
            self.dir_dirs = dirrules.scan(rule.root)
        units = [u for u in dirrules.plan(rule, rule.name, dirs=self.dir_dirs) if u.active and not u.error]
        failed = []
        for u in units:
            try:
                os.makedirs(u.target, exist_ok=True)
            except OSError as exc:
                failed.append(f"{u.target}: {exc}")
        if failed:
            self._dir_error(t("Zielordner konnten nicht angelegt werden:") + "\n" + "\n".join(failed[:12]))
            return False
        store = self._dir_store()
        rules = [r for r in store.get("rules", []) if r.get("name") != rule.name]
        rules.append(rule.to_dict())
        store.update(rules=rules, selected=rule.name)
        self._save_settings()
        dpg.configure_item(self.dir_rule_combo, items=[r["name"] for r in rules])
        dpg.set_value(self.dir_rule_combo, rule.name)
        self.dir_loaded = rule.name
        ev = self._auto_eval() if getattr(self, "dir_from_auto", False) else None
        if ev is not None and not ev.get("rule"):
            ev["rule"] = rule.name                        # neue Regel gehört zur Auswertung, aus der sie kam
        count = self._auto_rule_sync(rule) if any(e.get("rule") == rule.name for e in self.auto_evals) else 0
        if dpg.does_item_exist("auto_window"):
            self._auto_show_job()
        text = t("Regel {name} gespeichert: {units} Zielordner (angelegt bzw. vorhanden).", name=rule.name, units=len(units))
        if count:
            text += " " + t("Auswertungen nachgezogen: {count} Zielordner.", count=count)
        dpg.set_value(self.dir_state, text)
        self._dir_name_state()
        self._message(text)
        self.dir_preview()
        return True

    def _dir_load_rule(self, name: str) -> None:
        rule = self._auto_rule_get(name)
        if rule is None:
            return
        dpg.set_value(self.dir_rule_name, rule.name)
        dpg.set_value(self.dir_rule_combo, rule.name)
        self.dir_loaded = rule.name
        dpg.set_value(self.dir_root, rule.root)
        dpg.set_value(self.dir_base, rule.base or str(AUTO_BASE))
        if rule.version >= 2:
            dpg.set_value(self.dir_template, rule.template)
            self.dir_excluded, self.dir_deselected = set(rule.excluded), set(rule.deselected)
            self.dir_datetime = rule.datetime
        else:                                            # ältere Regel: Vorschlag aus der Struktur
            dpg.set_value(self.dir_template, "")
            self.dir_excluded, self.dir_deselected, self.dir_datetime = set(), set(), ""
        for key, field in self.dir_value_inputs.items():
            dpg.set_value(field, rule.values.get(key, "") if rule.version >= 2 else "")
        self._dir_store()["selected"] = name
        self._save_settings()
        self._dir_name_state()
        self.dir_analyze()

    def _dir_delete_rule(self) -> None:
        store = self._dir_store()
        name = dpg.get_value(self.dir_rule_combo) or dpg.get_value(self.dir_rule_name).strip()
        rules = [r for r in store.get("rules", []) if r.get("name") != name]
        store.update(rules=rules, selected="")
        for ev in self.auto_evals:
            if ev.get("rule") == name:
                ev["rule"] = ""
        self._save_settings()
        dpg.configure_item(self.dir_rule_combo, items=[r["name"] for r in rules])
        dpg.set_value(self.dir_rule_combo, "")
        self._dir_name_state()
        if dpg.does_item_exist("auto_window"):
            self._auto_show_job()
        self._message(t("Regel {name} gelöscht.", name=name or "-"))

    def _build_report_window(self) -> None:
        opts = self.settings.get("auto_report") or {}
        with dpg.window(tag="report_window", label=t("Report erstellen"), show=False, width=800, height=720,
                        no_collapse=True):
            item = dpg.add_text(t("Report aus den PNG und Kennwerten der gewählten Auswertungen (je Auswertung ein DUT): "
                                  "Deckblatt, Summary Comparison, Signal Plot Comparison und je DUT Tabelle und Graphen."),
                                wrap=0)
            self._colour(item, "text_dim")
            with dpg.group(horizontal=True):
                dpg.add_text(t("Auswertung"))
                self.report_eval = dpg.add_combo(items=[], width=300, callback=lambda s, v: self._report_pick_eval(v))
                self._tooltip(self.report_eval, t("Nur die DUTs dieser Auswertung (ihre Zielordner) gehen in den Report; "
                                                  "neue Modes und DUTs der Auswertung sind automatisch dabei."))
            with dpg.group(horizontal=True):
                dpg.add_text(t("Auswertungen (DUTs)"))
                dpg.add_button(label=t("Alle"), small=True, callback=lambda: self._report_select(True))
                dpg.add_button(label=t("Keine"), small=True, callback=lambda: self._report_select(False))
            self.report_list = dpg.add_child_window(height=200, border=True)
            with dpg.table(header_row=False, policy=dpg.mvTable_SizingStretchProp):
                dpg.add_table_column(init_width_or_weight=0.25)
                dpg.add_table_column(init_width_or_weight=0.75)
                with dpg.table_row():
                    dpg.add_text(t("Titel"))
                    self.report_title = dpg.add_input_text(default_value=opts.get("title", "Test Report"), width=-1)
                with dpg.table_row():
                    dpg.add_text(t("Projekt"))
                    self.report_project = dpg.add_input_text(default_value=opts.get("project", ""), width=-1)
                with dpg.table_row():
                    dpg.add_text(t("Mode"))
                    self.report_mode = dpg.add_input_text(default_value="", width=-1,
                                                          hint=t("leer = je Report der Mode seiner Auswertungen"))
                with dpg.table_row():
                    dpg.add_text(t("Ausgabeordner"))
                    with dpg.group(horizontal=True):
                        self.report_path = dpg.add_input_text(default_value=opts.get("path", ""), width=-110,
                                                              hint=t("leer = gemeinsamer Ordner der Zielverzeichnisse"))
                        self._tooltip(self.report_path, t("Je Mode ein Report mit allen gewählten DUTs dieses Modes: "
                                                          "Report_<Mode>_<Datum_Uhrzeit>.pdf"))
                        dpg.add_button(label=t("Wählen..."), width=100, callback=lambda: self._show_file_browser(
                            "folder", lambda p: self._report_set_dir(p[0]), "Ordner für den Report wählen"))
                with dpg.table_row():
                    dpg.add_text(t("Wasserzeichen"))
                    self.report_watermark = dpg.add_checkbox(label=t("\"NOT RELEASED\" auf jeder Seite"),
                                                             default_value=True)
                with dpg.table_row():
                    dpg.add_text(t("Graphen pro Seite"))
                    self.report_per_page = dpg.add_combo(items=["9", "4", "2", "1"], width=80,
                                                         default_value=str(opts.get("per_page", 9)),
                                                         callback=lambda: self._report_save_form())
            dpg.add_separator()
            sched = opts.get("schedule") or {}
            with dpg.group(horizontal=True):
                self.report_sched_on = dpg.add_checkbox(label=t("Zeitplan: Report automatisch zu festen Uhrzeiten"),
                                                        default_value=bool(sched.get("on")),
                                                        callback=lambda: self._report_schedule_changed())
                self._tooltip(self.report_sched_on, t("Unabhängig vom Datenzyklus: Der Report wird zu den Uhrzeiten mit den "
                                                      "aktuell gewählten Auswertungen und Einstellungen erstellt (solange "
                                                      "MessGraph läuft)."))
            with dpg.group(horizontal=True):
                dpg.add_text(t("Uhrzeiten"))
                self.report_times = dpg.add_input_text(default_value=sched.get("times", "00:00:00"), width=220,
                                                       hint="00:00:00, 12:00", on_enter=True,
                                                       callback=lambda: self._report_schedule_changed())
                self.report_repeat = dpg.add_combo(items=[t("täglich"), t("einmalig")], width=120,
                                                   default_value=t("einmalig") if sched.get("repeat") == "once"
                                                   else t("täglich"), callback=lambda: self._report_schedule_changed())
            self.report_next = dpg.add_text("")
            self._colour(self.report_next, "heading")
            with dpg.group(horizontal=True):
                self.report_btn = dpg.add_button(label=t("Report erstellen"), width=160, callback=lambda: self.create_report())
            with dpg.group(horizontal=True, show=False) as self.report_progress_row:
                self.report_bar = dpg.add_progress_bar(default_value=0.0, width=-1, overlay="")   # nicht abbrechbar
            self.report_state = dpg.add_text("", wrap=0)
        self.report_boxes = []
        self._report_plan()

    REPORT_ALL = "*"

    def _report_eval_names(self) -> list[str]:
        return [e["name"] for e in self.auto_evals]

    def _report_eval_choice(self) -> str:
        """Auswertung des Reports: gespeicherte Wahl, sonst die in Auto gewählte Auswertung."""
        stored = (self.settings.get("auto_report") or {}).get("evaluation")
        if stored == self.REPORT_ALL or stored in self._report_eval_names():
            return stored
        return self.auto_eval_name or (self._report_eval_names() or [self.REPORT_ALL])[0]

    def _report_candidates(self, evaluation: str) -> list[dict]:
        """Teile (DUTs) der Auswertung, je Zielordner einer, sortiert nach Mode und Name."""
        jobs = [j for j in self.auto_jobs if evaluation == self.REPORT_ALL or j.get("evaluation") == evaluation]
        out, seen = [], set()
        for job in sorted(jobs, key=lambda j: (str(j.get("evaluation", "")).casefold(),
                                               self._auto_mode_name(j).casefold(), j["name"].casefold())):
            key = self._norm_path(job.get("target")) or ("#" + job["name"])
            if key not in seen:                            # gleiches Zielverzeichnis nur einmal
                seen.add(key)
                out.append(job)
        return out

    def _report_ready(self, job: dict) -> tuple[bool, str]:
        """Standardwahl und Hinweis: mit Ausgaben oder lauffähig (Zyklus vor dem Report) -> gewählt."""
        if self._report_has_output(job):
            return True, ""
        problem = self._auto_problem(job)
        if problem:
            return False, t("noch keine Ausgaben") + " - " + problem
        if not job.get("enabled", True):
            return False, t("noch keine Ausgaben - Mode in Schritt 2 nicht zur Verarbeitung gewählt")
        return True, t("noch keine Ausgaben - Zyklus läuft vor dem Report")

    def _report_selected(self, evaluation: str, deselected) -> list[dict]:
        """Gewählte Teile ohne Fenster (Zeitplan): alle bereiten Teile der Auswertung außer ausdrücklich abgewählten -
        so sind neue Modes/DUTs der Auswertung automatisch im Report."""
        off = {self._norm_path(p) for p in deselected or []}
        return [dict(j) for j in self._report_candidates(evaluation)
                if self._report_ready(j)[0] and self._norm_path(j.get("target")) not in off]

    def open_report_window(self) -> None:
        if dpg.does_item_exist("auto_window") and dpg.is_item_shown("auto_window"):
            self._auto_read_form()                         # offene Eingaben der Auswertung übernehmen
        names = self._report_eval_names()
        labels = names + [t("Alle Auswertungen")]
        dpg.configure_item(self.report_eval, items=labels)
        choice = self._report_eval_choice()
        dpg.set_value(self.report_eval, t("Alle Auswertungen") if choice == self.REPORT_ALL else choice)
        self._report_fill(choice)
        dpg.set_value(self.report_watermark, True)           # Wasserzeichen standardmäßig an
        vw, vh = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
        dpg.configure_item("report_window", show=True, pos=[max(0, (vw - 800) // 2), max(0, (vh - 720) // 4)])
        self._report_plan()

    def _report_fill(self, evaluation: str) -> None:
        self.report_evaluation = evaluation
        dpg.delete_item(self.report_list, children_only=True)
        self.report_boxes = []
        stored = self.settings.get("auto_report") or {}
        off = {self._norm_path(p) for p in stored.get("deselected") or []} \
            if stored.get("evaluation") == evaluation else set()
        for job in self._report_candidates(evaluation):
            ready, note = self._report_ready(job)
            chosen = ready and self._norm_path(job.get("target")) not in off
            label = f"{job['name']}   ({job['target'] or '-'})" + (f"  - {note}" if note else "")
            if evaluation == self.REPORT_ALL:
                label = f"[{job.get('evaluation', '-')}] " + label
            box = dpg.add_checkbox(label=label, default_value=chosen, parent=self.report_list,
                                   callback=lambda: self._report_save_form())
            self.report_boxes.append((box, job))
        if not self.report_boxes:
            dpg.add_text(t("Keine DUTs in dieser Auswertung - Auswertung in Auto anlegen bzw. Verzeichnisregel speichern."),
                         parent=self.report_list)

    def _report_pick_eval(self, value: str) -> None:
        evaluation = self.REPORT_ALL if value == t("Alle Auswertungen") else value
        self._report_fill(evaluation)
        self._report_save_form()

    def _report_select(self, value: bool) -> None:
        for box, _job in self.report_boxes:
            dpg.set_value(box, value)

    def _report_set_dir(self, folder: str) -> None:
        dpg.set_value(self.report_path, folder)

    def _report_jobs(self) -> list:
        return [dict(job) for box, job in self.report_boxes if dpg.get_value(box)]

    def _report_form(self) -> dict:
        """Report-Einstellungen aus dem Fenster (für sofort und für den Zeitplan)."""
        return {"project": dpg.get_value(self.report_project).strip(),
                "title": dpg.get_value(self.report_title).strip() or "Test Report",
                "mode": dpg.get_value(self.report_mode).strip(), "path": dpg.get_value(self.report_path).strip(),
                "watermark": bool(dpg.get_value(self.report_watermark)),
                "per_page": int(dpg.get_value(self.report_per_page) or 9),
                "evaluation": getattr(self, "report_evaluation", "") or self._report_eval_choice(),
                "deselected": [job["target"] for box, job in self.report_boxes if not dpg.get_value(box)]}

    def _report_save_form(self) -> dict:
        form = self._report_form()
        stored = dict(self.settings.get("auto_report") or {})
        stored.update(project=form["project"], title=form["title"], path=form["path"], mode=form["mode"],
                      watermark=form["watermark"], per_page=form["per_page"], evaluation=form["evaluation"],
                      deselected=form["deselected"])
        stored.pop("jobs", None)                           # alte Wahl über Namen (mehrdeutig) entfällt
        self.settings["auto_report"] = stored
        self._save_settings()
        return form

    def create_report(self) -> None:
        """Report der gewählten Auswertungen im Hintergrund erstellen."""
        form = self._report_save_form()
        jobs = self._report_jobs()
        if not jobs:
            self._message(t("Report: bitte mindestens eine Auswertung wählen."), error=True)
            return
        self._report_request(jobs, form)

    @staticmethod
    def _report_has_output(job: dict) -> bool:
        target = job.get("target") or ""
        return bool(target) and os.path.isdir(target) and any(Path(target).glob("*/statistics.json"))

    def _report_request(self, jobs: list, form: dict, scheduled: bool = False) -> bool:
        """Report anfordern: läuft gerade eine Analyse oder ein Zyklus, wird danach erstellt. Gewählte Auswertungen
        ohne Ausgaben (noch kein Zyklus fertig) bekommen zuerst einen Zyklus - der Report ist damit nach einem
        Zyklus gültig und enthält alle gewählten Modes und DUTs."""
        if self._auto_busy():
            self.report_pending = (jobs, form, scheduled)
            self._message(t("Report: wird nach dem laufenden Zyklus erstellt."))
            return True
        real = {self._report_key(j): j for j in self.auto_jobs}
        missing = [real[self._report_key(j)] for j in jobs if self._report_key(j) in real
                   and not self._report_has_output(j) and not self._auto_problem(real[self._report_key(j)])]
        if missing:
            self.report_pending = (jobs, form, scheduled)
            for job in missing:                            # fehlender Zielordner: anlegen
                try:
                    os.makedirs(job["target"], exist_ok=True)
                except OSError:
                    pass
            self._auto_submit(force=True, jobs=missing)
            self._message(t("Report: zuerst ein Zyklus für {count} Auswertungen ohne Ausgaben ({names}), danach der "
                            "Report...", count=len(missing), names=", ".join(j["name"] for j in missing)))
            if dpg.does_item_exist("report_window"):
                dpg.set_value(self.report_state, t("Zyklus für Auswertungen ohne Ausgaben läuft, danach der Report..."))
            return True
        return self._start_report(jobs, form, scheduled=scheduled)

    def _report_continue(self) -> None:
        """Nach Analyse/Zyklus: angeforderten Report erstellen (ohne erneuten Zyklus)."""
        pending = getattr(self, "report_pending", None)
        if not pending or self._auto_busy():
            return
        self.report_pending = None
        jobs, form, scheduled = pending
        real = {self._report_key(j): j for j in self.auto_jobs}
        jobs = [dict(real.get(self._report_key(j), j)) for j in jobs]
        self._start_report(jobs, form, scheduled=scheduled)

    def _report_key(self, job: dict) -> str:
        """Teil eindeutig über Auswertung und Zielordner (Namen können sich zwischen Auswertungen gleichen)."""
        return f"{job.get('evaluation', '')}|{self._norm_path(job.get('target')) or job.get('name', '')}"

    def _report_plan_files(self, jobs: list, form: dict) -> tuple[list, list]:
        """Je Auswertung und Mode ein Report mit allen gewählten DUTs: [(Pfad, DUTs, Mode, Gründe)], Probleme.
        Auch ein Mode ohne Ausgaben bekommt einen Report (nur Deckblatt und Anhang, Endung _err); Gründe wie
        fehlende Ausgaben einzelner DUTs stehen im Anhang des Reports. Gleichnamige Modes verschiedener
        Auswertungen werden nicht vermischt.
        Datei: <Ausgabeordner>/Report_<Mode>_<JJJJMMTT_hhmmss>.pdf."""
        groups = {}
        for job in jobs:
            mode = self._auto_mode(job) or "Auto"
            groups.setdefault((job.get("evaluation", ""), mode), []).append(job)
        used = set()
        stamp = self._now().strftime("%Y%m%d_%H%M%S")
        folder_field = os.path.expanduser(form.get("path") or "")
        if folder_field.lower().endswith(".pdf"):          # alte Einstellung (Datei): deren Ordner
            folder_field = os.path.dirname(folder_field)
        plans, problems = [], []
        for (_evaluation, mode), group in groups.items():
            try:
                duts, found = autoreport.collect(group)
            except Exception as exc:                       # Report trotzdem erzeugen, Grund in den Anhang
                duts, found = [], [t("Ausgaben nicht lesbar: {error}", error=f"{type(exc).__name__}: {exc}")]
            problems += found
            folder = folder_field
            if not folder:
                targets = [os.path.abspath(j["target"]) for j in group if j.get("target")]
                try:
                    folder = os.path.commonpath(targets) if len(targets) > 1 else (targets[0] if targets else "")
                except ValueError:                         # verschiedene Laufwerke
                    folder = targets[0]
                folder = folder or str(Path.home())
            safe = lambda text: re.sub(r"[^\w.-]+", "_", str(text)).strip("_") or "Auto"
            path = os.path.join(os.path.abspath(folder), f"Report_{safe(mode)}_{stamp}.pdf")
            number = 2
            while self._norm_path(path) in used:            # gleicher Mode zweier Auswertungen im selben Ordner
                path = os.path.join(os.path.abspath(folder), f"Report_{safe(mode)}_{stamp}_{number}.pdf")
                number += 1
            used.add(self._norm_path(path))
            plans.append((path, duts, mode, found))
        return plans, problems

    def _start_report(self, jobs: list, form: dict, stamp: bool = True, scheduled: bool = False) -> bool:
        """Reports der gewählten Auswertungen im Hintergrund erstellen: je Mode einer (alle gewählten DUTs)."""
        if self.report_future is not None and not self.report_future.done():
            self._message(t("Report: wird bereits erstellt."))
            return False
        plans, problems = self._report_plan_files(jobs, form)
        if not plans:
            self._message(t("Report: {text}", text="; ".join(problems) or t("keine Ausgaben gefunden")), error=True)
            return False
        override = form.get("mode") if len(plans) == 1 else ""
        tasks = [(path, duts, autoreport.ReportOptions(project=form.get("project", ""), mode=override or mode,
                                                       title=form.get("title") or "Test Report",
                                                       watermark=bool(form.get("watermark", True)),
                                                       per_page=int(form.get("per_page", 9) or 9)), found)
                 for path, duts, mode, found in plans]
        if self.report_pool is None:
            self.report_pool = ThreadPoolExecutor(max_workers=1)
        self.report_cancel = False
        self.report_progress = (0, 1, t("Report wird vorbereitet..."))

        def build_all():
            """Alle Reports nacheinander; ein Fehler bei einem Report hält die anderen nicht auf."""
            made = []
            for number, (path, duts, options, found) in enumerate(tasks, 1):
                def progress(done, total, text, number=number, mode=options.mode):
                    self.report_progress = ((number - 1) * total + done, len(tasks) * total,
                                            f"{number}/{len(tasks)} {mode}: {text}")
                try:
                    made.append(autoreport.build_report(path, duts, options, progress, issues=found))
                except Exception as exc:                   # nicht einmal ein Ausweichname schreibbar
                    log_exception("Report", exc)
                    made.append(exc)
            return made

        self.report_future = self.report_pool.submit(build_all)
        self.report_problems = problems
        self.report_scheduled = scheduled
        if dpg.does_item_exist("report_window"):
            dpg.set_value(self.report_state, t("{count} Reports werden erstellt: {names}", count=len(tasks),
                                               names=", ".join(os.path.basename(p) for p, _d, _o, _f in tasks)))
        self._message((t("Report (Zeitplan): ") if scheduled else t("Report: ")) +
                      t("{count} Reports ({duts} DUTs) werden erstellt...", count=len(tasks),
                        duts=sum(len(d) for _p, d, _o, _f in tasks)))
        return True

    # ---- Zeitplan: Report zu festen Uhrzeiten, unabhängig vom Datenzyklus
    @staticmethod
    def parse_times(text: str) -> list:
        """Uhrzeiten "00:00:00, 12:30" -> sortierte Liste (Stunde, Minute, Sekunde); ValueError bei Fehlern."""
        out = []
        for part in re.split(r"[,;\s]+", str(text or "").strip()):
            if not part:
                continue
            match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?(?::(\d{2}))?", part)
            if not match:
                raise ValueError(part)
            h, m, sec = int(match.group(1)), int(match.group(2) or 0), int(match.group(3) or 0)
            if h > 23 or m > 59 or sec > 59:
                raise ValueError(part)
            out.append((h, m, sec))
        if not out:
            raise ValueError(text)
        return sorted(set(out))

    @staticmethod
    def next_report_time(times: list, now):
        """Nächster Zeitpunkt nach now (heute oder an einem der folgenden Tage)."""
        from datetime import timedelta
        for day in range(0, 2):
            base = (now + timedelta(days=day)).replace(microsecond=0)
            for h, m, sec in times:
                due = base.replace(hour=h, minute=m, second=sec)
                if due > now:
                    return due
        return None

    def _now(self):
        from datetime import datetime
        return datetime.now()

    def _report_schedule_changed(self) -> None:
        """Zeitplan-Eingaben übernehmen, prüfen und den nächsten Termin berechnen."""
        sched = {"on": bool(dpg.get_value(self.report_sched_on)), "times": dpg.get_value(self.report_times).strip(),
                 "repeat": "once" if dpg.get_value(self.report_repeat) == t("einmalig") else "daily"}
        self._report_save_form()
        stored = self.settings["auto_report"]
        stored["schedule"] = sched
        self._save_settings()
        self._report_plan()

    def _report_plan(self) -> None:
        sched = (self.settings.get("auto_report") or {}).get("schedule") or {}
        self.report_next_due = None
        text = t("Zeitplan aus.")
        if sched.get("on"):
            try:
                times = self.parse_times(sched.get("times") or "00:00:00")
                self.report_next_due = self.next_report_time(times, self._now())
                text = t("Nächster Report: {time} ({repeat})", time=self.report_next_due.strftime("%d.%m.%Y %H:%M:%S"),
                         repeat=t("einmalig") if sched.get("repeat") == "once" else t("täglich"))
            except ValueError as exc:
                text = t("Uhrzeit ungültig: {text} (z. B. 00:00:00, 06:00, 18:30)", text=exc)
        if dpg.does_item_exist("report_window"):
            dpg.set_value(self.report_next, text)
        self.report_plan_text = text

    def _poll_report_schedule(self) -> None:
        due = getattr(self, "report_next_due", None)
        if due is None or self._now() < due:
            return
        settings = self.settings.get("auto_report") or {}
        sched = settings.get("schedule") or {}
        evaluation = self._report_eval_choice()
        jobs = self._report_selected(evaluation, settings.get("deselected") if settings.get("evaluation") == evaluation
                                     else [])
        if self.report_future is not None and not self.report_future.done():
            return                                        # läuft noch: gleich erneut versuchen
        started = self._report_request(jobs, settings, scheduled=True)
        for job in jobs:
            engine = self.auto_engines.get(id(next((j for j in self.auto_jobs
                                                    if self._report_key(j) == self._report_key(job)), None)))
            if engine is not None:
                engine.log(t("Report nach Zeitplan {state}", state=t("gestartet") if started else t("nicht möglich")))
        if sched.get("repeat") == "once":                  # einmalig: Zeitplan danach aus
            sched["on"] = False
            settings["schedule"] = sched
            self.settings["auto_report"] = settings
            self._save_settings()
            if dpg.does_item_exist("report_window"):
                dpg.set_value(self.report_sched_on, False)
        self._report_plan()

    def _poll_report(self) -> None:
        future = self.report_future
        busy = future is not None and not future.done()
        if dpg.does_item_exist("report_window"):
            dpg.configure_item(self.report_progress_row, show=busy)
        if busy:
            done, total, text = self.report_progress
            fraction = min(1.0, done / total) if total else 0.0
            if dpg.does_item_exist("report_window"):
                dpg.set_value(self.report_bar, fraction)
                dpg.configure_item(self.report_bar, overlay=f"{int(fraction * 100)} %  {text}"[:90])
            if not self.jobs and not self._auto_busy():
                self.report_progress_shown = True
                dpg.set_value(self.progress_bar, fraction)
                dpg.configure_item(self.progress_bar, overlay=f"{int(fraction * 100)} %")
                dpg.set_value(self.progress_text, t("Report: {text}", text=text))
                dpg.configure_item(self.progress_row, show=True)
            return
        if getattr(self, "report_progress_shown", False) and not self.jobs and not self._auto_busy():
            self.report_progress_shown = False
            dpg.configure_item(self.progress_row, show=False)
        if future is None:
            return
        self.report_future = None
        try:
            path = future.result()
        except Exception as exc:
            log_exception("Report", exc)
            text = t("Report nicht erstellt: {error}", error=exc)
            self._message(text, error=True)
            if dpg.does_item_exist("report_window"):
                dpg.set_value(self.report_state, text)
            return
        results = path if isinstance(path, list) else [path]
        failed = [r for r in results if isinstance(r, Exception)]
        paths = [r for r in results if not isinstance(r, Exception)]
        incomplete = [p for p in paths if os.path.splitext(p)[0].endswith("_err")]
        if not paths:
            text = t("Report nicht erstellt: {error}", error="; ".join(str(f) for f in failed))
            self._message(text, error=True)
            if dpg.does_item_exist("report_window"):
                dpg.set_value(self.report_state, text)
            return
        listing = ", ".join(paths)
        text = (t("Report (Zeitplan) erstellt: {path}", path=listing) if getattr(self, "report_scheduled", False)
                else t("Report erstellt: {path}", path=listing)) if len(paths) == 1 else \
            (t("Report (Zeitplan): ") if getattr(self, "report_scheduled", False) else t("Report: ")) + \
            t("{count} Reports erstellt: {paths}", count=len(paths), paths=listing)
        if incomplete:
            text += "  " + t("{count} unvollständig (Endung _err, Gründe im Anhang des Reports).", count=len(incomplete))
        if failed:
            text += "  " + t("Nicht geschrieben: {text}", text="; ".join(str(f) for f in failed))
        self._message(text, error=bool(failed or incomplete))
        if dpg.does_item_exist("report_window"):
            dpg.set_value(self.report_state, text)

    def _poll_auto(self) -> None:
        self._report_continue()
        self._poll_report()
        self._poll_report_schedule()
        self._auto_progress()
        analysis = self.auto_analysis
        if analysis is not None and analysis.done():
            self.auto_analysis = None
            self.auto_running_engine = None
            try:
                self._auto_analyzed(*analysis.result())
            except Exception as exc:
                log_exception("Auto-Analyse", exc)
                self._message(t("Auto: {error}", error=exc), error=True)
                if dpg.does_item_exist("auto_window"):
                    dpg.set_value(self.auto_analysis_text, "")
            if getattr(self, "auto_batch", None):
                self._auto_batch_next()                    # nächste Auswertung der Regel
        future = self.auto_future
        if future is not None and future.done():
            self.auto_future = None
            self.auto_running_engine = None
            try:
                outcome = future.result()
                self._auto_done(outcome if isinstance(outcome, list) else [(dict(self._auto_job()), outcome)])
            except Exception as exc:                       # Quelle weg, keine Rechte ...
                log_exception("Auto-Zyklus", exc)
                self._message(t("Auto: {error}", error=exc), error=True)
        now = time.monotonic()
        if self.auto_running and now >= self.auto_next:
            self.auto_next = now + self.auto_settings.cycle_s
            if self.auto_future is not None:              # vorheriger Zyklus läuft noch: diesen auslassen
                text = t("Hinweis: Zyklus übersprungen - der vorherige läuft noch (Zykluszeit {cycle} zu kurz).",
                         cycle=limitconfig.format_time(self.auto_settings.cycle_s))
                for job in self._auto_ready_jobs():
                    self._auto_engine_for(job).log(text)
                if dpg.does_item_exist("auto_window"):
                    dpg.set_value(self.auto_hint, text)
            else:
                self._auto_submit()
        if now - getattr(self, "auto_shown", 0.0) > 1.0 and dpg.does_item_exist("auto_window") \
                and (dpg.is_item_shown("auto_window") or dpg.is_item_shown("auto_run_window")):
            self.auto_shown = now
            self._auto_refresh()

    def _auto_done(self, outcome: list) -> None:
        """Ergebnis eines Zyklus über alle Auswertungen: Tabelle, Hinweise, Vorschläge übernehmen."""
        rows, hints, messages = [], [], []
        total = auto.CycleResult(started=time.time())
        for job, result in outcome:
            if result.proposal is not None:               # ohne Konfiguration: Vorschlag je Auswertung übernehmen
                mode_name = next(iter(result.proposal.modes))
                if self.limit_cfg is None:
                    self.limit_cfg = result.proposal
                    self.set_limit_mode(next(iter(self.limit_cfg.modes)), quiet=True)
                elif mode_name not in self.limit_cfg.modes and mode_name in result.proposal.modes:
                    self.limit_cfg.modes[mode_name] = result.proposal.modes[mode_name]
                    self.limit_cfg.modified = True
                for stored in self.auto_jobs:
                    if stored["name"] == job["name"] and not stored.get("mode"):
                        stored["mode"] = mode_name
                self._refresh_mode_combo()
                self.open_limit_editor()
                messages.append(t("Auto: Keine Grenzwert-Konfiguration geladen - Vorschlag aus den Daten im Grenzwert-"
                                  "Konfigurator; bitte prüfen und speichern."))
            rows += [(job, key, entry) for key, entry in result.counters.items()]
            if result.collision:
                hints.append(f"[{job['name']}] " + t("Hinweis: Zykluszeit zu kurz für die Datenmenge - {files} Dateien und "
                                                     "{png} Bilder werden auf die nächsten Zyklen verteilt.",
                                                     files=result.deferred_files, png=result.deferred_png))
            if result.errors:
                hints.append(f"[{job['name']}] " + t("{count} Fehler (siehe Log).", count=len(result.errors)))
            total.new_files += result.new_files
            total.png_written += result.png_written
            total.counters.update(result.counters)
            total.seconds += result.seconds
            total.errors += result.errors
            total.forced = total.forced or result.forced
            total.deferred_files += result.deferred_files
            total.deferred_png += result.deferred_png
            total.json_path = result.json_path or total.json_path
        self.auto_last = total
        self.auto_last_jobs = outcome
        self._auto_store()
        hint = "  ".join(hints)
        if dpg.does_item_exist("auto_window"):
            dpg.set_value(self.auto_hint, hint)
            self._auto_fill_table(rows)
            if dpg.get_value(self.auto_log):
                self._auto_show_log()
        if total.new_files or total.collision or total.errors or total.forced:
            self._message(t("Auto: {jobs} Auswertungen, {files} Dateien neu, {png} Bilder, {count} Zähler, Ergebnis {path}",
                            jobs=len(outcome), files=len(total.new_files), png=total.png_written,
                            count=len(total.counters), path=total.json_path or t("(keine Zähler - kein Mode passt)"))
                          + (f"  {hint}" if hint else ""), error=bool(total.errors))
        elif messages:
            self._message(messages[0])
        self._auto_refresh()

    # ---------------------------------------------------------------- Limiter
    @staticmethod
    def _limiter_channel(dataset: Dataset, signal: str) -> Channel | None:
        for channel in dataset.channels:
            if channel.name == signal:
                return channel
        return next((c for c in dataset.channels if c.label == signal), None)

    @staticmethod
    def _limiter_fresh(channel: Channel) -> None:
        """Wurden die Daten seit dem Kürzen neu geladen (Downsampling, Neu-Import), gilt die alte Kürzung nicht mehr."""
        if channel.limit_key is not None and channel.x is not channel.limit_out:
            channel.raw, channel.limit_key, channel.limit_out = None, None, None

    def _apply_limiter(self) -> bool:
        """Alle geladenen Kanäle je Datei auf den Limit-Anteil kürzen bzw. ungekürzt zurückgeben.
        Gibt True zurück, wenn sich Daten geändert haben. Ohne Änderung der Regeln kostet der Aufruf fast nichts."""
        changed, config, state = False, self.limiter, {}
        for dataset in self.datasets:
            rules = config.rules_for(dataset.name) if config else []
            found, missing, waiting = [], [], []
            for rule in rules:
                channel = self._limiter_channel(dataset, rule.signal)
                if channel is None:
                    missing.append(rule.signal)
                    continue
                self._limiter_fresh(channel)
                if not channel.loaded:
                    waiting.append(channel)
                found.append((rule, channel))
            for channel in waiting:                       # MF4: Führungssignal erst laden (ohne es anzuzeigen)
                if channel not in self.loading:
                    self.loading[channel] = LIMITER
                    job = self._start_job(channel.name) if downsample.applies(channel.source) else None
                    self.pool.submit(self._channel_worker, channel, job)
            key = tuple(rule.key() for rule, _c in found) if found and not waiting else None
            old = self.limiter_state.get(dataset.path)
            share = old[0] if old and old[3] == key else None
            todo = []
            for channel in dataset.channels:
                self._limiter_fresh(channel)
                if channel.loaded and channel.limit_key != key:
                    todo.append(channel)
            if todo or (key is not None and share is None):
                guides = []
                if key is not None:
                    for rule, channel in found:
                        x, y = channel.raw if channel.raw is not None else (channel.x, channel.y)
                        guides.append((x, limiter.mask(y, rule.lo, rule.hi)))
                    share = limiter.kept_share(guides)
                for channel in todo:
                    if channel.raw is not None:
                        channel.x, channel.y = channel.raw
                        channel.raw = None
                    if key is not None:
                        raw = (channel.x, channel.y)
                        channel.x, channel.y = limiter.apply(channel.x, channel.y, guides)
                        channel.raw = raw
                    channel.limit_key, channel.limit_out = key, (channel.x if key is not None else None)
                    changed = True
            if rules:
                state[dataset.path] = (share, missing, [c.name for c in waiting], key)
        self.limiter_state = state
        if changed:
            for path, item in getattr(self, "limiter_hints", {}).items():
                dataset = next((d for d in self.datasets if d.path == path), None)
                if dataset is not None and dpg.does_item_exist(item):
                    dpg.set_value(item, self._limiter_text(dataset))
        return changed

    def _limiter_text(self, dataset: Dataset) -> str:
        share, missing, waiting, _key = self.limiter_state.get(dataset.path, (None, [], [], None))
        if waiting:
            return t("Limiter: lade {names}...", names=", ".join(waiting))
        text = (t("Limiter: {share} % der Messzeit im Limit", share=f"{share * 100:.1f}".replace(".", self._decimal()))
                if share is not None else t("Limiter: kein Führungssignal gefunden"))
        if missing:
            text += " | " + t("Nicht in der Datei: {names}", names=", ".join(missing))
        return text

    def _limiter_status(self) -> None:
        if dpg.does_item_exist("limiter_window"):
            lines = [f"{d.name}: {self._limiter_text(d)}" for d in self.datasets if d.path in self.limiter_state]
            dpg.set_value(self.lim_result, "\n".join(lines) if lines else (
                t("Keine Regel passt zu den geladenen Dateien.") if self.limiter and self.limiter.rules else ""))
            dpg.set_value(self.lim_file, self.limiter.path if self.limiter and self.limiter.path
                          else t("(nicht gespeichert)"))
        if dpg.does_item_exist(self.limiter_item):
            dpg.set_value(self.limiter_item, bool(self.limiter and self.limiter.active))
        if dpg.does_item_exist(getattr(self, "lim_active", 0) or 0):
            dpg.set_value(self.lim_active, bool(self.limiter and self.limiter.active))

    def _limiter_changed(self, fit: bool = False, relist: bool = False) -> None:
        """Regeln geändert: anwenden, Graphen und Wertanzeige aktualisieren."""
        self._apply_limiter()
        if getattr(self, "auto_stats", None) and dpg.does_item_exist(getattr(self, "auto_analysis_text", 0) or 0):
            dpg.set_value(self.auto_analysis_text, t("Limiter geändert: \"Grenzen neu vorschlagen\" berechnet die "
                                                     "Grenzen ohne die weggeschnittenen Spitzen."))
        if relist:
            self._refresh_channel_list()
        self._layout_changed()
        if fit:
            self._fit_all()
        self._limiter_status()

    def load_limiter(self, path: str, quiet: bool = False) -> bool:
        try:
            config = limiter.load(path)
        except LoadError as exc:
            self._message(str(exc), error=True)
            return False
        self.limiter = config
        self._limiter_changed(fit=True, relist=True)
        if dpg.is_item_shown("limiter_window"):
            self._lim_rows()
        if not quiet:
            self._message(t("Limiter geladen: {count} Regeln aus {name}.", count=len(config.rules), name=Path(path).name))
        return True

    def save_limiter(self, path: str) -> None:
        if self.limiter is None:
            self._message(t("Kein Limiter definiert."), error=True)
            return
        try:
            written = limiter.save(self.limiter, os.path.expanduser(path))
        except LoadError as exc:
            self._message(str(exc), error=True)
            return
        self._limiter_status()
        self._message(t("Limiter gespeichert: {path}", path=written))

    def _ask_limiter_save(self) -> None:
        if self.limiter is None:
            self._message(t("Kein Limiter definiert."), error=True)
            return
        folder = self.settings.get("last_dir_db") or self.settings.get("last_dir") or str(Path.home())
        default = self.limiter.path or str(Path(folder) / "Limiter.yaml")
        self._ask_save_path("Limiter-Konfiguration speichern", "Datei für die Limiter-Konfiguration (*.yaml):",
                            default, self.save_limiter)

    def set_limiter_active(self, active: bool) -> None:
        if self.limiter is None:
            if active:
                self.open_limiter_window()
            self._limiter_status()
            return
        self.limiter.active = bool(active)
        self._limiter_changed(fit=True, relist=True)
        self._message(t("Limiter aktiv.") if active else t("Limiter aus: alle Daten werden angezeigt."))

    def remove_limiter(self) -> None:
        self.limiter = None
        self._limiter_changed(fit=True, relist=True)
        if dpg.is_item_shown("limiter_window"):
            self._lim_rows()
        self._message(t("Limiter entfernt: alle Daten werden angezeigt."))

    def _build_limiter_window(self) -> None:
        with dpg.window(tag="limiter_window", label=t("Limiter"), show=False, width=980, height=560, no_collapse=True):
            with dpg.group(horizontal=True):
                self.lim_active = dpg.add_checkbox(label=t("Limiter aktiv"), default_value=True,
                                                   callback=lambda _s, v: self.set_limiter_active(v))
                dpg.add_button(label=t("Laden..."), small=True, callback=lambda: self._show_file_browser(
                    "limiter", lambda paths: self.load_limiter(paths[0]), "Limiter-Konfiguration laden"))
                dpg.add_button(label=t("Speichern"), small=True, callback=lambda: (
                    self.save_limiter(self.limiter.path) if self.limiter and self.limiter.path else self._ask_limiter_save()))
                dpg.add_button(label=t("Speichern unter..."), small=True, callback=lambda: self._ask_limiter_save())
                self.lim_file = dpg.add_text("")
                self._colour(self.lim_file, "text_dim")
            item = dpg.add_text(t("Je Regel: Datei, Führungssignal, untere und obere Grenze (leer = keine). Angezeigt werden "
                                  "nur die Abschnitte, in denen das Signal in seinen Grenzen liegt - für ALLE Signale "
                                  "dieser Datei. Mehrere Regeln einer Datei gelten gleichzeitig (UND). Datei * = alle "
                                  "Dateien mit diesem Signal, Muster wie lauf_*.csv sind möglich."), wrap=0)
            self._colour(item, "text_dim")
            dpg.add_separator()
            with dpg.group(horizontal=True):
                dpg.add_button(label=t("Regel hinzufügen"), callback=lambda: self._lim_add())
                dpg.add_button(label=t("Datei wählen..."), callback=lambda: self._lim_pick_files())
                self.lim_count = dpg.add_text("")
                self._colour(self.lim_count, "text_dim")
            with dpg.group(horizontal=True):
                dpg.add_text(t("Regel übertragen"))
                self.lim_xfer_rule = dpg.add_combo(items=[], width=360, callback=lambda: self._lim_xfer_refresh())
                self._tooltip(self.lim_xfer_rule, t("Diese Regel (Signal, Limit min/max, aktiv) auf die gewählten Dateien "
                                                    "anwenden"))
                self.lim_xfer_btn = dpg.add_button(label=t("Dateien: keine..."), width=240)
                with dpg.popup(self.lim_xfer_btn, mousebutton=dpg.mvMouseButton_Left, tag="lim_xfer_popup"):
                    with dpg.group(horizontal=True):
                        dpg.add_button(label=t("Alle"), small=True, callback=lambda: self._lim_xfer_select(True))
                        dpg.add_button(label=t("Keine"), small=True, callback=lambda: self._lim_xfer_select(False))
                        dpg.add_button(label=t("Nur mit Signal"), small=True, callback=lambda: self._lim_xfer_select(None))
                    self.lim_xfer_list = dpg.add_child_window(width=520, height=260, border=False)
                dpg.add_button(label=t("Auf Auswahl anwenden"), callback=lambda: self.lim_transfer())
                self.lim_xfer_note = dpg.add_text("")
                self._colour(self.lim_xfer_note, "text_dim")
            self.lim_table = dpg.add_child_window(height=-90, border=True)
            self.lim_result = dpg.add_text("", wrap=0)
            self._colour(self.lim_result, "heading")

    def open_limiter_window(self) -> None:
        if self.limiter is None:
            self.limiter = limiter.LimiterConfig()
        if not self.limiter.rules:
            self._lim_add(apply=False)
        vw, vh = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
        w, h = min(1040, int(vw * 0.85)), min(620, int(vh * 0.8))
        dpg.configure_item("limiter_window", show=True, width=w, height=h, pos=[max(0, (vw - w) // 2), max(0, (vh - h) // 3)])
        self._lim_rows()
        self._limiter_status()

    def _lim_sources(self) -> dict[str, list[str]]:
        """Dateien (bzw. Auswertungsgruppen) mit ihren Signalen für die Limiter-Auswahl: geladene Dateien,
        Dateien und Gruppen der Auto-Auswertungen (nach Analysieren/Zyklus) und manuell gewählte Dateien."""
        sources: dict[str, list[str]] = {}
        keys: dict[str, str] = {}                         # casefold -> angezeigter Name (jede Datei nur einmal)

        def add(name: str, signals) -> None:
            key = keys.setdefault(name.casefold(), name)
            names = sources.setdefault(key, [])
            names += [s for s in signals if s not in names]

        for dataset in self.datasets:
            add(dataset.name, [c.name for c in dataset.channels])
        jobs = list(getattr(self, "auto_jobs", []) or [])
        current = self._auto_job() if jobs else None
        for job in sorted(jobs, key=lambda j: j is not current):        # gewählte Auswertung zuerst
            engine = self.auto_engines.get(id(job))
            for group in (engine.groups.values() if engine else []):
                signals = []
                for data in group.files.values():
                    signals += [n for n in data.signals if n not in signals]
                if len(group.files) != 1:                # eine Datei: Gruppe = Datei, nur einmal anbieten
                    add(group.name, signals)             # Gruppe = alle Dateien der Auswertung
                for path, data in group.files.items():
                    add(Path(path).name, list(data.signals))
        for name, entry in (getattr(self, "auto_stats", None) or {}).items():
            for file in entry[1]:
                add(file, [name])
        for name, signals in self.lim_extra.items():
            add(name, signals)
        return sources

    def _lim_signal_names(self, pattern: str) -> list[str]:
        probe = limiter.Rule(file=pattern, signal="x")
        names = []
        for name, signals in self._lim_sources().items():
            if probe.matches_file(name):
                names += [s for s in signals if s not in names]
        return names

    def _lim_default_file(self) -> str:
        """Vorschlag für eine neue Regel: erste geladene Datei, sonst die Gruppe der gewählten Auto-Auswertung."""
        if self.datasets:
            return self.datasets[0].name
        if getattr(self, "auto_jobs", None):
            engine = self.auto_engines.get(id(self._auto_job()))
            if engine and engine.groups:
                group = next(iter(engine.groups.values()))
                return Path(next(iter(group.files))).name if len(group.files) == 1 else group.name
        return next(iter(self.lim_extra), "*")

    def _lim_pick_files(self) -> None:
        """Messdateien manuell wählen, nur ihre Signalnamen werden für die Regeln gelesen (nicht angezeigt)."""
        start = None
        if getattr(self, "auto_jobs", None):
            source = self._auto_job().get("source") or ""
            start = source if os.path.isdir(source) else None
        self._show_file_browser("data", self._lim_read_files, "Datei für den Limiter wählen", start_dir=start)

    def _lim_read_files(self, paths: list[str]) -> None:
        added, failed = [], []
        for path in paths:
            try:
                dataset = load_file(path)
            except (LoadError, OSError, ValueError) as exc:
                failed.append(f"{Path(path).name}: {exc}")
                continue
            self.lim_extra[dataset.name] = [c.name for c in dataset.channels]
            added.append(dataset.name)
        if added and self.limiter is not None:
            empty = [r for r in self.limiter.rules if not r.signal]
            for rule in empty[:1]:                        # leere erste Regel gleich auf die Datei setzen
                rule.file = added[0]
        if dpg.is_item_shown("limiter_window"):
            self._lim_rows()
        if added:
            self._message(t("Limiter: Signale aus {names} verfügbar.", names=", ".join(added)))
        if failed:
            self._message("; ".join(failed), error=True)

    def _lim_add(self, apply: bool = True) -> None:
        if self.limiter is None:
            self.limiter = limiter.LimiterConfig()
        self.limiter.rules.append(limiter.Rule(file=self._lim_default_file(), signal=""))
        if apply:
            self._lim_rows()
            self._limiter_status()

    def _lim_rows(self) -> None:
        """Regeltabelle neu aufbauen (Datei, Signal, Min, Max, aktiv, löschen)."""
        dpg.delete_item(self.lim_table, children_only=True)
        rules = self.limiter.rules if self.limiter else []
        files = ["*"] + [n for n in self._lim_sources() if n != "*"]
        known = {f.casefold() for f in files}
        for r in rules:                                   # Dateien nur einmal (ohne Rücksicht auf Groß/klein)
            if r.file.casefold() not in known:
                files.append(r.file)
                known.add(r.file.casefold())
        with dpg.table(parent=self.lim_table, header_row=True, resizable=True, borders_innerH=True,
                       policy=dpg.mvTable_SizingStretchProp):
            dpg.add_table_column(label=t("Aktiv"), init_width_or_weight=0.4)
            dpg.add_table_column(label=t("Datei"), init_width_or_weight=2.2)
            dpg.add_table_column(label=t("Signal"), init_width_or_weight=2.2)
            dpg.add_table_column(label=t("Limit min"), init_width_or_weight=1.0)
            dpg.add_table_column(label=t("Limit max"), init_width_or_weight=1.0)
            dpg.add_table_column(label="", init_width_or_weight=0.7)
            for index, rule in enumerate(rules):
                with dpg.table_row():
                    dpg.add_checkbox(default_value=rule.enabled, user_data=index,
                                     callback=lambda _s, v, i: self._lim_set(i, "enabled", v))
                    dpg.add_combo(items=files, default_value=rule.file, width=-1, user_data=index,
                                  callback=lambda _s, v, i: self._lim_set(i, "file", v))
                    names = self._lim_signal_names(rule.file)
                    if rule.signal and rule.signal not in names:
                        names = [rule.signal] + names
                    dpg.add_combo(items=names, default_value=rule.signal, width=-1, user_data=index,
                                  callback=lambda _s, v, i: self._lim_set(i, "signal", v))
                    for field in ("lo", "hi"):
                        value = getattr(rule, field)
                        dpg.add_input_text(default_value="" if value is None else f"{value:g}", width=-1, hint="-",
                                           user_data=(index, field), on_enter=False,
                                           callback=lambda _s, v, u: self._lim_set(u[0], u[1], v))
                    dpg.add_button(label=t("Löschen"), small=True, user_data=index,
                                   callback=lambda _s, _a, i: self._lim_delete(i))
        usable = sum(1 for r in rules if r.usable)
        dpg.set_value(self.lim_count, t("{count} Regeln, {usable} wirksam", count=len(rules), usable=usable))
        self._lim_xfer_refresh()

    # ---- Regel auf eine Auswahl von Dateien übertragen
    def _lim_rule_label(self, index: int, rule) -> str:
        def num(v):
            return "-" if v is None else f"{v:g}"
        return f"{index + 1}: {rule.file} / {rule.signal or '?'} [{num(rule.lo)} .. {num(rule.hi)}]"

    def _lim_xfer_rule_obj(self):
        rules = self.limiter.rules if self.limiter else []
        text = dpg.get_value(self.lim_xfer_rule) or ""
        for index, rule in enumerate(rules):
            if self._lim_rule_label(index, rule) == text:
                return rule
        return None

    def _lim_xfer_refresh(self) -> None:
        """Regel-Auswahl und Dateiliste (Häkchen) für das Übertragen aktualisieren; gewählte Häkchen bleiben."""
        if not dpg.does_item_exist(getattr(self, "lim_xfer_rule", 0) or 0):
            return
        rules = self.limiter.rules if self.limiter else []
        labels = [self._lim_rule_label(i, r) for i, r in enumerate(rules) if r.signal]
        current = dpg.get_value(self.lim_xfer_rule)
        dpg.configure_item(self.lim_xfer_rule, items=labels)
        if current not in labels:
            dpg.set_value(self.lim_xfer_rule, labels[0] if labels else "")
        rule = self._lim_xfer_rule_obj()
        old = {name: dpg.get_value(box) for name, box in getattr(self, "lim_xfer_boxes", {}).items()
               if dpg.does_item_exist(box)}
        dpg.delete_item(self.lim_xfer_list, children_only=True)
        self.lim_xfer_boxes = {}
        for name, signals in self._lim_sources().items():
            if rule is not None and name == rule.file:
                continue                                  # Ausgangsdatei der Regel
            has = rule is not None and rule.signal in signals
            label = name if has else f"{name}  ({t('ohne Signal')})"
            self.lim_xfer_boxes[name] = dpg.add_checkbox(label=label, default_value=old.get(name, False),
                                                         parent=self.lim_xfer_list, callback=lambda: self._lim_xfer_label())
        self._lim_xfer_label()

    def _lim_xfer_chosen(self) -> list[str]:
        return [name for name, box in getattr(self, "lim_xfer_boxes", {}).items() if dpg.get_value(box)]

    def _lim_xfer_label(self) -> None:
        chosen = self._lim_xfer_chosen()
        text = t("Dateien: keine...") if not chosen else (f"{chosen[0]}..." if len(chosen) == 1 else
                                                         t("Dateien: {count} gewählt...", count=len(chosen)))
        dpg.configure_item(self.lim_xfer_btn, label=text)

    def _lim_xfer_select(self, value) -> None:
        """Alle (True), keine (False) oder nur Dateien, die das Signal der Regel enthalten (None)."""
        rule = self._lim_xfer_rule_obj()
        sources = self._lim_sources()
        for name, box in self.lim_xfer_boxes.items():
            if value is None:
                dpg.set_value(box, rule is not None and rule.signal in sources.get(name, []))
            else:
                dpg.set_value(box, bool(value))
        self._lim_xfer_label()

    def lim_transfer(self) -> None:
        """Gewählte Regel auf die gewählten Dateien anwenden: vorhandene Regel (Datei + Signal) übernimmt Grenzen und
        aktiv, sonst wird eine Regel ergänzt."""
        rule = self._lim_xfer_rule_obj()
        chosen = self._lim_xfer_chosen()
        if rule is None or not chosen:
            dpg.set_value(self.lim_xfer_note, t("Bitte eine Regel und mindestens eine Datei wählen."))
            return
        sources = self._lim_sources()
        added, updated, missing = 0, 0, []
        for name in chosen:
            if rule.signal not in sources.get(name, []):
                missing.append(name)
            existing = next((r for r in self.limiter.rules if r is not rule and r.file == name and r.signal == rule.signal),
                            None)
            if existing is not None:
                existing.lo, existing.hi, existing.enabled = rule.lo, rule.hi, rule.enabled
                updated += 1
            else:
                self.limiter.rules.append(limiter.Rule(file=name, signal=rule.signal, lo=rule.lo, hi=rule.hi,
                                                       enabled=rule.enabled))
                added += 1
        for box in self.lim_xfer_boxes.values():
            dpg.set_value(box, False)
        self._lim_rows()
        self._limiter_changed(fit=True, relist=True)
        text = t("Regel übertragen: {added} neu, {updated} aktualisiert.", added=added, updated=updated)
        if missing:
            text += " " + t("Signal {signal} fehlt in: {names}", signal=rule.signal, names=", ".join(missing))
        dpg.set_value(self.lim_xfer_note, text)
        self._message(text, error=bool(missing))

    def _lim_set(self, index: int, field: str, value) -> None:
        if self.limiter is None or not 0 <= index < len(self.limiter.rules):
            return
        rule = self.limiter.rules[index]
        if field in ("lo", "hi"):
            text = str(value).strip().replace(",", ".")
            if text in ("", "-"):
                number = None
            else:
                try:
                    number = float(text)
                except ValueError:
                    return                                # unfertige Eingabe: alte Grenze bleibt
            setattr(rule, field, number)
        elif field == "enabled":
            rule.enabled = bool(value)
        else:
            setattr(rule, field, str(value))
        if field == "file":
            self._lim_rows()                              # Signalauswahl passend zur Datei
        else:
            usable = sum(1 for r in self.limiter.rules if r.usable)
            dpg.set_value(self.lim_count, t("{count} Regeln, {usable} wirksam", count=len(self.limiter.rules),
                                            usable=usable))
        self._limiter_changed(relist=field in ("file", "signal", "enabled"))

    def _lim_delete(self, index: int) -> None:
        if self.limiter and 0 <= index < len(self.limiter.rules):
            del self.limiter.rules[index]
            self._lim_rows()
            self._limiter_changed(fit=True, relist=True)

    def _build_limit_editor(self) -> None:
        heading, dim = themes.color(self.mode, "heading"), themes.color(self.mode, "text_dim")
        with dpg.window(tag="limit_editor", label=t("Grenzwert-Konfigurator"), show=False, width=1100, height=720,
                        no_collapse=True, on_close=lambda: self._le_closed()):
            with dpg.group(horizontal=True):
                self.le_file = dpg.add_text("")
                self._colour(self.le_file, "heading")
                dpg.add_button(label=t("Neu"), callback=lambda: self._le_new())
                dpg.add_button(label=t("Laden..."), callback=lambda: self._show_file_browser(
                    "limitconfig", lambda paths: self._le_load(paths[0]), "Grenzwert-Konfiguration laden"))
                dpg.add_button(label=t("Speichern"), callback=lambda: self._le_save())
                dpg.add_button(label=t("Speichern unter..."), callback=lambda: self._le_save(ask=True))
            item = dpg.add_text(t("Signale aus den geladenen Dateien. Je Mode: aktiv, untere und obere Grenze sowie "
                                  "steps (Zielabstand bis zur Grenzverletzung). Änderungen wirken sofort, wenn der "
                                  "Mode im Programm gewählt ist; Signale ohne aktive Grenze behalten die manuellen "
                                  "Werte."), wrap=0, color=dim)
            self._colour(item, "text_dim")
            dpg.add_separator()
            with dpg.group(horizontal=True):
                self._colour(dpg.add_text(t("Mode"), color=heading), "heading")
                self.le_mode = dpg.add_combo(items=[], width=230, callback=lambda _s, v: self._le_select_mode(v))
                self.le_mode_name = dpg.add_input_text(width=170, hint=t("Name für neuen Mode"))
                dpg.add_button(label=t("Anlegen"), callback=lambda: self._le_mode_action("add"))
                dpg.add_button(label=t("Kopieren"), callback=lambda: self._le_mode_action("copy"))
                dpg.add_button(label=t("Umbenennen"), callback=lambda: self._le_mode_action("rename"))
                dpg.add_button(label=t("Löschen"), callback=lambda: self._le_mode_action("delete"))
            with dpg.group(horizontal=True):
                dpg.add_text(t("Zielzeit (steps)"))
                self.le_steps = dpg.add_input_text(width=150, hint=t("z. B. 26306 oder 7h 18m 26s"),
                                                   callback=self._le_steps)
                self._tooltip(self.le_steps, t("Zielabstand bis zur Grenzverletzung: Zahl ohne Einheit = Schritte "
                                               "(Messpunkte), mit Einheiten = Zeit, z. B. 7h 18m 26s, 45m, 90s "
                                               "(auch d für Tage). Leer = keine."))
                self.le_steps_unit = dpg.add_text("")
                self._colour(self.le_steps_unit, "text_dim")
                self.le_use = dpg.add_button(label=t("Diesen Mode im Programm verwenden"), callback=lambda: self._le_use())
                self.le_state = dpg.add_text("")
                self._colour(self.le_state, "ok")
            with dpg.group(horizontal=True):
                self.le_filter = dpg.add_input_text(width=220, hint=t("Signal suchen"), callback=lambda: self._le_rows())
                self.le_only_active = dpg.add_checkbox(label=t("Nur aktive"), callback=lambda: self._le_rows())
                dpg.add_button(label=t("Sichtbare aktivieren"), callback=lambda: self._le_bulk_enable(True))
                dpg.add_button(label=t("Sichtbare deaktivieren"), callback=lambda: self._le_bulk_enable(False))
            with dpg.group(horizontal=True):
                dpg.add_text(t("Grenzen aus Daten vorschlagen:"))
                self._tooltip(dpg.add_button(label=t("Dieser Mode"), callback=lambda: self._le_suggest()),
                              t("Nur dieser Mode: sichtbare aktive Signale mit Daten bekommen neue Grenzen = "
                                "Datenbereich (Min/Max aller Dateien) plus Abstand in Prozent; vorhandene Grenzen "
                                "werden neu berechnet. Von Hand eingetragene Grenzen bleiben."))
                self._tooltip(dpg.add_button(label=t("Alle Modes"), callback=lambda: self._le_suggest_all()),
                              t("Alle Modes der Konfiguration: aktive Signale mit Daten (Suchfeld gilt) bekommen neue "
                                "Grenzen = Datenbereich plus Abstand in Prozent. Daten je Mode aus der Auto-Analyse "
                                "aller Dateien dieses Modes, sonst aus allen geladenen Dateien. Von Hand eingetragene "
                                "Grenzen bleiben."))
                dpg.add_text(t("Abstand"))
                self.le_margin = dpg.add_input_float(width=90, default_value=10.0, step=0, format="%.1f %%",
                                                     callback=lambda: self._le_margin_changed())
                self._tooltip(self.le_margin, t("Abstand der vorgeschlagenen Grenzen zum Datenbereich (Min/Max) in "
                                                "Prozent der Spannweite; gilt für beide Varianten. Ändern berechnet die "
                                                "Grenzen der sichtbaren aktiven Signale dieses Modes sofort neu (von "
                                                "Hand eingetragene bleiben)."))
            self.le_count = dpg.add_text("")
            self._colour(self.le_count, "text_dim")
            self.le_table_area = dpg.add_child_window(height=-1, border=True)
        self.le_widgets = {}

    def open_limit_editor(self) -> None:
        if self.limit_cfg is None:                     # noch keine Konfiguration: neue anlegen und gleich nutzen
            self._le_new(quiet=True)
        if self.le_edit_mode not in (self.limit_cfg.modes if self.limit_cfg else {}):
            own = self._auto_mode() if self.auto_jobs else None       # Standard: Mode = Name der Auswertung
            self.le_edit_mode = (own if own in self.limit_cfg.modes else None) or self.cfg_mode or \
                next(iter(self.limit_cfg.modes), None)
        vw, vh = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
        w, h = min(1180, int(vw * 0.9)), int(vh * 0.85)
        dpg.configure_item("limit_editor", show=True, width=w, height=h, pos=[max(0, (vw - w) // 2), max(0, (vh - h) // 2)])
        self._le_refresh()

    def _le_closed(self) -> None:
        if self.limit_cfg is not None and self.limit_cfg.modified:
            self._message(t("Grenzwert-Konfiguration geändert, aber nicht gespeichert (Graph-Optionen > Grenzwert-Konfigurator "
                            "> Speichern)."))

    def _le_new(self, quiet: bool = False) -> None:
        name = self._auto_mode() if self.auto_jobs else None
        self.limit_cfg = limitconfig.new_config(name or t("Standard"))     # Mode-Name = Name der Auswertung
        self.le_edit_mode = next(iter(self.limit_cfg.modes))
        self._refresh_mode_combo()
        self.set_limit_mode(self.le_edit_mode, quiet=True)
        self._le_refresh()
        if not quiet:
            self._message(t("Neue Grenzwert-Konfiguration mit Mode {name}; sie wirkt sofort.", name=self.le_edit_mode))

    def _le_load(self, path: str) -> None:
        if self.load_limit_config(path):
            self.le_edit_mode = self.cfg_mode or next(iter(self.limit_cfg.modes), None)
            self._le_refresh()

    def _le_save(self, ask: bool = False) -> None:
        if self.limit_cfg is None:
            return
        if ask or not self.limit_cfg.path:
            folder = self.settings.get("last_dir_db") or self.settings.get("last_dir") or str(Path.home())
            default = self.limit_cfg.path or str(Path(folder) / "Grenzwerte.yaml")
            self._ask_save_path("Grenzwert-Konfiguration speichern", "Datei für die Grenzwert-Konfiguration "
                                "(*.yaml):", default, self._le_write)
            return
        self._le_write(self.limit_cfg.path)

    def _le_write(self, path: str) -> None:
        try:
            written = limitconfig.save(self.limit_cfg, path)
        except LoadError as exc:
            self._message(str(exc), error=True)
            return
        self.settings["limit_config"] = os.path.abspath(written)
        self.settings["last_dir_db"] = os.path.dirname(os.path.abspath(written))
        self._save_settings()
        self._refresh_mode_combo()
        self._le_refresh(rows=False)
        self._message(t("Grenzwert-Konfiguration gespeichert: {path}", path=written))

    def _le_mode(self):
        return self.limit_cfg.modes.get(self.le_edit_mode) if self.limit_cfg is not None else None

    def _le_select_mode(self, value) -> None:
        self.le_edit_mode = value
        self._le_refresh()

    def _le_mode_action(self, action: str) -> None:
        config, current = self.limit_cfg, self.le_edit_mode
        if config is None:
            return
        name = dpg.get_value(self.le_mode_name).strip()
        try:
            if action == "add":
                config.add_mode(name)
                self.le_edit_mode = name
            elif action == "copy" and current:
                config.copy_mode(current, name or t("{name} (Kopie)", name=current))
                self.le_edit_mode = name or t("{name} (Kopie)", name=current)
            elif action == "rename" and current:
                config.rename_mode(current, name)
                if self.cfg_mode == current:
                    self.cfg_mode = name
                self.le_edit_mode = name
            elif action == "delete" and current:
                config.delete_mode(current)
                self.le_edit_mode = next(iter(config.modes), None)
                if self.cfg_mode == current:
                    self.cfg_mode = None
        except ValueError as exc:
            self._message(str(exc), error=True)
            return
        dpg.set_value(self.le_mode_name, "")
        self._refresh_mode_combo()
        self._apply_limit_source()
        self._le_refresh()

    def _le_use(self) -> None:
        if self.le_edit_mode:
            self.set_limit_mode(self.le_edit_mode)
            self._le_refresh(rows=False)

    def _le_steps(self, _sender, value, _user_data=None) -> None:
        mode = self._le_mode()
        if mode is None:
            return
        try:
            mode.set_steps(value)
        except ValueError:
            dpg.set_value(self.le_steps_unit, t("Eingabe unvollständig: Zahl = Schritte, Zeit wie 7h 18m 26s"))
            return                               # unvollständige Eingabe: bisheriger Wert bleibt
        self._le_changed(mode)

    def _le_changed(self, mode) -> None:
        """Nach jeder Änderung: als geändert markieren und, wenn der Mode im Programm gilt, sofort anwenden."""
        self.limit_cfg.modified = True
        if self.cfg_mode == mode.name:
            self._apply_limit_source()
        self._le_refresh(rows=False)

    def _le_signals(self) -> list:
        """(Name, Einheit, Dateien, Min, Max) je Signalname der geladenen Dateien; danach Signale nur im Mode."""
        info = {}
        for dataset in self.datasets:
            for channel in dataset.channels:
                entry = info.setdefault(channel.name, [channel.unit, [], np.inf, -np.inf])
                entry[1].append(dataset.name)
                if channel.y is not None and channel.y.size:
                    y = channel.y[np.isfinite(channel.y)]
                    if y.size:
                        entry[2], entry[3] = min(entry[2], float(y.min())), max(entry[3], float(y.max()))
        for name, (unit, files, lo, hi, _values) in self.auto_stats.items():     # Quellordner der Auto-Auswertung
            entry = info.setdefault(name, [unit, [], np.inf, -np.inf])
            entry[0] = entry[0] or unit
            entry[1].append(t("Auto: {count} Dateien", count=len(files)))
            if lo is not None:
                entry[2], entry[3] = min(entry[2], lo), max(entry[3], hi)
        rows = [(name, unit, files, lo if np.isfinite(lo) else None, hi if np.isfinite(hi) else None)
                for name, (unit, files, lo, hi) in info.items()]
        mode = self._le_mode()
        if mode is not None:
            known = {r[0] for r in rows}
            rows += [(name, "", [], None, None) for name in mode.entries if name not in known]
        return rows

    def _le_visible(self) -> list:
        words = dpg.get_value(self.le_filter).lower().split()
        only_active = dpg.get_value(self.le_only_active)
        mode = self._le_mode()
        out = []
        for row in self._le_signals():
            name = row[0]
            if words and not all(w in name.lower() for w in words):
                continue
            entry = mode.entries.get(name) if mode is not None else None
            if only_active and not (entry and entry.enabled):
                continue
            out.append(row)
        return out

    def _le_refresh(self, rows: bool = True) -> None:
        if not dpg.does_item_exist("limit_editor"):
            return
        config, mode = self.limit_cfg, self._le_mode()
        dpg.set_value(self.le_file, (config.name + ("  *" if config.modified else "")) if config else t("(keine)"))
        dpg.configure_item(self.le_mode, items=config.mode_names() if config else [])
        dpg.set_value(self.le_mode, self.le_edit_mode or "")
        if mode is not None and dpg.get_value(self.le_steps) != mode.steps_text():
            focused = False
            try:
                focused = dpg.is_item_focused(self.le_steps)
            except Exception:
                pass
            if not focused:                          # während der Eingabe nicht überschreiben
                dpg.set_value(self.le_steps, mode.steps_text())
        elif mode is None:
            dpg.set_value(self.le_steps, "")
        target = mode.target if mode is not None else None
        dpg.set_value(self.le_steps_unit, "" if target is None else (
            t("= {count} Schritte", count=f"{target[1]:g}") if target[0] == "steps"
            else t("= Zeit {time}", time=limitconfig.format_time(target[1]))))
        active = mode is not None and self.cfg_mode == mode.name
        dpg.set_value(self.le_state, t("wirkt im Programm") if active else "")
        dpg.configure_item(self.le_use, show=mode is not None and not active)
        if rows:
            self._le_rows()
        elif mode is not None:
            dpg.set_value(self.le_count, t("{active} aktive Signale im Mode, {matched} davon in den geladenen Dateien.",
                                           active=len(mode.signals), matched=self._le_matched(mode)))

    def _le_matched(self, mode) -> int:
        names = {c.name for d in self.datasets for c in d.channels} | set(self.auto_stats)
        return sum(1 for n in mode.signals if any(mode.lookup(x) is mode.signals[n] for x in names))

    def _le_rows(self) -> None:
        dpg.delete_item(self.le_table_area, children_only=True)
        self.le_widgets = {}
        mode = self._le_mode()
        if mode is None:
            dpg.add_text(t("Kein Mode: zuerst einen Mode anlegen."), parent=self.le_table_area)
            return
        rows = self._le_visible()
        shown = rows[:self.LE_FILTER_LIMIT]
        with dpg.table(parent=self.le_table_area, header_row=True, row_background=True, resizable=True,
                       borders_innerH=True, borders_innerV=True, policy=dpg.mvTable_SizingStretchProp,
                       scrollY=True, height=-1):
            for label, weight in (("Aktiv", 0.5), ("Signal", 2.2), ("Datei", 1.4), ("Daten min", 0.9),
                                  ("Daten max", 0.9), ("Untere Grenze", 1.0), ("Obere Grenze", 1.0)):
                dpg.add_table_column(label=t(label), init_width_or_weight=weight)
            for name, unit, files, lo, hi in shown:
                entry = mode.entries.get(name)
                with dpg.table_row():
                    box = dpg.add_checkbox(default_value=bool(entry and entry.enabled), callback=self._le_edit,
                                           user_data=(name, "enabled"))
                    label = name + (f" [{unit}]" if unit else "")
                    text = dpg.add_text(label if files else t("{name} (nicht in den Daten)", name=label))
                    if not files:
                        self._colour(text, "text_dim")
                    dpg.add_text(", ".join(dict.fromkeys(files)) if files else "-")
                    dpg.add_text("-" if lo is None else fmt(lo, unit))
                    dpg.add_text("-" if hi is None else fmt(hi, unit))
                    lower = dpg.add_input_text(width=-1, hint=t("leer = keine"), callback=self._le_edit,
                                               user_data=(name, "lower"),
                                               default_value="" if entry is None or entry.lower is None else f"{entry.lower:g}")
                    upper = dpg.add_input_text(width=-1, hint=t("leer = keine"), callback=self._le_edit,
                                               user_data=(name, "upper"),
                                               default_value="" if entry is None or entry.upper is None else f"{entry.upper:g}")
                    self.le_widgets[name] = (box, lower, upper)
        more = len(rows) - len(shown)
        text = t("{shown} Signale angezeigt", shown=len(shown)) + (
            "  " + t("({count} weitere: Suche eingrenzen)", count=more) if more > 0 else "")
        dpg.set_value(self.le_count, text + " · " + t("{active} aktive Signale im Mode, {matched} davon in den "
                                                      "geladenen Dateien.", active=len(mode.signals),
                                                      matched=self._le_matched(mode)))

    @staticmethod
    def _le_number(text):
        text = str(text or "").strip().replace(",", ".")
        if not text:
            return None
        return float(text)                         # ValueError: unvollständige Eingabe

    def _le_edit(self, _sender, value, user_data) -> None:
        name, field_name = user_data
        mode = self._le_mode()
        if mode is None:
            return
        entry = mode.entries.get(name) or limitconfig.Entry(False, None, None)
        enabled, lower, upper = entry.enabled, entry.lower, entry.upper
        try:
            if field_name == "enabled":
                enabled = bool(value)
            elif field_name == "lower":
                lower = self._le_number(value)
            else:
                upper = self._le_number(value)
        except ValueError:
            return
        if field_name != "enabled" and not entry.enabled and (lower is not None or upper is not None) \
                and name not in mode.entries:
            enabled = True                         # erste Grenze für ein neues Signal: gleich aktiv
            if name in self.le_widgets:
                dpg.set_value(self.le_widgets[name][0], True)
        if field_name != "enabled":                # von Hand eingetragen: Vorschläge überschreiben sie nicht
            if not hasattr(self, "le_manual"):
                self.le_manual = set()
            if lower is None and upper is None:
                self.le_manual.discard((mode.name, name))
            else:
                self.le_manual.add((mode.name, name))
        if not enabled and lower is None and upper is None:
            mode.remove_entry(name)               # nichts eingetragen: aus der Konfiguration nehmen
        else:
            mode.set_entry(name, enabled, lower, upper)
        self._le_changed(mode)

    def _le_bulk_enable(self, enabled: bool) -> None:
        mode = self._le_mode()
        if mode is None:
            return
        for name, *_rest in self._le_visible():
            entry = mode.entries.get(name)
            if entry is not None:
                mode.set_entry(name, enabled, entry.lower, entry.upper)
            elif enabled:
                mode.set_entry(name, True, None, None)
        self._le_changed(mode)
        self._le_rows()

    def _le_share(self) -> float:
        """Abstand in Prozent der Spannweite (gilt für beide Vorschlags-Varianten)."""
        return max(0.0, float(dpg.get_value(self.le_margin) or 0.0)) / 100.0

    def _le_fill(self, mode, rows, share: float) -> tuple[int, int]:
        """Aktive Signale mit Daten: Grenzen = Datenbereich plus Abstand (vorhandene Vorschläge werden neu berechnet).
        Von Hand im Konfigurator eingetragene Grenzen bleiben. Liefert (gesetzt, von Hand behalten)."""
        count = kept = 0
        manual = getattr(self, "le_manual", set())
        for name, _unit, _files, lo, hi in rows:
            entry = mode.entries.get(name)
            if entry is None or not entry.enabled or lo is None or hi is None:
                continue
            if (mode.name, name) in manual:
                kept += 1
                continue
            pad = (hi - lo) * share or abs(hi) * share or share
            mode.set_entry(name, True, round(lo - pad, 6), round(hi + pad, 6))
            count += 1
        return count, kept

    @staticmethod
    def _le_kept_text(kept: int) -> str:
        return "  " + t("{count} von Hand eingetragene Grenzen bleiben.", count=kept) if kept else ""

    def _le_suggest(self) -> None:
        """Nur dieser Mode: sichtbare aktive Signale mit Daten, Datenbereich plus Abstand in Prozent der Spannweite."""
        mode = self._le_mode()
        if mode is None:
            return
        share = self._le_share()
        count, kept = self._le_fill(mode, self._le_visible(), share)
        self._le_changed(mode)
        self._le_rows()
        self._message(t("Grenzen für {count} Signale aus den Daten vorgeschlagen ({pct} %).", count=count,
                        pct=f"{share * 100:g}") + self._le_kept_text(kept))

    def _le_margin_changed(self) -> None:
        """Abstand geändert: Vorschläge dieses Modes sofort neu berechnen."""
        self._le_suggest()

    def _le_mode_rows(self, mode_name: str) -> tuple[list, str]:
        """Datenbereiche für einen Mode: Auto-Analyse dieses Modes (alle Dateien seiner DUTs), sonst alle geladenen
        Dateien. Liefert (Zeilen wie _le_signals, Quelle)."""
        words = dpg.get_value(self.le_filter).lower().split()
        stats = self.auto_mode_stats.get(mode_name)
        if stats:
            rows, source = [(n, u, f, lo, hi) for n, (u, f, lo, hi) in stats.items()], "auto"
        else:
            rows, source = [], "files"
            info = {}
            for dataset in self.datasets:
                for channel in dataset.channels:
                    if channel.y is None or not channel.y.size:
                        continue
                    y = channel.y[np.isfinite(channel.y)]
                    if not y.size:
                        continue
                    lo, hi = info.get(channel.name, (np.inf, -np.inf))
                    info[channel.name] = (min(lo, float(y.min())), max(hi, float(y.max())))
            rows = [(n, "", [], lo, hi) for n, (lo, hi) in info.items()]
        return [r for r in rows if not words or all(w in r[0].lower() for w in words)], source

    def _le_suggest_all(self) -> None:
        """Alle Modes: je Mode aktive Signale ohne Grenzen aus den Daten dieses Modes (gleicher Prozent-Abstand)."""
        if self.limit_cfg is None:
            return
        share = self._le_share()
        total, touched, without, kept = 0, [], [], 0
        for name in self.limit_cfg.mode_names():
            mode = self.limit_cfg.modes[name]
            rows, source = self._le_mode_rows(name)
            if not rows and not self.auto_mode_stats.get(name):
                without.append(name)
                continue
            count, skipped = self._le_fill(mode, rows, share)
            kept += skipped
            if count:
                total += count
                touched.append(name)
        if touched:
            self.limit_cfg.modified = True
            if self.cfg_mode in touched:
                self._apply_limit_source()
        self._le_refresh(rows=False)
        self._le_rows()
        text = t("Grenzen für {count} Signale in {modes} Modes aus den Daten vorgeschlagen ({pct} %).", count=total,
                 modes=len(touched), pct=f"{share * 100:g}")
        if without:
            text += "  " + t("Ohne Daten: {names} (Auto > Analysieren oder Dateien laden).", names=", ".join(without))
        self._message(text + self._le_kept_text(kept))

    def close_limit_config(self) -> None:
        had = self.limit_cfg is not None
        self.limit_cfg, self.cfg_mode = None, None
        self.settings.pop("limit_config", None)
        self._save_settings()
        self._refresh_mode_combo()
        self._apply_limit_source()
        self.le_edit_mode = None
        if dpg.does_item_exist("limit_editor"):
            dpg.configure_item("limit_editor", show=False)
        if had:
            self._message(t("Grenzwert-Konfiguration entfernt: es gelten die manuellen Werte."))

    def _refresh_mode_combo(self) -> None:
        if not dpg.does_item_exist(getattr(self, "mode_combo", 0) or 0):
            return
        items = [t("(manuell)")] + (self.limit_cfg.mode_names() if self.limit_cfg else [])
        dpg.configure_item(self.mode_combo, items=items)
        dpg.set_value(self.mode_combo, self.cfg_mode or t("(manuell)"))
        if dpg.does_item_exist(getattr(self, "cfg_label", 0) or 0):
            text = (limitconfig.describe(self.limit_cfg) + (t("  * geändert") if self.limit_cfg.modified else "")
                    if self.limit_cfg else
                    t("Keine Grenzwert-Konfiguration geladen (Graph-Optionen > Grenzwert-Konfiguration laden)."))
            dpg.set_value(self.cfg_label, text)
            dpg.configure_item(self.cfg_save, show=self.limit_cfg is not None)

    def set_limit_mode(self, value, quiet: bool = False) -> None:
        mode = value if self.limit_cfg is not None and value in self.limit_cfg.modes else None
        self.cfg_mode = mode
        if dpg.does_item_exist(getattr(self, "mode_combo", 0) or 0):
            dpg.set_value(self.mode_combo, mode or t("(manuell)"))
        self._apply_limit_source()
        if dpg.does_item_exist("limit_editor") and dpg.get_item_configuration("limit_editor").get("show"):
            self._le_refresh(rows=False)
        if not quiet:
            if mode is None:
                self._message(t("Manuelle Grenzen und Zielzeiten."))
            else:
                matched, total = self._mode_matches()
                self._message(t("Mode {name}: {matched} von {total} Signalen der Konfiguration zugeordnet; die übrigen "
                                "Signale behalten die manuellen Werte.", name=mode, matched=matched, total=total))

    def _mode_spec(self):
        if self.limit_cfg is None or not self.limit_cfg.enabled or self.cfg_mode is None:
            return None
        return self.limit_cfg.modes.get(self.cfg_mode)

    def _mode_matches(self) -> tuple[int, int]:
        spec = self._mode_spec()
        if spec is None:
            return 0, 0
        names = {c.name for c in self.layout.signals()} | {c.name for d in self.datasets for c in d.channels}
        matched = {n for n in spec.signals if any(spec.lookup(x) is spec.signals[n] for x in names)}
        return len(matched), len(spec.signals)

    def _config_limits(self, channel: Channel):
        spec = self._mode_spec()
        return spec.lookup(channel.name) if spec is not None else None

    def _limits_for(self, slot: GraphSlot, channel: Channel) -> list:
        """Wirksame Grenzen: aus der Konfiguration (Mode, Signal zugeordnet), sonst die manuellen."""
        config = self._config_limits(channel)
        if config is not None:
            return list(config)
        return list(slot.limits.get(channel, [None, None]))

    def _target_for(self, slot: GraphSlot, channel: Channel):
        """Wirksames Ziel (Art, Wert, Quelle): ("steps", Messpunkte) oder ("s", Sekunden); None = keins.

        Hat der gewählte Mode steps, gilt dieses eine Ziel für alle Signale (wie im Konfigurator: eine Einstellung
        je Mode), auch für Signale ohne Eintrag in der Konfiguration; sonst die manuelle Zielzeit."""
        spec = self._mode_spec()
        if spec is not None and spec.target is not None:
            kind, value = spec.target                # Zahl = Schritte, Text mit Einheiten = Zeit
            return kind, value, "yaml"
        seconds = slot.targets.get(channel)
        return ("s", seconds, "manual") if seconds else None

    def _target_text(self, slot: GraphSlot, channel: Channel) -> str:
        target = self._target_for(slot, channel)
        if target is None:
            return ""
        kind, value, source = target
        if kind == "steps":
            text = t("{count} Schritte", count=f"{value:g}")
        else:
            text = limitconfig.format_time(value) if source == "yaml" else format_target(value)
        return text + (" (YAML)" if source == "yaml" else "")

    @staticmethod
    def _sample_step(channel: Channel) -> float:
        """Typischer Abstand zweier Messpunkte (Median, X-Einheiten); zwischengespeichert je Datenstand."""
        cache = getattr(channel, "_sample_step", None)
        if cache is not None and cache[0] is channel.x:
            return cache[1]
        step = NAN
        if channel.x is not None and channel.x.size > 1:
            dx = np.diff(channel.x[np.isfinite(channel.x)])
            dx = dx[dx > 0]
            if dx.size:
                step = float(np.median(dx))
        channel._sample_step = (channel.x, step)
        return step

    def _apply_limit_source(self) -> None:
        """Nach Wechsel von Konfiguration, Mode oder steps-Bedeutung: Linien, Tabelle und Bewertung neu."""
        for ui in self._all_ui():
            for channel in list(ui.series):
                self._update_limit_lines(ui, channel)
        if hasattr(self, "table_area") and dpg.does_item_exist(self.table_area):
            self._rebuild_table()

    # ---------------------------------------------------------------- Zielzeit (Prognose gegen Grenze)
    def _on_target(self, _sender, value, user_data) -> None:
        ui, channel = user_data
        effective = self._target_for(ui.slot, channel)
        if effective is not None and effective[2] == "yaml":      # steps des Modes (gilt für alle seine Signale)
            mode = self._mode_spec()
            try:
                mode.set_steps(value)
            except ValueError:
                return
            self.limit_cfg.modified = True
            for _other, _signal, box in self.target_box_list:  # steps gilt für jede Zeile der Wertanzeige
                if box != _sender and dpg.does_item_exist(box):
                    dpg.set_value(box, mode.steps_text())
            self._update_measurements()
            self._config_edited()
            if mode.target is None:                  # steps entfernt: Zielzeiten wieder manuell
                self._later(self._rebuild_table)
            return
        try:
            seconds = parse_duration(value)
        except ValueError:
            return                           # unvollständige Eingabe: bisherige Zielzeit bleibt
        if seconds is None or seconds <= 0:
            ui.slot.targets.pop(channel, None)
        else:
            ui.slot.targets[channel] = seconds
        self._sync_target_boxes(skip=_sender)
        self._update_measurements()

    def _target_to_all(self, _sender, _app_data, user_data) -> None:
        ui, channel = user_data
        seconds = ui.slot.targets.get(channel)
        count = 0
        for slot in self.layout.slots:
            for signal in slot.signals:
                if seconds:
                    slot.targets[signal] = seconds
                else:
                    slot.targets.pop(signal, None)
                count += 1
        self._sync_target_boxes()
        self._update_measurements()
        if seconds:
            self._message(t("Zielzeit {time} für alle {count} Signale übernommen.", time=format_target(seconds),
                            count=count))
        else:
            self._message(t("Zielzeit für alle {count} Signale entfernt.", count=count))

    def _sync_target_boxes(self, skip=None) -> None:
        for ui, channel, box in self.target_box_list:      # jede Zeile, auch gleichnamige Signale mehrerer Dateien
            if box == skip or not dpg.does_item_exist(box):
                continue
            effective = self._target_for(ui.slot, channel)
            if effective is not None and effective[2] == "yaml":
                dpg.set_value(box, self._mode_spec().steps_text())
                continue
            target = ui.slot.targets.get(channel)
            dpg.set_value(box, format_target(target) if target else "")

    def _violation(self, ui: SlotUI, channel: Channel, slope: float | None = None):
        """(verletzt, Sekunden bis zur Grenze) oder None, wenn keine Bewertung möglich ist.

        Verletzt, wenn die Prognose die Grenze früher als die Zielzeit erreicht (oder sie schon überschritten ist).
        Nur mit Markern, Grenze, Zielzeit und einer Zeitachse (Datumsachse oder X in s, min, h ...)."""
        target = self._target_for(ui.slot, channel)
        lo, hi = self._limits_for(ui.slot, channel)
        if not self.cross_on or not target or (lo is None and hi is None) or channel.y is None:
            return None
        kind, goal, _source = target
        if kind == "steps":                  # Zielabstand in Messpunkten: X-Abstand / typischer Messpunktabstand
            factor = self._sample_step(channel)
            if not (np.isfinite(factor) and factor > 0):
                return None
        else:
            factor = 1.0 if ui.time_axis else TIME_FACTORS.get((channel.x_unit or "").strip().lower())
            if factor is None:
                return None
        ok = np.flatnonzero(np.isfinite(channel.y))
        if not ok.size:
            return None
        slope = self._regression(channel) if slope is None else slope
        p = predict(slope, float(channel.y[ok[-1]]), lo, hi)
        if p.kind == "reached":
            return True, 0.0
        if p.kind not in ("max", "min"):
            return False, NAN
        if kind == "steps":
            remaining = p.x2 / factor        # Messpunkte bis zur Grenze
        else:
            remaining = p.x2 * factor        # Sekunden bis zur Grenze
        return remaining < goal, remaining

    def _alarm_slots(self) -> set:
        """Graphen mit mindestens einem Signal, dessen Zielzeit verletzt ist."""
        alarm = set()
        for slot in self.layout.slots:
            ui = self._ui_for(slot)
            if ui is not None and any((self._violation(ui, c) or (False,))[0] for c in slot.signals):
                alarm.add(id(slot))
        return alarm

    def _update_alarms(self, rows: list | None = None) -> None:
        """Zeilen rot und betroffene Graphen (auch im Detailfenster) schwach rot hinterlegen."""
        row_colour = (*themes.alarm_row_bg(self.mode), 255)
        flagged = set()
        for position, (ui, channel, _cells) in enumerate(self.table_rows):
            state = rows[position] if rows is not None and position < len(rows) else self._violation(ui, channel)
            bad = bool(state and state[0])
            if bad:
                flagged.add(id(ui.slot))
            if position < len(self.table_row_pos):
                table, number = self.table_row_pos[position]
                if not dpg.does_item_exist(table):
                    continue
                if bad:
                    dpg.highlight_table_row(table, number, row_colour)
                else:
                    dpg.unhighlight_table_row(table, number)
        if not self.table_rows:
            flagged = self._alarm_slots() if self.cross_on else set()
        plots = {ui.plot for ui in self._all_ui() if id(ui.slot) in flagged}
        for ui in self._all_ui():
            if not dpg.does_item_exist(ui.plot):
                continue
            if ui.plot in plots and ui.plot not in self.alarm_plots:
                dpg.bind_item_theme(ui.plot, self.alarm_themes[self.mode])
            elif ui.plot not in plots and ui.plot in self.alarm_plots:
                dpg.bind_item_theme(ui.plot, 0)
        self.alarm_plots = plots

    def _update_limit_lines(self, ui: SlotUI, channel: Channel) -> None:
        """Waagerechte Linien für Y min / Y max über den Datenbereich des Signals (nur wenn gesetzt)."""
        for item in ui.limit_series.pop(channel, []):
            if dpg.does_item_exist(item):
                dpg.delete_item(item)
        lo, hi = self._limits_for(ui.slot, channel)
        if (lo is None and hi is None) or channel.x is None or not channel.x.size or channel not in ui.colors:
            return
        off = self._offset(ui, channel)
        x0, x1 = float(channel.x[0] + off), float(channel.x[-1] + off)
        axis = ui.y2_axis if channel in ui.slot.right and ui.y2_axis is not None else ui.y_axis
        items = []
        for value in (lo, hi):
            if value is not None:
                item = dpg.add_line_series([x0, x1], [value, value], label=f"##grenze{len(items)}", parent=axis,
                                           show=self.cross_on)   # "##": ohne Eintrag in der Legende
                dpg.bind_item_theme(item, self._theme_for(ui.slot, channel, ui.colors[channel]))
                items.append(item)
        ui.limit_series[channel] = items

    def _regression_mb(self, channel: Channel) -> tuple[float, float]:
        """Regressionsgerade y = m*x + b über alle Daten des Signals nach der gewählten Art der Drift-Regression
        (zwischengespeichert je Datenstand und Art)."""
        if channel.x is None or not channel.x.size:
            return NAN, NAN
        method = self.reg_method
        cache = getattr(channel, "_regression", None)
        if cache is None or cache[0] is not channel.x or len(cache) < 4 or cache[1] != method:
            m, b = regression(channel.x, channel.y, method)
            cache = (channel.x, method, m, b)
            channel._regression = cache
        return cache[2], cache[3]

    def _regression(self, channel: Channel) -> float:
        """Steigung m der Regressionsgeraden über alle Daten des Signals."""
        return self._regression_mb(channel)[0]

    # ---------------------------------------------------------------- Regressionsgeraden im Graphen (gestrichelt)
    REG_DASHES = 48                       # Striche über den sichtbaren Ausschnitt
    REG_DASH_SHARE = 0.62                 # Anteil Strich je Strich + Lücke

    def _reg_extent(self, ui: SlotUI, channel: Channel):
        """(x0, x1, m, b) in Plotkoordinaten (mit Startzeit-Versatz) oder None."""
        m, b = self._regression_mb(channel)
        if not (np.isfinite(m) and np.isfinite(b)) or channel.x is None or channel.x.size < 2:
            return None
        ok = np.isfinite(channel.x)
        if not ok.any():
            return None
        off = float(self._offset(ui, channel) or 0.0)
        return float(channel.x[ok][0]) + off, float(channel.x[ok][-1]) + off, m, b - m * off

    def _dash_points(self, x0: float, x1: float, m: float, b: float, view=None):
        """Gerade als Striche (Lücken über NaN), gleich viele Striche über den sichtbaren Teil."""
        lo, hi = x0, x1
        if view is not None and view[1] > view[0]:
            lo, hi = max(x0, view[0]), min(x1, view[1])
        if hi <= lo:
            return [], []
        step = (hi - lo) / self.REG_DASHES
        xs = []
        for k in range(self.REG_DASHES):
            start = lo + k * step
            xs += [start, start + step * self.REG_DASH_SHARE, NAN]
        xs = np.asarray(xs)
        ys = m * xs + b
        return xs.tolist(), ys.tolist()

    @staticmethod
    def _series_active(ui: SlotUI, channel: Channel) -> bool:
        """Signal im Graphen aktiv: nicht über die Legende (Klick auf den Eintrag, Dear PyGui/ImPlot) ausgeblendet."""
        series = ui.series.get(channel)
        if series is None or not dpg.does_item_exist(series):
            return False
        try:
            return bool(dpg.get_item_configuration(series).get("show", True))
        except Exception:                              # ältere Versionen ohne Konfiguration der Serie
            return True

    def _apply_series(self, ui: SlotUI, channel: Channel) -> None:
        """Daten einer Serie: Kurve und - durch eine Lücke (NaN) getrennt - die Striche ihrer Regressionsgeraden.
        Kurve und Regressionslinie sind so ein Element: ein Eintrag im Signalspiegel (Legende), und das Aktivieren/
        Deaktivieren dort schaltet beide gemeinsam."""
        series = ui.series.get(channel)
        if series is None or not dpg.does_item_exist(series):
            return
        x, y = ui.curve.get(channel, ([], []))
        reg = ui.reg_points.get(channel)
        if reg is not None and len(reg[0]):
            x = list(x) + [float("nan")] + list(reg[0])
            y = list(y) + [float("nan")] + list(reg[1])
        dpg.set_value(series, [x, y])

    def _update_reg_line(self, ui: SlotUI, channel: Channel, view=None) -> None:
        had = ui.reg_points.pop(channel, None) is not None
        ui.reg_series.pop(channel, None)
        if self.reg_on and channel in ui.colors and not self._is_bar(channel):
            extent = self._reg_extent(ui, channel)
            if extent is not None:
                ui.reg_points[channel] = self._dash_points(*extent, **({"view": view} if view else {}))
                ui.reg_series[channel] = ui.series[channel]     # dieselbe Serie (gemeinsamer Legendeneintrag)
        if had or channel in ui.reg_points:
            self._apply_series(ui, channel)
        ui.reg_view = None

    def _set_regression(self, value: bool) -> None:
        self.reg_on = bool(value)
        self.settings["regression_lines"] = self.reg_on
        self._save_settings()
        for box in (getattr(self, "reg_box", None), getattr(self, "zoom_reg", None), getattr(self, "reg_menu_item", None)):
            if box is not None and dpg.does_item_exist(box):
                dpg.set_value(box, self.reg_on)
        for ui in self._all_ui():
            for channel in list(ui.series):
                self._update_reg_line(ui, channel)

    def _reg_number(self, method: str | None = None) -> int:
        """Nummer der Regressionsart wie im Menü Graph-Optionen: (1), (2), ..."""
        return list(REG_METHODS).index(method or self.reg_method) + 1

    def _drift_label(self) -> str:
        """Spaltenkopf mit der gewählten Art: Drift (Regression 1), Drift (Regression 2), ..."""
        return t("Drift (Regression {number})", number=self._reg_number())

    def set_regression_method(self, method: str, quiet: bool = False) -> None:
        """Art der Drift-Regression wählen: gilt für Drift (Regression), Prognose, Zielzeit, Regressionslinien,
        Druck/Export und Report."""
        if method not in REG_METHODS:
            return
        self.reg_method = method
        self.settings["regression_method"] = method
        self._save_settings()
        for key, item in getattr(self, "reg_method_items", {}).items():
            if dpg.does_item_exist(item):
                dpg.set_value(item, key == method)
        for ui in self._all_ui():
            for channel in list(ui.series):
                self._update_reg_line(ui, channel)
        if hasattr(self, "table_area") and dpg.does_item_exist(self.table_area):
            self._rebuild_table()                  # Spalten Drift (Regression) und Prognose neu
        if not quiet:
            self._message(t("Drift-Regression: {name}", name=f"({self._reg_number()}) " + t(REG_METHODS[method])))

    def _poll_reg_dashes(self) -> None:
        """Striche an den sichtbaren Ausschnitt anpassen (beim Zoomen bleiben sie gleich lang)."""
        for ui in self._all_ui():
            if not ui.reg_series or not dpg.does_item_exist(ui.x_axis):
                continue
            view = tuple(float(v) for v in dpg.get_axis_limits(ui.x_axis))
            if view == ui.reg_view or view[1] <= view[0]:
                continue
            ui.reg_view = view
            for channel in list(ui.reg_series):
                extent = self._reg_extent(ui, channel)
                if extent is not None:
                    ui.reg_points[channel] = self._dash_points(*extent, view=view)
                    self._apply_series(ui, channel)

    def _prediction_text(self, ui: SlotUI, channel: Channel, slope: float) -> str:
        """x2 = (y2 - b) / m: b = letzter y-Wert (x1 = 0), m aus der Regression, y2 = Y max bzw. Y min.

        Datumsachse: "max, 08.11.2026 20:02:01, 2 days 6 hrs 2 min"; sonst x2 in X-Einheiten.
        """
        lo, hi = self._limits_for(ui.slot, channel)
        if lo is None and hi is None or channel.y is None:
            return "-"
        ok = np.flatnonzero(np.isfinite(channel.y))
        if not ok.size:
            return "-"
        last = ok[-1]
        x_last, y_last = float(channel.x[last]), float(channel.y[last])
        p = predict(slope, y_last, lo, hi)
        if p.kind == "inside":
            return t("kein Schnitt (Drift führt von der Grenze weg)")
        if p.kind == "reached":
            return t("Grenze {limit} schon überschritten (letzter Wert {value})", limit=fmt(p.limit, channel.unit),
                     value=fmt(y_last, channel.unit))
        if p.kind not in ("max", "min"):
            return "-"
        if ui.time_axis:
            target = format_wallclock(x_last + self._offset(ui, channel) + p.x2)[:19]
            return f"{p.kind}, {target}, {self._days_hours_minutes(p.x2)}"
        text = f"{p.kind}, x2 = {fmt(p.x2, channel.x_unit)}"
        if channel.x_unit == "s":
            text += f", {self._days_hours_minutes(p.x2)}"
        elif not channel.x_unit:
            text += f" ({channel.x_name})"
        return text

    @staticmethod
    def _days_hours_minutes(seconds: float) -> str:
        minutes = int(round(seconds / 60.0))
        days, rest = divmod(minutes, 1440)
        hours, mins = divmod(rest, 60)
        return t("{days} days {hours} hrs {minutes} min", days=days, hours=hours, minutes=mins)

    def _measure_values(self, ui: SlotUI, channel: Channel) -> list[str]:
        """X1, X2, Wert 1, Wert 2, Delta X, Delta Y, Drift als Text (Wertanzeige und Report)."""
        c1, c2 = ui.slot.cross
        off = self._offset(ui, channel)
        m = measure(channel.x, channel.y, None if c1 is None else c1 - off, None if c2 is None else c2 - off)
        xu = channel.x_unit
        if ui.time_axis:
            x1, x2 = format_wallclock(c1), format_wallclock(c2)
            dx = format_duration(m.delta_x)
        else:
            x1, x2, dx = fmt(m.x1, xu), fmt(m.x2, xu), fmt(m.delta_x, xu)
        return [x1, x2, self._with_text(channel, m.value1), self._with_text(channel, m.value2),
                dx, fmt(m.delta_y, channel.unit), fmt(m.drift, drift_unit(channel.unit, xu))]

    @staticmethod
    def _with_text(channel: Channel, value: float) -> str:
        """Messwert, bei Wert->Text-Umrechnung mit dem Text des nächsten Rohwerts, z. B. 3 (Charging)."""
        text = fmt(value, channel.unit)
        table = channel.value_text
        if table and np.isfinite(value):
            key = float(round(value))
            label = table.get(key) if abs(value - key) < 1e-6 else None
            if label:
                text += f" ({label})"
        return text

    def _update_measurements(self) -> None:
        self._update_harmonics()                       # Balken der Harmonischen folgen den Markern
        if not self.cross_on:
            self._update_alarms([None] * len(self.table_rows))   # ohne Marker keine Bewertung
            return
        preds = self.table_preds if len(self.table_preds) == len(self.table_rows) else [None] * len(self.table_rows)
        states = []
        for (ui, channel, cells), pred in zip(self.table_rows, preds):
            states.append(self._violation(ui, channel))
            values = self._measure_values(ui, channel)
            xu = channel.x_unit
            for cell, text in zip(cells, values):
                dpg.set_value(cell, text)
            if pred is not None:
                slope_text, pred_text = pred
                m_reg = self._regression(channel)
                dpg.set_value(slope_text, fmt(m_reg, drift_unit(channel.unit, xu)) if np.isfinite(m_reg) else "-")
                text = self._prediction_text(ui, channel, m_reg)
                state = states[-1]
                if state is not None and state[0]:
                    text += "  " + t("(Zielzeit {time} verletzt)", time=self._target_text(ui.slot, channel))
                dpg.set_value(pred_text, text)
        self._update_alarms(states)

    # ---------------------------------------------------------------- Laufende Prüfungen
    def _poll_detail(self) -> None:
        """Passt die reduzierte Darstellung langer Signale an den sichtbaren Bereich an."""
        now = time.monotonic()
        if now - self.last_lod < LOD_INTERVAL:
            return
        self.last_lod = now
        for ui in self._all_ui():
            if not any(c.x.size > LOD_POINTS for c in ui.series):
                continue
            limits = tuple(dpg.get_axis_limits(ui.x_axis))
            if limits == ui.limits or limits[1] <= limits[0]:
                continue
            ui.limits = limits
            for channel, series in ui.series.items():
                if channel.x.size > LOD_POINTS:
                    off = self._offset(ui, channel)
                    x, y = view_points(channel.x, channel.y, limits[0] - off, limits[1] - off)
                    ui.curve[channel] = ((x + off).tolist(), y.tolist())
                    self._apply_series(ui, channel)

    def _poll_height(self) -> None:
        if self.subplots is None:
            return
        if self.row_subplots:
            height = self._row_height(self.layout.grid()[0])
            if height != self.last_height:
                self.last_height = height
                for sub in self.row_subplots:
                    dpg.configure_item(sub, height=height)
            return
        height = self._subplot_height(self.layout.grid()[0])
        if height != self.last_height:
            self.last_height = height
            dpg.configure_item(self.subplots, height=height)

    def _poll_splitters(self) -> None:
        """Trenner ziehen: solange die Maustaste auf dem Trenner gehalten wird, folgt die Größe der Maus."""
        for name, item in (("left", self.split_left), ("table", self.split_table)):
            active = dpg.is_item_active(item)
            if active and (self.split_drag is None or self.split_drag[0] != name):
                start = self.left_width if name == "left" else self.table_h
                self.split_drag = (name, dpg.get_mouse_pos(local=False), start)
            elif active:
                _, origin, start = self.split_drag
                pos = dpg.get_mouse_pos(local=False)
                if name == "left":
                    limit = dpg.get_viewport_client_width() - MIN_PLOTS
                    width = int(max(MIN_LEFT, min(start + pos[0] - origin[0], limit)))
                    if width != self.left_width:
                        self.left_width = width
                        dpg.configure_item(self.left_panel, width=width)
                else:
                    limit = dpg.get_viewport_client_height() - MIN_PLOTS
                    height = int(max(MIN_TABLE, min(start - (pos[1] - origin[1]), limit)))
                    if height != self.table_h:
                        self.table_h = height
                        dpg.configure_item(self.table_area, height=height)
                        dpg.configure_item(self.plot_area, height=self._plot_area_height())
            elif self.split_drag is not None and self.split_drag[0] == name:
                self.split_drag = None
                self.settings["left_width"], self.settings["table_height"] = self.left_width, self.table_h
                self._save_settings()

    def _later(self, func, frames: int = 2) -> None:
        """func erst einige Bilder später ausführen.

        Dear PyGui öffnet kein modales Fenster, solange im selben Bild ein anderes modales Fenster oder Popup
        geschlossen wird (Rechendialog -> Datei-Browser, Datei-Browser -> Auswahldialog, Kontextmenü -> Export).
        """
        self.deferred.append([frames, func])

    def _run_deferred(self) -> None:
        due = []
        for item in list(self.deferred):
            item[0] -= 1
            if item[0] <= 0:
                self.deferred.remove(item)
                due.append(item[1])
        for func in due:
            func()

    def tick(self) -> None:
        """Einmal je Bild im Render-Thread."""
        self._run_deferred()
        self._poll_splitters()
        self._poll_menu_spacer()
        self._poll_toolbar_width()
        self._drain_results()
        self._poll_progress()
        self._poll_screenshots()
        self._poll_crosslines()
        self._poll_m3()
        self._poll_view()
        self._poll_link()
        self._poll_y_release()
        self._poll_reg_dashes()
        self._poll_comment_drag()
        self._poll_m3_tip()
        self._poll_marker_tip()
        self._poll_y2_pan()
        self._snapshot_y2()
        self._poll_detail()
        self._poll_height()
        self._poll_auto()

    # ---------------------------------------------------------------- Lauf
    def run(self) -> None:
        self.build()
        dpg.setup_dearpygui()
        dpg.show_viewport()
        projects = [p for p in self.initial_files if p.lower().endswith(project.SUFFIX)]
        if projects:   # main.py Projekt.mgproj: Projekt öffnen
            self.open_project(projects[0])
        elif self.initial_files:
            self.open_files(self.initial_files)
        elif self.settings.get("restore_last") and LAST_SESSION.exists():
            self.load_session(str(LAST_SESSION))
        while dpg.is_dearpygui_running():
            try:
                jobs = dpg.get_callback_queue()
                dpg.run_callbacks(jobs)
                self.tick()
            except Exception as exc:  # ein Bedienfehler soll das Programm nicht beenden
                log_exception("Bedienung", exc)
                self._message(f"{t('Interner Fehler: {error}', error=f'{type(exc).__name__}: {exc}')}  ({t('Details: {path}', path=LOG_FILE)})", error=True)
            dpg.render_dearpygui_frame()
        self.shutdown()

    def shutdown(self) -> None:
        if self.settings.get("restore_last") and not self.shots:
            try:
                sessions.write_session(str(LAST_SESSION), self.session_dict(str(LAST_SESSION.parent)))
            except OSError:
                pass
        self.pool.shutdown(wait=False, cancel_futures=True)
        if self.auto_pool is not None:
            self.auto_pool.shutdown(wait=False, cancel_futures=True)
        for dataset in self.datasets:
            dataset.close()
        dpg.destroy_context()
