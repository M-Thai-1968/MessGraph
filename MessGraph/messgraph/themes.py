"""Farbschemata (Hell, Dunkel und weitere): Farben und Dear-PyGui-Themes.

Farbkonstanten werden über ihren Namen geholt, weil sich die Plot-Konstanten
zwischen Dear-PyGui-Versionen unterscheiden. Fehlende werden übersprungen.
"""
from __future__ import annotations

import dearpygui.dearpygui as dpg

DARK, LIGHT = "Dunkel", "Hell"
SOLAR_DARK, SOLAR_LIGHT, NORD, CONTRAST, PAPER, COLORBLIND = (
    "Solar dunkel", "Solar hell", "Nord", "Kontrast", "Papier", "Farbenblind")

PALETTE = {
    DARK: {
        "window": (24, 27, 32), "child": (30, 34, 40), "popup": (36, 40, 47), "border": (66, 72, 82),
        "frame": (44, 49, 57), "frame_hover": (58, 65, 75), "frame_active": (70, 78, 90),
        "title": (24, 27, 32), "title_active": (36, 40, 47), "menu": (30, 34, 40),
        "button": (46, 88, 130), "button_hover": (58, 108, 158), "button_active": (70, 126, 182),
        "header": (46, 56, 68), "header_hover": (58, 72, 88), "header_active": (70, 88, 108),
        "tab": (36, 40, 47), "tab_hover": (58, 108, 158), "tab_active": (46, 88, 130),
        "text": (226, 230, 236), "text_dim": (150, 158, 170), "heading": (122, 186, 255),
        "error": (255, 120, 110), "ok": (120, 210, 150), "check": (122, 186, 255),
        "table_header": (44, 49, 57), "row_alt": (36, 40, 47),
        "plot_bg": (18, 20, 24), "plot_frame": (30, 34, 40), "grid": (70, 76, 86),
        "cross": [(255, 170, 60), (90, 220, 230)],
        "series": [(100, 170, 255), (255, 140, 90), (110, 215, 130), (225, 115, 200),
                   (235, 205, 90), (90, 215, 215), (175, 150, 255), (200, 200, 200)],
    },
    LIGHT: {
        "window": (243, 244, 246), "child": (252, 252, 253), "popup": (255, 255, 255), "border": (190, 195, 203),
        "frame": (229, 231, 235), "frame_hover": (214, 218, 224), "frame_active": (198, 204, 212),
        "title": (229, 231, 235), "title_active": (214, 218, 224), "menu": (235, 236, 239),
        "button": (46, 110, 175), "button_hover": (38, 96, 156), "button_active": (30, 82, 136),
        "header": (216, 226, 238), "header_hover": (198, 214, 232), "header_active": (178, 200, 226),
        "tab": (224, 227, 232), "tab_hover": (120, 170, 220), "tab_active": (46, 110, 175),
        "text": (28, 32, 38), "text_dim": (92, 100, 112), "heading": (20, 84, 150),
        "error": (190, 40, 30), "ok": (20, 125, 70), "check": (30, 96, 165),
        "table_header": (224, 227, 232), "row_alt": (243, 244, 246),
        "plot_bg": (255, 255, 255), "plot_frame": (252, 252, 253), "grid": (205, 209, 215),
        "cross": [(205, 95, 0), (0, 125, 150)],
        "series": [(0, 92, 190), (205, 75, 25), (15, 135, 65), (170, 50, 150),
                   (150, 115, 0), (0, 130, 135), (100, 75, 200), (75, 80, 90)],
    },
}


def _mix(a, b, share: float):
    return tuple(int(round(x + (y - x) * share)) for x, y in zip(a, b))


def _scheme(window, text, accent, series, cross, plot_bg=None, error=None, ok=None, dark=True,
            button_text_on_accent=True) -> dict:
    """Vollständiges Schema aus wenigen Grundfarben: Flächen werden zwischen Hintergrund und Text abgestuft."""
    step = (lambda k: _mix(window, text, k))
    plot_bg = plot_bg or (_mix(window, (0, 0, 0), 0.25) if dark else _mix(window, (255, 255, 255), 0.6))
    button = _mix(accent, window, 0.45 if dark else 0.62)
    return {
        "window": window, "child": step(0.03), "popup": step(0.06), "border": step(0.22),
        "frame": step(0.09), "frame_hover": step(0.15), "frame_active": step(0.21),
        "title": window, "title_active": step(0.06), "menu": step(0.03),
        "button": button, "button_hover": _mix(button, accent if not dark else window, 0.2 if dark else 0.25),
        "button_active": _mix(button, accent if not dark else window, 0.35),
        "header": _mix(step(0.08), accent, 0.15), "header_hover": _mix(step(0.12), accent, 0.25),
        "header_active": _mix(step(0.16), accent, 0.35),
        "tab": step(0.06), "tab_hover": _mix(button, window, 0.2), "tab_active": button,
        "text": text, "text_dim": step(0.6), "heading": accent,
        "error": error or ((255, 120, 110) if dark else (190, 40, 30)), "ok": ok or ((120, 210, 150) if dark else (20, 125, 70)),
        "check": accent, "table_header": step(0.09), "row_alt": step(0.05),
        "plot_bg": plot_bg, "plot_frame": step(0.03), "grid": _mix(plot_bg, text, 0.2),
        "cross": list(cross), "series": list(series),
    }


