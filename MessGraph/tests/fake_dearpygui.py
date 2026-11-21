"""Nachbildung der genutzten Dear-PyGui-Schnittstelle für Tests ohne Bildschirm.

Nur die Parameter aus ALLOWED sind erlaubt, damit Tippfehler auffallen. Die Liste
stammt aus der Dear-PyGui-Dokumentation, ist aber selbst kein Ersatz für das echte Paket.
"""
import contextlib
import inspect
import itertools
import sys
import types

COMMON = {"label", "tag", "parent", "show", "width", "height", "callback", "user_data"}
ALLOWED = {
    "window": COMMON | {"modal", "no_collapse", "pos", "no_title_bar", "no_resize", "autosize", "no_scrollbar",
                        "no_focus_on_appearing", "on_close", "no_move"},
    "add_color_button": COMMON | {"default_value", "width", "height", "no_border"}, "tab_bar": COMMON, "tab": COMMON, "group": COMMON | {"horizontal"},
    "child_window": COMMON | {"border"}, "handler_registry": COMMON, "menu_bar": COMMON, "menu": COMMON,
    "drag_payload": {"parent", "drag_data", "payload_type"},
    "file_dialog": COMMON | {"directory_selector", "modal", "cancel_callback", "file_count", "default_path"},
    "collapsing_header": COMMON | {"default_open"}, "tree_node": COMMON | {"default_open"},
    "add_tree_node": COMMON | {"default_open"}, "tooltip": {"parent"}, "popup": {"parent", "tag", "mousebutton", "modal", "min_size", "no_move"},
    "subplots": COMMON | {"rows", "columns", "no_title", "link_all_x"},
    "plot": COMMON | {"no_menus", "payload_type", "drop_callback"},
    "add_plot": COMMON | {"no_menus", "payload_type", "drop_callback", "use_24hour_clock", "use_ISO8601", "use_local_time"},
    "add_subplots": COMMON | {"no_title", "link_all_x", "column_ratios", "row_ratios"}, "add_drawlist": COMMON, "table": COMMON | {"header_row", "row_background", "resizable", "borders_innerH",
                                       "borders_innerV", "borders_outerH", "borders_outerV", "policy", "scrollY",
                                       "scrollX", "freeze_rows", "freeze_columns"},
    "table_row": COMMON, "font_registry": set(), "font": set(), "theme": set(), "theme_component": set(),
    "add_text": COMMON | {"wrap", "bullet", "color"}, "add_button": COMMON | {"small", "pos"},
    "add_checkbox": COMMON | {"default_value"}, "add_combo": COMMON | {"items", "default_value"},
    "add_listbox": COMMON | {"items", "default_value", "num_items"},
    "add_input_text": COMMON | {"hint", "on_enter", "default_value", "multiline", "height", "enabled", "readonly"}, "add_plot_annotation": COMMON | {"default_value", "offset", "color", "clamped"}, "add_separator": COMMON, "add_spacer": COMMON,
    "add_child_window": COMMON | {"border", "payload_type", "drop_callback", "horizontal_scrollbar"},
    "add_window": COMMON | {"popup", "autosize", "pos"}, "add_group": COMMON | {"horizontal"},
    "add_slider_int": COMMON | {"default_value", "min_value", "max_value", "format"},
    "add_progress_bar": COMMON | {"default_value", "overlay"},
    "add_radio_button": COMMON | {"items", "default_value", "horizontal"}, "add_input_int": COMMON | {"step", "default_value", "min_value", "min_clamped", "max_value", "max_clamped"},
    "add_input_float": COMMON | {"step", "format", "default_value"},
    "add_menu_item": COMMON | {"check", "default_value", "enabled"}, "add_texture_registry": COMMON,
    "add_static_texture": COMMON, "add_image": COMMON, "add_viewport_drawlist": COMMON | {"front"}, "add_selectable": COMMON | {"span_columns", "default_value"},
    "add_color_edit": COMMON | {"default_value", "no_inputs", "no_alpha"},
    "add_mouse_click_handler": COMMON | {"button"}, "add_mouse_wheel_handler": COMMON, "add_mouse_release_handler": COMMON | {"button"}, "add_mouse_double_click_handler": COMMON | {"button"}, "add_file_extension": {"color"},
    "add_plot_legend": COMMON | {"location"}, "add_plot_axis": COMMON | {"payload_type", "drop_callback", "scale", "opposite", "log_scale"},
    "add_line_series": COMMON | {"show"}, "add_bar_series": COMMON | {"show", "weight", "horizontal"}, "add_inf_line_series": COMMON | {"show", "horizontal"}, "add_drag_line": COMMON | {"color", "default_value", "vertical", "show_label", "thickness"},
    "add_table_column": COMMON | {"init_width_or_weight"}, "add_font_range_hint": set(), "add_font_range": set(),
    "add_theme_color": {"category"}, "add_theme_style": {"category"},
}