# Weitere Schemata: Linienfarben je Hintergrund abgestimmt (Kontrast mindestens 3:1, untereinander unterscheidbar)
PALETTE.update({
    # Solarized (Ethan Schoonover): ruhiges Petrol mit warmen und kühlen Akzenten
    SOLAR_DARK: _scheme((0, 43, 54), (238, 232, 213), (38, 139, 210),
                        [(38, 139, 210), (203, 75, 22), (133, 153, 0), (211, 54, 130), (181, 137, 0),
                         (42, 161, 152), (108, 113, 196), (147, 161, 161)],
                        [(253, 160, 40), (147, 230, 220)], plot_bg=(0, 34, 43)),
    SOLAR_LIGHT: _scheme((238, 232, 213), (7, 54, 66), (38, 110, 175),
                         [(31, 110, 175), (190, 65, 15), (100, 120, 0), (185, 40, 110), (150, 105, 0),
                          (20, 125, 118), (90, 90, 180), (88, 110, 117)],
                         [(225, 0, 0), (7, 54, 66)], plot_bg=(253, 246, 227), dark=False),
    # Nord: kühles Blaugrau, gedämpfte Pastellfarben
    NORD: _scheme((46, 52, 64), (236, 239, 244), (136, 192, 208),
                  [(136, 192, 208), (208, 135, 112), (163, 190, 140), (180, 142, 173), (235, 203, 139),
                   (216, 222, 233), (110, 140, 230), (191, 97, 106)],
                  [(255, 120, 200), (120, 255, 180)], plot_bg=(36, 41, 51), error=(220, 110, 120)),
    # Hoher Kontrast: Schwarz mit kräftigen, reinen Farben (Beamer, Sonnenlicht)
    CONTRAST: _scheme((0, 0, 0), (255, 255, 255), (255, 220, 0),
                      [(0, 200, 255), (255, 80, 80), (60, 255, 60), (255, 230, 0), (255, 110, 255),
                       (255, 160, 30), (160, 160, 255), (255, 255, 255)],
                      [(255, 0, 128), (0, 255, 200)], plot_bg=(0, 0, 0), error=(255, 90, 90), ok=(80, 255, 120)),
    # Papier: warmes Cremeweiß mit kräftigen, druckähnlichen Tinten
    PAPER: _scheme((244, 238, 224), (40, 34, 28), (150, 60, 30),
                   [(30, 70, 150), (175, 45, 30), (35, 115, 55), (125, 50, 125), (140, 95, 10),
                    (10, 115, 120), (80, 60, 40), (190, 85, 0)],
                   [(210, 0, 110), (0, 150, 210)], plot_bg=(252, 248, 238), dark=False),
    # Farbenblind: Okabe-Ito-Farben auf dunklem Grund, auch bei Rot-Grün-Schwäche unterscheidbar
    COLORBLIND: _scheme((28, 30, 34), (235, 235, 235), (86, 180, 233),
                        [(230, 159, 0), (86, 180, 233), (0, 158, 115), (240, 228, 66), (213, 94, 0),
                         (204, 121, 167), (130, 160, 255), (150, 150, 150)],
                        [(255, 255, 255), (0, 220, 255)], plot_bg=(16, 17, 20)),
})
PALETTE[CONTRAST].update({"button": (0, 80, 160), "button_hover": (0, 60, 120), "button_active": (0, 45, 95),
                          "tab_active": (0, 80, 160), "tab_hover": (0, 60, 120)})
MODES = list(PALETTE)


def alarm_plot_bg(mode: str):
    """Schwach roter Plothintergrund (Zielzeit verletzt): Plotfarbe des Schemas leicht ins Rote gezogen."""
    c = PALETTE[mode]
    if is_dark(mode):     # dunkles Rot: der Grund bleibt dunkel, die Linien behalten ihren Kontrast
        return _mix(c["plot_bg"], (125, 18, 24), 0.34)
    return _mix(c["plot_bg"], c["error"], 0.11)


def alarm_row_bg(mode: str):
    """Rot hinterlegte Tabellenzeile, Text des Schemas bleibt lesbar."""
    c = PALETTE[mode]
    return _mix(c["child"], c["error"], 0.40 if is_dark(mode) else 0.28)