def install():
    items = {}
    ids = itertools.count(1000)
    stack = []
    state = types.SimpleNamespace(items=items, callbacks=[], fits=[], viewport_h=900, theme=None, primary=None,
                                  axis_limits={}, fixed_axes=set(), stack=stack)

    def new(kind, args, kw):
        allowed = ALLOWED[kind]
        bad = set(kw) - allowed
        assert not bad, f"{kind}: unbekannte Parameter {bad}"
        tag = kw.get("tag") or next(ids)
        assert not (kw.get("tag") and tag in items), f"{kind}: Alias already exists: {tag}"   # wie Dear PyGui
        parent = kw.get("parent") or (stack[-1] if stack else None)
        if parent is not None:
            assert parent in items, f"{kind}: Eltern-Element {parent} fehlt"
        items[tag] = dict(kw, kind=kind, args=args, id=tag, parent=parent, children=[], value=kw.get("default_value"))
        if parent is not None:
            items[parent]["children"].append(tag)
        state.last = tag
        return tag

    mod = types.ModuleType("dearpygui.dearpygui")
    for name in ALLOWED:
        if name.startswith("add_"):
            def adder(*a, _n=name, **kw):
                tag = new(_n, a, kw)
                if _n == "add_input_text":
                    items[tag]["value"] = kw.get("default_value", "")
                if _n == "add_text":
                    items[tag]["value"] = a[0] if a else ""
                if _n in ("add_line_series", "add_bar_series"):
                    assert len(a[0]) == len(a[1]), "Serie: X/Y-Länge unterschiedlich"
                    items[tag]["value"] = [a[0], a[1]]
                return tag
            setattr(mod, name, adder)
        else:
            def ctx(*a, _n=name, **kw):
                @contextlib.contextmanager
                def cm():
                    if _n == "popup" and a:                      # popup(auslösendes_Element, ...)
                        kw.setdefault("parent", a[0])
                    tag = new(_n, a, kw)
                    stack.append(tag)
                    try:
                        yield tag
                    finally:
                        stack.pop()
                return cm()
            setattr(mod, name, ctx)

    def delete_item(tag, children_only=False):
        def drop(t):
            for c in list(items[t]["children"]):
                if c in items and items[c]["parent"] is not None:
                    drop(c)
            del items[t]
        def drop_child(c):
            if items[c]["kind"] == "popup":                       # Popups sind in Dear PyGui eigene Fenster:
                items[c]["parent"] = None                          # sie überleben das Löschen des Auslösers
            else:
                drop(c)
        def walk(t):
            for c in list(items[t]["children"]):
                if items[c]["kind"] == "popup":
                    drop_child(c)
                else:
                    walk(c)
        walk(tag)
        for c in list(items[tag]["children"]):
            if c in items and items[c]["parent"] is not None:
                drop(c)
        items[tag]["children"] = []
        if not children_only:
            p = items[tag]["parent"]
            if p:
                items[p]["children"].remove(tag)
            del items[tag]

    def get_value(tag):
        return items[tag]["value"]

    def set_value(tag, value):
        items[tag]["value"] = value

    def configure_item(tag, **kw):
        assert set(kw) <= ALLOWED[items[tag]["kind"]] | {"items", "color", "pos", "enabled"}, (items[tag]["kind"], kw)
        items[tag].update(kw)

    def show_item(tag):
        items[tag]["show"] = True

    def does_item_exist(tag):
        return tag in items

    def bind_item_theme(item, theme):
        assert item in items and (theme in items or theme == 0)   # 0 hebt die Bindung auf (wie Dear PyGui)
        items[item]["bound"] = theme

    def bind_theme(theme):
        state.theme = theme

    def bind_font(font):
        pass

    def run_callbacks(jobs):
        pass

    def fit_axis_data(axis):
        assert axis in items
        state.fits.append(axis)

    mod.delete_item = delete_item
    mod.get_value = get_value
    mod.set_value = set_value
    mod.configure_item = configure_item
    mod.show_item = show_item
    mod.does_item_exist = does_item_exist
    state.frames = []

    def output_frame_buffer(file=""):
        state.frames.append(file)
        with open(file, "wb") as fh:
            fh.write(b"\x89PNG fake")

    def load_image(path):
        import os
        if not os.path.exists(path):
            return None
        w, h = 4, 2                      # 4x2 Pixel RGBA, Werte 0..1 wie bei Dear PyGui
        return w, h, 4, [0.5, 0.25, 1.0, 1.0] * (w * h)

    mod.output_frame_buffer = output_frame_buffer
    mod.load_image = load_image
    state.rects = {}   # Item -> (links oben, Größe); sonst feste Werte
    mod.get_y_scroll = lambda tag: state.scroll.get(tag, 0.0)
    state.scroll = {}
    mod.get_item_rect_min = lambda tag: list(state.rects.get(tag, ([300.0, 120.0], None))[0])
    def get_item_rect_max(tag):
        if tag in state.rects and state.rects[tag][0] is not None and state.rects[tag][1] is not None:
            (x, y), (w, h) = state.rects[tag]
            return [x + w, y + h]
        return [420.0, 150.0]

    mod.get_item_rect_max = get_item_rect_max
    mod.get_item_rect_size = lambda tag: list(state.rects.get(tag, (None, [120.0, 30.0]))[1])
    mod.set_item_pos = lambda tag, pos: items[tag].__setitem__("pos", list(pos))
    mod.get_item_pos = lambda tag: list(items[tag].get("pos") or [0, 0])
    def get_item_children(tag, slot=None):
        """Wie Dear PyGui: Tabellenspalten liegen in Slot 0, Zeilen und übrige Elemente in Slot 1."""
        children = list(items[tag].get("children", []))
        if slot == 0:
            return [c for c in children if items[c]["kind"] == "add_table_column"]
        if slot == 1:
            return [c for c in children if items[c]["kind"] != "add_table_column"]
        return children
    mod.get_item_children = get_item_children
    mod.get_item_configuration = lambda tag: {k: v for k, v in items[tag].items()
                                              if k not in ("children", "parent", "kind", "id", "args")}
    state.drawn = []
    mod.draw_circle = lambda center, radius, **kw: state.drawn.append(("circle", tuple(center), kw.get("parent")))
    mod.draw_text = lambda pos, text, **kw: state.drawn.append(("text", text, kw.get("parent")))
    mod.draw_rectangle = lambda a, b, **kw: state.drawn.append(("rect", tuple(a), kw.get("parent")))
    mod.bind_item_font = lambda item, font: items[item].__setitem__("font", font)
    mod.is_item_shown = lambda tag: bool(items[tag].get("show", True))
    mod.bind_item_theme = bind_item_theme
    mod.bind_theme = bind_theme
    mod.bind_font = bind_font
    mod.fit_axis_data = fit_axis_data
    mod.run_callbacks = run_callbacks
    mod.last_item = lambda: state.last
    mod.get_axis_limits = lambda axis: state.axis_limits.get(axis, [0.0, 1.0])

    def set_axis_limits(axis, lo, hi):
        assert axis in items
        state.axis_limits[axis] = [lo, hi]
        state.fixed_axes.add(axis)

    def set_axis_limits_auto(axis):
        assert axis in items
        state.fixed_axes.discard(axis)
    mod.set_axis_limits = set_axis_limits
    mod.set_axis_limits_auto = set_axis_limits_auto
    mod.get_viewport_client_height = lambda: state.viewport_h
    mod.get_viewport_client_width = lambda: 1500
    state.hovered = None
    state.mouse = [0.0, 0.0]
    mod.is_item_hovered = lambda tag: tag == state.hovered
    state.plot_mouse = [0.0, 0.0]
    state.left_down = False
    mod.is_mouse_button_down = lambda button: state.left_down
    mod.get_plot_mouse_pos = lambda: list(state.plot_mouse)
    state.active = None
    mod.is_item_active = lambda tag: tag == state.active
    mod.get_mouse_pos = lambda local=True: list(state.mouse)
    def create_context():                                         # neuer Kontext: feste Tags wieder frei
        for tag in [k for k in items if isinstance(k, str)]:
            items.pop(tag, None)
        stack.clear()
    mod.create_context = create_context
    mod.setup_dearpygui = mod.show_viewport = mod.destroy_context = lambda: None
    mod.configure_app = lambda **kw: None
    mod.create_viewport = lambda **kw: None
    mod.set_primary_window = lambda tag, value: setattr(state, "primary", tag)
    mod.is_dearpygui_running = lambda: False
    mod.get_callback_queue = lambda: []
    mod.render_dearpygui_frame = lambda: None
    mod.clipboard = []
    mod.hovered = set()   # Items, über denen die Maus steht (für is_item_hovered)
    mod.highlighted = {}
    mod.highlight_table_row = lambda table, row, color: mod.highlighted.__setitem__((table, row), color)
    mod.unhighlight_table_row = lambda table, row: mod.highlighted.pop((table, row), None)
    mod.set_clipboard_text = mod.clipboard.append
    for const in ["mvAll", "mvLineSeries", "mvBarSeries", "mvInfLineSeries", "mvPlotCol_Fill", "mvXAxis", "mvYAxis", "mvThemeCat_Core", "mvThemeCat_Plots",
                  "mvPlotCol_Line", "mvPlotCol_PlotBg", "mvThemeCol_WindowBg", "mvThemeCol_Text",
                  "mvStyleVar_FrameRounding", "mvStyleVar_FramePadding", "mvStyleVar_ChildRounding", "mvStyleVar_ItemSpacing",
                  "mvFontRangeHint_Default", "mvTable_SizingStretchProp", "mvMouseButton_Right", "mvMouseButton_Left", "mvPlotScale_Time", "mvPlotScale_Log10", "mvButton",
                  "mvThemeCol_Button", "mvThemeCol_ButtonHovered", "mvThemeCol_ButtonActive",
                  "mvFontRangeHint_Thai", "mvYAxis2", "mvTable_SizingFixedFit", "mvThemeCol_Border",
                  "mvStyleVar_WindowPadding", "mvStyleVar_WindowMinSize", "mvStyleVar_WindowBorderSize",
                  "mvPlot_Location_NorthWest", "mvPlot_Location_North", "mvPlot_Location_NorthEast",
                  "mvPlot_Location_SouthWest", "mvPlot_Location_South", "mvPlot_Location_SouthEast"]:
        setattr(mod, const, const)

    pkg = types.ModuleType("dearpygui")
    pkg.dearpygui = mod
    sys.modules["dearpygui"] = pkg
    sys.modules["dearpygui.dearpygui"] = mod
    return state


def assert_callback_arity(fn):
    """Dear PyGui ruft Callbacks mit bis zu 3 Argumenten; run_callbacks kürzt passend."""
    return len(inspect.signature(fn).parameters) <= 3