def create_alarm_plot_theme(mode: str) -> int:
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvPlotCol_PlotBg, (*alarm_plot_bg(mode), 255), category=dpg.mvThemeCat_Plots)
    return theme                      # Reihenfolge in der Auswahl "Darstellung"


def is_dark(mode: str) -> bool:
    r, g, b = PALETTE[mode]["window"]
    return 0.299 * r + 0.587 * g + 0.114 * b < 128


def color(mode: str, role: str):
    return PALETTE[mode][role]


def series_color(mode: str, index: int):
    colors = PALETTE[mode]["series"]
    return colors[index % len(colors)]


def _core(name, col):
    target = getattr(dpg, name, None)
    if target is not None:
        dpg.add_theme_color(target, (*col, 255), category=dpg.mvThemeCat_Core)


def _plot(name, col):
    target = getattr(dpg, name, None)
    if target is not None:
        dpg.add_theme_color(target, (*col, 255), category=dpg.mvThemeCat_Plots)


def create_global_theme(mode: str):
    c = PALETTE[mode]
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvAll):
            for name, role in [
                ("mvThemeCol_WindowBg", "window"), ("mvThemeCol_ChildBg", "child"),
                ("mvThemeCol_PopupBg", "popup"), ("mvThemeCol_Border", "border"),
                ("mvThemeCol_FrameBg", "frame"), ("mvThemeCol_FrameBgHovered", "frame_hover"),
                ("mvThemeCol_FrameBgActive", "frame_active"), ("mvThemeCol_TitleBg", "title"),
                ("mvThemeCol_TitleBgActive", "title_active"), ("mvThemeCol_MenuBarBg", "menu"),
                ("mvThemeCol_Button", "button"), ("mvThemeCol_ButtonHovered", "button_hover"),
                ("mvThemeCol_ButtonActive", "button_active"), ("mvThemeCol_Header", "header"),
                ("mvThemeCol_HeaderHovered", "header_hover"), ("mvThemeCol_HeaderActive", "header_active"),
                ("mvThemeCol_Tab", "tab"), ("mvThemeCol_TabHovered", "tab_hover"),
                ("mvThemeCol_TabActive", "tab_active"), ("mvThemeCol_Text", "text"),
                ("mvThemeCol_TextDisabled", "text_dim"), ("mvThemeCol_CheckMark", "check"),
                ("mvThemeCol_TableHeaderBg", "table_header"), ("mvThemeCol_TableRowBgAlt", "row_alt"),
                ("mvThemeCol_ScrollbarBg", "window"), ("mvThemeCol_ScrollbarGrab", "frame_active"),
                ("mvThemeCol_Separator", "border"),
            ]:
                _core(name, c[role])
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 3, category=dpg.mvThemeCat_Core)
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 4, category=dpg.mvThemeCat_Core)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8, 5, category=dpg.mvThemeCat_Core)
            _plot("mvPlotCol_FrameBg", c["plot_frame"])
            _plot("mvPlotCol_PlotBg", c["plot_bg"])
            _plot("mvPlotCol_PlotBorder", c["border"])
            _plot("mvPlotCol_LegendBg", c["popup"])
            _plot("mvPlotCol_LegendBorder", c["border"])
            _plot("mvPlotCol_LegendText", c["text"])
            _plot("mvPlotCol_TitleText", c["text"])
            _plot("mvPlotCol_InlayText", c["text"])
            _plot("mvPlotCol_AxisText", c["text"])
            _plot("mvPlotCol_AxisGrid", c["grid"])
            _plot("mvPlotCol_XAxis", c["text"])
            _plot("mvPlotCol_YAxis", c["text"])
            _plot("mvPlotCol_XAxisGrid", c["grid"])
            _plot("mvPlotCol_YAxisGrid", c["grid"])
    return theme


def create_series_theme(col):
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvLineSeries):
            dpg.add_theme_color(dpg.mvPlotCol_Line, (*col, 255), category=dpg.mvThemeCat_Plots)
        if hasattr(dpg, "mvBarSeries"):                       # Balken (Harmonische der Fourier-Analyse)
            with dpg.theme_component(dpg.mvBarSeries):
                dpg.add_theme_color(dpg.mvPlotCol_Line, (*col, 255), category=dpg.mvThemeCat_Plots)
                dpg.add_theme_color(dpg.mvPlotCol_Fill, (*col, 200), category=dpg.mvThemeCat_Plots)
    return theme


def create_splitter_theme(mode: str):
    """Trenner: schmale Fläche in Rahmenfarbe, beim Überfahren in Akzentfarbe."""
    c = PALETTE[mode]
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (*c["border"], 255), category=dpg.mvThemeCat_Core)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (*c["heading"], 255), category=dpg.mvThemeCat_Core)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (*c["heading"], 255), category=dpg.mvThemeCat_Core)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 0, category=dpg.mvThemeCat_Core)
    return theme
