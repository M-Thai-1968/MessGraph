"""Help in English. Labels are quoted as shown on the English interface.

Elements: ("h", heading), ("p", paragraph), ("b", bullet), ("img", image id, caption).
Only characters up to U+00FF (interface font and PDF encoding).
"""

TITLE = "MessGraph - Manual"
SUBTITLE = "Display and measure data from MF4, MDF, BLF, CSV, ASCII and Parquet files"

CHAPTERS = [
    ("Overview", [
        ("p", "MessGraph opens measurement files in MF4, MDF, BLF, CSV, ASCII and Parquet format, detects the time axis and data "
              "columns by itself and shows the selected signals in one or more graphs. Two vertical markers measure the "
              "signals: values, distances and drift appear in the value display."),
        ("p", "The language of the interface and of this manual is switched in the menu bar: \"Language\" at the "
              "right edge. The included illustrations show the German interface."),
        ("img", "uebersicht", "Figure 1: main window"),
        ("m", "1", "Menu bar: File, Graph options, Limiter, Auto and Help on the left; Language at the right edge"),
        ("m", "2", "File list: a tick shows the signal"),
        ("m", "3", "Toolbar in two rows: file, matrix, show all, delete all plots; below markers, axes, regression lines, compare files, appearance"),
        ("m", "4", "Graphs, here stacked"),
        ("m", "5", "Splitter: drag to change the width of the file list"),
        ("m", "6", "Status line: result of the last action"),
        ("h", "Areas of the main window"),
        ("b", "Menu bar: \"File\" on the left (open and save projects, open files, save and load views) and \"Graph "
              "options\" (limits, calculations, kind of drift regression), \"Limiter\" (reduce data per file to the limits of guide signals), \"Auto\" (evaluate a folder cyclically), then, a little further apart, \"Help\" "
              "(manual, PDF, screenshots); the language switch sits at the right edge. Below the menu bar there is "
              "only the \"Graph\" tab - the manual opens in a window of its own."),
        ("b", "File list on the left: loaded files with their signals. A tick shows the signal."),
        ("b", "Toolbar: two compact rows, groups separated by a thin bar. First row - data and layout: File (for all "
              "graphs) | Matrix with Apply, Rows..., Propose... | Show all, Delete all plots. Second row - display and "
              "measuring: Markers, Markers synchronous | Couple X axes, Date/time axis, Regression lines | Compare "
              "files..., Appearance.... The file selection gets narrower when space is short (narrow window, wide "
              "file list)."),
        ("b", "Appearance... (right end of the second toolbar row, drops down): colour scheme of the interface and the graphs. Besides Dark and Light "
              "there are Solar dark and Solar light (teal or cream, Solarized colours), Nord (cool blue-grey, pastel "
              "lines), High contrast (black with strong colours, for projectors and bright surroundings), Paper "
              "(cream white with ink colours) and Colour-blind safe (Okabe-Ito colours, distinguishable with red-green "
              "deficiency). Line and marker colours are matched to each scheme's plot background (contrast at least "
              "3:1, distinguishable from each other). The scheme is remembered and belongs to the view; printing, "
              "export and report always use the light appearance, custom signal colours stay."),
        ("b", "Font: the slider under Appearance... sets the font size of the graphs (title, axes, legend, "
              "marker labels) and the value display, 10 to 32 px. The size is kept."),
        ("b", "Graphs: one or more charts, stacked or arranged as an n*m matrix."),
        ("b", "Value display: measurements at the markers, visible once \"Markers\" is ticked."),
        ("b", "Status line at the bottom: result of the last action, hints and error messages."),
        ("p", "The splitters between file list and graphs and between graphs and value display can be dragged "
              "with the mouse (chapter Resizing the window areas)."),
        ("h", "Quick start"),
        ("b", "Click \"Open files...\", tick files, click \"Open\"."),
        ("b", "Tick signals on the left: each one appears in its own graph."),
        ("b", "Right-click a graph: add more signals, change colours and names, print, export, report."),
        ("b", "Tick \"Markers\" and drag the vertical markers: the measurements appear below."),
        ("b", "\"File > Save view...\": keep everything for next time."),
    ]),
    ("Installation and start", [
        ("h", "Requirements"),
        ("p", "Python 3.10 or newer on Windows or Linux. Required packages are listed in requirements.txt: "
              "dearpygui, numpy, pandas, pyarrow (Parquet), asammdf (MF4) and canmatrix (DBC)."),
        ("h", "Windows"),
        ("p", "Double-click start_windows.bat. The first start creates a Python environment in the folder .venv "
              "and installs the packages. After that the program starts directly."),
        ("h", "Linux"),
        ("p", "Run sh start_linux.sh in a terminal. The first start sets up the environment the same way "
              "(requires python3-venv)."),
        ("h", "Computers without Python (portable version)"),
        ("p", "If the program folder contains a bundled Python in runtime\\python, the start files use it "
              "automatically; no installed Python is needed. Python 3.12.0 is bundled. This version is built once on a "
              "computer with internet access: on Windows tools\\build_portable_windows.bat (creates "
              "dist\\MessGraph_portable_windows.zip), on Linux sh tools/build_portable_linux.sh (creates "
              "dist/MessGraph_portable_linux_x86_64.tar.gz or _aarch64). The script downloads Python 3.12.0 "
              "(python-build-standalone from GitHub, SHA-256 checksum verified; on Windows python.org as fallback), "
              "checks the version, installs all packages and packs the result. Unpack it on the target computer and "
              "start as usual."),
        ("p", "A .venv alone is not enough, because it always points to an installed Python. The package only "
              "works on the operating system it was built on."),
        ("h", "Start with files"),
        ("p", "python main.py measurement1.mf4 measurement2.csv opens the files right away."),
        ("h", "Example data"),
        ("p", "The folder demo_data contains three CSV examples. python tools/make_demo_data.py recreates them, plus "
              "demo.mf4 and demo.parquet if asammdf and pyarrow are installed. The examples are also used to create "
              "the screenshots for this manual."),
    ]),
    ("Opening files", [
        ("p", "\"Open files...\" shows the file browser."),
        ("img", "browser", "Figure 2: file browser"),
        ("m", "1", "Up, Home and path entry"),
        ("m", "2", "File type, name filter, All in folder, None"),
        ("m", "3", "Folder: click to open"),
        ("m", "4", "Files with tick box, size and date"),
        ("m", "5", "Number of selected files"),
        ("m", "6", "Open loads all selected files"),
        ("h", "Navigating"),
        ("b", "Click a [Folder] (folder) entry to open it."),
        ("b", "\"Up\" goes to the parent folder, \"Home\" to the home folder."),
        ("b", "On Windows the drop-down next to \"Home\" selects the drive."),
        ("b", "A path can be typed at the top and opened with Enter. A typed file path selects the file at once."),
        ("h", "Filtering"),
        ("b", "\"File type\": measurement data (mf4, blf, csv, parquet), a single format or all files. "
              "Upper and lower case of the extension do not matter (.MF4 = .mf4)."),
        ("b", "\"Name contains\": search words; several words must all occur."),
        ("h", "Selecting several files"),
        ("p", "Every file has a tick box. \"All in folder\" ticks all files shown, \"None\" clears them. The "
              "selection is kept when changing folders, so files from several folders can be opened together. "
              "The count at the bottom also shows how many come from other folders."),
        ("p", "\"Open\" loads all selected files in the background. The folder is remembered for next time. "
              "A file that is already open is not loaded twice."),
        ("h", "Loaded files"),
        ("img", "dateiliste", "Figure 3: file list with two loaded files"),
        ("m", "1", "Open files and deselect all"),
        ("m", "2", "Target graph for the next ticked signal"),
        ("m", "3", "Signal search across all files"),
        ("m", "4", "File entry, collapsible, with Close"),
        ("m", "5", "Detection: shown while the mouse is on \"Detection\""),
        ("m", "6", "Hint, here a text column without numbers"),
        ("m", "7", "Signal tick box"),
        ("p", "Each file appears on the left as a collapsible entry with its signals. Hovering \"Detection\" "
              "(detection) shows what was detected: separator, header line, time axis, start time. Hints follow, "
              "for example about text columns. \"Close\" removes the file and its signals from all "
              "graphs. MF4 files also have the button \"Databases...\"."),
        ("h", "One signal across all files"),
        ("p", "If several files are loaded and the signal search finds a signal in at least two files (e.g. \"Temp\" "
              "in several test runs), the bar \"Matches in several files\" appears below the search field. The "
              "drop-down lists all such signals; below it you see in how many files the signal occurs and how many "
              "of them are shown."),
        ("img", "allefiles", "Figure 4: signal Temperatur from all files in one shared graph"),
        ("m", "1", "Search text"),
        ("m", "2", "Signals that occur in several files"),
        ("m", "3", "Shared graph, separate graphs, remove"),
        ("m", "4", "In how many files present and shown"),
        ("b", "\"Shared graph\": the signal of all files in one graph, ideal for direct comparison. The target is the "
              "selected target graph; with \"Automatic\" a new graph (with a matrix the first empty one). The "
              "legend names the file of each curve."),
        ("b", "\"Separate graphs\": one graph per file with the signal (with a matrix the empty or least used "
              "graphs). With \"Couple X axes\" all of them zoom together."),
        ("b", "\"Remove\": removes the signal of all files from all graphs."),
        ("p", "The exact signal name is compared. Afterwards the curves can be measured, compared, printed and put "
              "into the report as usual."),
        ("h", "Loading progress"),
        ("p", "While MF4 and Parquet files load, a progress display appears above the status line: a bar with "
              "percent, the file and the current step (e.g. \"Reading Parquet: 1,200,000 of 3,000,000 rows\", "
              "\"Detecting columns\", \"Downsampling\") and the time elapsed. With several files the bar shows the "
              "overall progress and \"2 of 5 done\"."),
        ("b", "Parquet is read in blocks, so the bar grows evenly."),
        ("b", "MF4: opening the file, reading a channel when it is ticked and DBC decoding are single asammdf steps "
              "whose duration is not known in advance. Dots then run behind the percentage."),
        ("b", "Loading a view: every file and every displayed signal is one part."),
        ("b", "\"Cancel\" stops all running loads at the next intermediate point. Files already loaded stay, "
              "cancelled signals are unticked again. Inside an asammdf step the cancel takes effect as soon as that "
              "step has finished."),
    ]),
    ("Data detection", [
        ("h", "CSV"),
        ("p", "The structure is detected without any settings:"),
        ("b", "encoding UTF-8, UTF-16 or Windows-1252;"),
        ("b", "separator semicolon, comma, tab, vertical bar or space;"),
        ("b", "decimal mark point or comma;"),
        ("b", "preamble: lines before the table (test bench, date ...) are skipped;"),
        ("b", "header: the last text-only line directly before the data; without one the columns are called "
              "Spalte_1, Spalte_2 and so on;"),
        ("b", "units from a separate line below the header or from the name: Speed [km/h], Pressure (bar)."),
        ("h", "ASCII files with variable preamble (asc, txt, dat ...)"),
        ("p", "Besides CSV, any ASCII raw data can be opened: extensions asc, txt, dat, tsv, log and prn. Such files "
              "often start with a preamble of varying length (date, version, comments). The file is read, then the "
              "signal header is detected automatically or set by the user; after that the data are handled like any "
              "other file (time axis, signals, graphs)."),
        ("img", "ascii", "Figure 5: ASCII import with the header in line 7, continued in line 8"),
        ("m", "1", "Start of the file with line numbers; K = header, E = unit line, D = first data line"),
        ("m", "2", "Header as line number (0 = automatic, -1 = none)"),
        ("m", "3", "Separator and decimal separator (automatic or fixed)"),
        ("m", "4", "Result: detected lines, number of columns and signal names"),
        ("m", "5", "Apply and read, Automatic, Close"),
        ("m", "6", "ASCII import button in the file entry"),
        ("b", "Additional information of the form <{...}>, e.g. <{Continue}>, is ignored. If a line starts with such a "
              "marker, it continues the previous line: a header that the logger wrapped after 1000 characters "
              "(line 7 ends with DUT_TS_, line 8 starts with <{Continue}>12,...) yields the signal name DUT_TS_12 "
              "again. This way header and data columns match logically."),
        ("b", "Values such as x, - or empty count as missing; columns without any numbers (text, only x) are reported "
              "and not offered. Time stamps such as 2026-11-10_16-00-51 are recognised as date/time."),
        ("b", "\"ASCII import...\" in the file entry shows the detection. There the header can be given as a line "
              "number as in an editor (e.g. 7, even if it continues in line 8), plus unit line, separator and "
              "decimal separator. The result appears immediately; \"Apply and read\" reads the file again. Signals "
              "already shown stay in their graphs."),
        ("b", "If a file is not recognised, the dialog opens by itself."),
        ("b", "\"Use as template ...\": further ASCII files (not CSV) are read with these settings first; if they do "
              "not fit, the structure is detected automatically."),
        ("b", "User settings are saved with the view and in definition files."),
        ("b", "Vector ASC bus recordings (CAN traces with messages instead of values) are not value tables; MessGraph "
              "points this out. They can be saved as BLF and opened with DBC/ARXML."),
        ("p", "Example: demo_data/demo_pruefstand.asc."),
        ("h", "Parquet"),
        ("p", "All numeric columns are offered; date columns are used as time axis."),
        ("h", "X axis for CSV and Parquet"),
        ("p", "Searched in this order:"),
        ("b", "a rising date or time column (text or date type), also split into date and time of day;"),
        ("b", "a rising numeric column with numeric timestamps (Unix, LabVIEW);"),
        ("b", "a rising numeric column named like time, zeit or timestamp;"),
        ("b", "the first column if it rises strictly; it also stays available as a signal;"),
        ("b", "otherwise the row number."),
        ("h", "Special data"),
        ("b", "Columns without a single numeric value (text, empty, placeholders only) are not offered; the hint "
              "names exactly these columns of the file. It is built when the list is shown: with an active signal "
              "search it names only matching names and disappears when none matches."),
        ("b", "A signal recorded only part of the time (otherwise placeholders such as x, -, n/a) is offered; the "
              "placeholders become gaps. Further date or time columns are listed in the detection details."),
        ("b", "MF4 with bus raw data: the hint names the frame channels present (e.g. CAN_DataFrame, LIN_Frame) and, "
              "after assigning databases, the number of decoded signals."),
        ("b", "Single invalid values become gaps."),
        ("b", "A time axis that does not rise is sorted; a hint says so."),
        ("h", "MF4"),
        ("p", "The channels are listed at once; the values are read when a channel is ticked (on demand), so even "
              "large files with thousands of channels open quickly; the search field above the list filters, at most "
              "400 matches per file are shown. If the file contains raw CAN frames, the databases dialog opens."),
        ("b", "Duplicate channel names (MF4 and MDF): every channel is read via group and index, never by name alone. "
              "Unique names stay unchanged; for equal names the list shows \"group / channel\" (e.g. "
              "IVT6_Msg_Result_I / IVT_Result_I; with bus logging the group is usually the message) or, for a group "
              "with only one data channel or without a group name, \"channel [g714]\"; if still duplicate, "
              "\"channel [g714:i3]\". Views and projects with the former names (channel (G714)) still find the "
              "channels; the search knows them too. The detection details give the number of renamed channels."),
        ("b", "Every signal keeps its own time axis (timestamps and values from the file, no resampling onto a common "
              "grid); the graph draws each signal with its own time."),
        ("b", "Value-to-text conversion (e.g. 0 = Idle, 1 = Charging): the graph shows the raw values as numbers; the "
              "value display adds the text, e.g. 1 (Charging), and the channel's tooltip lists the table."),
        ("b", "Not plottable and grey in the list: text channels (VLSD strings, byte arrays), channels with only one "
              "value (constant; the Value button shows it in the status line) and channels without values. They "
              "cannot be ticked; the detection details give their number."),
    ]),
    ("Time formats", [
        ("p", "The time column is detected automatically. Internally the X axis counts seconds from the first value. "
              "Timestamps with a date also provide the start time for the date/time axis."),
        ("h", "Timestamps as text"),
        ("b", "ISO and variants: 2026-10-01 23:00:51, 2026-10-01T23:00:51.250, 2026-10-01_23-00-51"),
        ("b", "German: 01.10.2026 23:00:51,5 and 01.10.26 23:00 (two-digit years from 2000)"),
        ("b", "With slashes: 13/10/2026 or 10/13/2026 08:00:00 AM"),
        ("b", "Without separators: 20261001_230051 or 20261001T230051.5"),
        ("b", "With month names, English or German: 01-Oct-2026 23:00:51, 1. Okt. 2026 um 23:00, "
              "Oct 1, 2026 11:00:51 PM, Thu Oct 1 23:00:51 2026"),
        ("h", "Day or month first?"),
        ("p", "For 03/04/2026 the program decides per column: a value above 12 settles the order, a dot always means "
              "day.month. Otherwise the reading wins in which time rises with the smallest steps; on a tie the day "
              "comes first."),
        ("h", "Times of day and durations without a date"),
        ("b", "If 00:00:00 follows 23:59:59, a new day is counted."),
        ("b", "Durations like 25:30:00, 0 days 00:00:01.5 or 1 d 02:00:00 are taken as seconds."),
        ("p", "Without a date there is no start time and therefore no date axis."),
        ("h", "Numeric timestamps"),
        ("p", "A rising numeric column counts as timestamps if its name is time-like or it is the first column and "
              "all values fall into the years 2000 to 2050: Unix time in s, ms, µs or ns, LabVIEW time (seconds "
              "since 1904). Unix time is shown in local time."),
        ("h", "Time zones"),
        ("p", "Zone markers in text (Z, UTC, +02:00) are ignored: the time appears as written in the file. Parquet "
              "timestamps with a time zone and the start time of MF4 files are shown in local time."),
    ]),
    ("Signals and graphs", [
        ("h", "Selecting signals"),
        ("p", "A tick in the file list shows the signal; removing the tick removes it from all graphs. The search "
              "field above the list filters by name; several words must all occur. At most 400 matches are listed "
              "per file. \"Deselect all\" empties all graphs."),
        ("b", "Same-named signals of all files (tick below the buttons, only with several open files): on - ticking a "
              "signal selects the signal of the same name in all open files at once, together in one graph (chosen "
              "target graph, otherwise a new one); unticking removes it from all files. Off - single selection per "
              "file. The setting is saved."),
        ("h", "Target graph (\"Target graph\")"),
        ("b", "\"Automatic\" without matrix: every ticked signal gets its own graph, stacked."),
        ("b", "\"Automatic\" with matrix: into the first graph with the fewest signals."),
        ("b", "\"Graph k\": the next ticked signal goes into graph k."),
        ("h", "Matrix n*m"),
        ("p", "Enter a layout such as 2*3 (2 rows, 3 columns) in the toolbar and click \"Apply\"; 2x3 "
              "or 2,3 work as well. Graphs are numbered row by row, 64 at most. An empty field stacks all graphs; "
              "if the height is not sufficient, a scroll bar appears."),
        ("img", "matrix", "Figure 6: 2*2 matrix with several signals per graph"),
        ("m", "1", "Matrix 2*2 entered and applied"),
        ("m", "2", "Custom graph name"),
        ("m", "3", "Two signals in one graph, temperature with a custom colour on the right axis"),
        ("m", "4", "Target graph shows number, position and name"),
        ("m", "5", "Right (secondary) Y axis with its own unit"),
        ("h", "Merging rows"),
        ("p", "In a matrix, the graph areas of individual rows can be merged freely. Example 4*3: rows 1 and 2 with 3 "
              "graphs each, row 3 with one graph across 2 columns and one across 1 column, row 4 with one graph "
              "across the full width."),
        ("img", "zeilen", "Figure 7: matrix 4*3 with merged areas"),
        ("m", "1", "Matrix field with row entries: 4*3: 3, 3, 2+1, 1"),
        ("m", "2", "Rows... button opens the dialog"),
        ("m", "3", "Row 3: graph across two columns and graph across one column"),
        ("m", "4", "Row 4: one graph across the full width"),
        ("m", "5", "Entry per row"),
        ("m", "6", "Preview of the layout"),
        ("m", "7", "Apply, All single graphs, Close"),
        ("p", "Per row: a number is the count of equally wide graphs (3 = three graphs, 1 = one graph across all "
              "columns, with 4 columns 2 = two graphs across two columns each); with + the widths are given in "
              "columns (2+1, 1+2, 1+1+2). The widths of a row add up to the number of columns."),
        ("b", "Directly in the matrix field: after the matrix a colon and the rows separated by commas, e.g. "
              "4*3: 3, 3, 2+1, 1. Missing rows stay single graphs."),
        ("b", "Or with \"Rows...\": one input per row, the preview shows the layout immediately, \"Apply\" applies "
              "it. \"All single graphs\" resets all rows."),
        ("p", "Graphs are numbered row by row; the target graph names the occupied columns, e.g. Graph 7 (Z3/S1-2). "
              "Signals are kept when the layout changes; if graphs disappear, their signals are distributed to the "
              "remaining ones. \"Couple X axes\" also works across rows. The layout is saved with view and project; "
              "\"Print all graphs\" follows it (a row stays on one page)."),
        ("h", "Proposing an arrangement"),
        ("p", "\"Propose...\" next to \"Rows...\" analyses the signals and proposes graphs and matrix. Test bench "
              "example: AC voltages, AC currents, AC powers and AC frequencies each in one graph and together in one "
              "row, below HVDC, LVDC etc., at the end the temperatures and the states."),
        ("img", "vorschlag", "Figure 8: proposing an arrangement for demo_pruefstand.asc"),
        ("m", "1", "Propose... button"),
        ("m", "2", "Which signals, max. curves per graph and columns"),
        ("m", "3", "Preview of the matrix with graph names and number of curves"),
        ("m", "4", "Rows and graphs with their signals"),
        ("m", "5", "Apply replaces the current arrangement"),
        ("b", "Signals: the displayed signals, the matches of the signal search or all signals of a file."),
        ("b", "Quantity from the unit (V, A, W, Hz, °C, bar, rpm ...) or from the name: V/U = voltage, I = current, "
              "P = power, T/TS/Temp = temperature, H = humidity, F = frequency for AC/grid/V2L, otherwise flow, "
              "Mode/Status = state. The system is the first part of the name (AC, HVDC, LVDC, Kl30, Chiller, DUT ...)."),
        ("b", "A graph combines the same quantity of the same system; set values (Set, Soll) stay with the actual values. "
              "One row per system; small systems share a row (e.g. HVDC and LVDC). Temperatures and states get rows of "
              "their own (can be switched off), signals without a recognisable quantity go to Other."),
        ("b", "More curves than allowed split the graph (DUT temperature 1/5 ...), more graphs than columns split the "
              "row. Rows with fewer graphs are filled using merged areas. With very many systems the proposal groups "
              "per quantity across all systems (at most 64 graphs)."),
        ("p", "\"Apply\" sets matrix, graph names and signals; afterwards everything can be changed as usual."),
        ("h", "Choosing the file for the graphs"),
        ("p", "At the start of the toolbar, the \"File\" selection lists all loaded files. It shows which file the graphs come "
              "from (\"Several files\" when they are mixed)."),
        ("b", "Choosing another file: all existing graphs show the signals of the same name from that file. Signals of "
              "the previous file are replaced, as is a signal that was plotted over several files in one graph (it "
              "stays once, from the chosen file)."),
        ("b", "Matrix, merged areas, graph names, colours, right axis, limits and notes stay. This way an arrangement "
              "(built by hand or from \"Proposal...\") can be viewed for several measurements one after another."),
        ("b", "Signals are matched by name (then label, then ignoring case). A signal missing in the chosen file is "
              "dropped and named in the status line. MF4 channels are loaded first, then all graphs switch at once."),
        ("b", "\"All files\" (first entry as soon as more than one file is loaded) switches back to all files. If "
              "the graphs were not filled differently since switching to one file, exactly the previous view returns, "
              "including custom colours and graphs that showed only one file. Otherwise each graph shows, for each "
              "of its signals, the signal of the same name from every loaded file (right axis, limits and target "
              "time go along, colours come from the colour scheme)."),
        ("b", "Everything else stays: ticking, dragging, target graph, search over all files and \"Compare files...\" "
              "work as before."),
        ("h", "Delete all plots"),
        ("p", "\"Delete all plots\" clears the plot area: all graphs and the layout (matrix, merged areas) are "
              "removed, as are graph names, colours, limits, notes and comments. The files stay loaded; the next "
              "signal starts as after opening."),
        ("p", "With no file loaded the plot area stays empty, even with a matrix set. The matrix is kept and appears "
              "with the next file; closing the last file empties the area again."),
        ("h", "Several signals in one graph"),
        ("p", "A graph shows any number of signals. More signals are added"),
        ("b", "by right-clicking the graph (chapter Graph context menu), where a signal can also be put on the "
              "right Y axis,"),
        ("b", "by drag and drop: grab a signal name on the left and drop it on a graph or one of its axes; dropped "
              "on the free area, the signal is placed automatically,"),
        ("b", "with target graph and tick."),
        ("p", "The same signal may appear in several graphs. Without a matrix an empty graph disappears; with a "
              "matrix it stays as an empty slot."),
        ("h", "Using a graph"),
        ("b", "Mouse wheel: zoom, also on a single axis."),
        ("b", "Drag with the left button: pan."),
        ("b", "Drag with the right button: zoom into a box."),
        ("b", "Click the right button (without dragging): context menu."),
        ("b", "\"Show all\": fit to the data. Double-clicking a graph opens it large in the detail window (see "
              "below); in the detail window a double-click fits."),
        ("b", "The Y axis is fitted with a margin as in the report: Y max = largest value * 1.1, Y min = smallest "
              "value * 0.9 (in general 10 % of the magnitude outwards, so negative values fit too; if a value is 0, "
              "10 % of the span applies). This happens when a graph is built, on \"Show all\" and on double-click in the detail window, "
              "per axis over all signals of the graph. Zooming works as usual afterwards."),
        ("b", "Click a legend entry: hide or show the signal."),
        ("h", "Graph in the detail window (double-click)"),
        ("p", "Double-clicking a graph with the left mouse button opens it in a separate, large window. It shows the "
              "same graph, not a copy: signals, colours, right axis, limits, markers, legend, name and comments belong "
              "to the graph and apply in the plot area and in the detail window at once."),
        ("b", "Zooming, panning and drawing a box only act in the detail window; the plot area stays as it is. "
              "Double-click or \"Show all\" in the detail window fits."),
        ("b", "Bar at the top: Show all, Markers, Markers synchronous, Print / export (the visible range of the detail "
              "window), Report and Close. With markers the detail window shows its own value display; the markers "
              "move along with the same graph in the plot area, limits apply in both value displays."),
        ("b", "Right-click opens the same context menu as in the plot area (name, add and remove signals, colours, "
              "right axis, legend, comments, print). Comments can be moved with the left mouse button, signals can be "
              "dragged here from the list."),
        ("b", "Double-clicking another graph shows that one in the detail window. If the graph disappears (all signals "
              "removed, file closed, Delete all plots), the window closes."),
        ("h", "Coupling X axes (\"Couple X axes\")"),
        ("p", "Zoom and pan act on all graphs together. Switching rebuilds the graphs and resets the zoom."),
        ("h", "Large data"),
        ("p", "For long signals MessGraph draws the minimum and maximum of each section of the visible range. Peaks "
              "stay visible and the display stays smooth. Measurements always use the complete data."),
    ]),
    ("Graph context menu", [
        ("p", "Right-clicking a graph (without dragging) opens its context menu. A click outside or \"Close\" "
              "closes it."),
        ("img", "kontextmenue", "Figure 9: context menu after right-clicking a graph"),
        ("m", "1", "Graph name"),
        ("m", "2", "Search a signal and click to add it"),
        ("m", "3", "Remove a signal from this graph"),
        ("m", "4", "Colour swatches: click to open the colour picker"),
        ("m", "5", "Restore default colours"),
        ("m", "6", "Right Y axis: a tick puts the signal on the secondary axis"),
        ("m", "7", "Print and export: graph, all graphs, report"),
        ("m", "8", "Legend position: top left, centre, right or bottom left, centre, right"),
        ("m", "9", "Comment at the clicked point: new text, change, move or delete existing comments"),
        ("m", "10", "Comment field in the graph"),
        ("h", "Graph name (\"Graph name\")"),
        ("p", "Enter a name and press Enter or \"Apply\". The name appears as the graph title, in the "
              "target graph list and in the value display. An empty field restores the default name \"Graph k\"."),
        ("h", "Comment fields"),
        ("p", "Right-click the desired point in the graph. Enter the text under \"Comment at the clicked point\" "
              "(several lines possible) and choose \"Insert comment\". The comment appears as a field in the graph, "
              "anchored at the clicked point (X value and value of the left Y axis); it moves along when zooming "
              "and panning."),
        ("b", "Moving with the mouse: hovering a comment highlights it. Hold the left mouse button and drag, the "
              "comment follows the mouse while the graph stays still. Releasing drops it."),
        ("b", "Existing comments are listed below: change the text and press Enter or \"Apply\" (applying an "
              "empty text deletes it), \"Move here\" moves it to the point of the right-click, \"Delete\" removes it."),
        ("b", "Any number of comments per graph. They are saved with view and project, kept when switching the file "
              "(\"File\" selection) and appear when printing, in the export (PDF, SVG) and in both reports as a box "
              "with a dot at the point."),
        ("b", "\"Delete all plots\" removes the comments as well (together with all graphs and the layout)."),
        ("h", "Adding signals (\"Add signal\")"),
        ("p", "The list holds all signals of all loaded files that the graph does not show yet. The search field "
              "filters; a click adds the signal."),
        ("h", "Removing signals (\"Remove signal\")"),
        ("b", "\"Remove: signal name\" removes the signal from this graph only."),
        ("b", "\"Remove all signals of this graph\" empties the graph."),
        ("h", "Signal colours (\"Signal colours\")"),
        ("p", "Each signal has a colour swatch. Clicking it opens the colour picker; the new colour applies "
              "immediately and only in this graph. Signals without a custom colour get the default colour of their "
              "position, matching the chosen colour scheme. \"Restore default colours\" removes all custom "
              "colours of the graph. Custom colours are saved with the view."),
        ("h", "Right Y axis (secondary)"),
        ("p", "Signals with very different value ranges, such as speed and temperature, can be read together in one "
              "graph: a tick under \"Right Y axis (secondary)\" puts the signal on a second Y axis at the right edge "
              "with its own scale and unit. Without the tick it returns to the left."),
        ("b", "The right axis only appears when at least one signal of the graph uses it."),
        ("b", "Legend and value display add \"(right)\" after the signal."),
        ("b", "Drag and drop onto the right axis places a signal there directly; a signal of the graph moves to the "
              "right this way."),
        ("b", "The assignment applies per graph and is saved with the view. The mouse wheel over the right axis "
              "zooms only its scale, over the plot area it zooms both Y axes around the mouse position; \"Show all\" "
              "fits both axes. If the installed Dear PyGui version does not zoom the right axis itself, MessGraph "
              "does it (10 % per notch). The same applies to panning with the left mouse button: over the plot area the "
              "right axis follows the left one, over the right axis it follows the mouse."),
    ]),
    ("Measuring with markers", [
        ("p", "The tick \"Markers\" shows two vertical markers M1 and M2 in every graph and the value display below. "
              "The markers only mark the points in time; the signal values are listed in the value display, so the "
              "graph stays clear."),
        ("img", "crosslines", "Figure 10: markers M1 and M2 with value display"),
        ("m", "1", "Tick Markers"),
        ("m", "2", "Marker M1: vertical line, drag with the mouse"),
        ("m", "3", "Marker M2 likewise"),
        ("m", "4", "Value display with values, delta and drift"),
        ("m", "5", "Splitter: drag to change the height of the value display"),
        ("m", "6", "Y min / Y max: limits per signal"),
        ("m", "7", "Limit line in the graph"),
        ("h", "Operation"),
        ("p", "Grab a marker at its line or at its label M1 or M2 and drag it sideways. New markers start at 1/3 and "
              "2/3 of the data range. With \"Markers synchronous\" the same marker moves in all graphs; without it "
              "each graph has its own positions."),
        ("b", "Zoom and unzoom (mouse wheel, drawing a box, double-click, \"Show all\"): afterwards the markers are "
              "placed at 10 % (M1) and 90 % (M2) of the new visible range; this is the new basis of the measurement. If "
              "several graphs change their view at the same time (e.g. coupled X axes), the graph under the mouse "
              "counts. When markers are switched on, markers outside the view are also placed at 10 % and 90 %."),
        ("b", "Panning the view leaves the markers in place. If a marker leaves the view while panning, both are "
              "also set to 10 % and 90 %."),
        ("h", "Values per signal"),
        ("b", "X1, X2: position of M1 and M2."),
        ("b", "Value 1, Value 2: signal value at M1 and M2, linearly interpolated between samples."),
        ("b", "Delta X = X2 - X1 and Delta Y = value 2 - value 1."),
        ("b", "Drift = Delta Y / Delta X: change per X unit, for example V/s."),
        ("b", "Drift (regression) and Forecast: see chapter Date/time axis, Forecast to the limit."),
        ("p", "A dash (-) means no value: the marker is outside the data or in a gap, or Delta X is 0. Units come "
              "from the file."),
        ("h", "Marker 3 with value table"),
        ("p", "The check box \"Marker 3\" (next to \"Markers synchronised\") shows a third, green marker M3 in "
              "every graph. It is independent of M1 and M2: it works without the markers switched on, does not change "
              "the value display and is not moved to 10 %/90 % when zooming (only when it leaves the view, it is "
              "placed in the middle of the view)."),
        ("b", "With the mouse at M3 (about 10 pixels horizontally) or while M3 is dragged, a tooltip shows a value "
              "table: at the top the position (X or date/time), below one row per signal of the graph with name, value "
              "at M3 (interpolated between samples, with unit and value-to-text text if any; signals on the right axis "
              "marked (right)), min, max, average and drift. While the table is visible the signal tooltip rests."),
        ("b", "Range for min, max, average and drift: selection next to \"Marker 3\" - \"Between M1 and M2\" "
              "(default; only with markers switched on, otherwise the entire signal is used and the table says so) "
              "or \"Entire signal\". Drift = delta Y / delta X: between M1 and M2 from the values at the markers "
              "(as in the value display), over the entire signal from the first to the last sample. The line below "
              "the table names the range used."),
        ("b", "With \"Markers synchronised\" the M3 of all graphs with the same axis type move along; the detail "
              "window always does. Position and check box are saved with view and project."),
        ("h", "Tooltip on the signal"),
        ("p", "With markers switched on, a tooltip shows the values of the signal whose curve the mouse tip points "
              "at: X1 value, X2 value, Y1 value, Y2 value, Delta X, Delta Y, average signal (mean between M1 and M2), "
              "drift (signal, between M1 and M2), drift (regression) and the regression line f(x) = m*x + b "
              "(selected drift regression method, x from the first sample)."),
        ("b", "With many curves in one graph the tooltip applies only to the curve closest to the mouse tip (at most "
              "about 10 pixels vertically); signals on the right Y axis are measured in its scale and marked (right)."),
        ("b", "Away from the curves, without markers, with the context menu open or while moving a comment the "
              "tooltip disappears. It also works in the detail window."),
        ("h", "Limits Y min and Y max"),
        ("p", "The Y min and Y max columns of the value display take a lower and an upper limit per signal (decimal "
              "point or comma). Limits that are set appear in the graph as a horizontal line in the signal's colour "
              "while the markers are switched on. An empty field means no limit. The limits are saved with the view."),
    ]),
    ("Date/time axis", [
        ("p", "The tick \"Date/time axis\" shows the X axis as date and time. It applies to every graph whose "
              "signals all have a start time: text or numeric timestamps, date columns in Parquet and MF4 files with "
              "a recorded start time."),
        ("img", "datumsachse", "Figure 11: date/time axis"),
        ("m", "1", "Tick Date/time axis"),
        ("m", "2", "X axis with date and time"),
        ("m", "3", "X1 and X2 as date with milliseconds"),
        ("m", "4", "Delta X as duration"),
        ("m", "5", "Limit Y min, here -20 A"),
        ("m", "6", "Forecast: when the drift reaches the limit"),
        ("m", "7", "Target time (here 1 h) with \"All\"; the forecast is earlier, so the row is red and the graph faint red"),
        ("b", "Signals from different files line up in time; in seconds every file starts at 0."),
        ("b", "The value display shows X1 and X2 as date with milliseconds and Delta X as a duration, for example "
              "1 d 02:03:04.5 (93784.5 s). Drift is per second."),
        ("b", "A graph containing a signal without start time stays in seconds. If both kinds exist, the X axes "
              "are not coupled and \"Markers synchronous\" only links graphs of the same kind."),
        ("b", "When switching, the markers restart at 1/3 and 2/3 of the data range."),
        ("h", "Forecast to the limit"),
        ("p", "The Drift (regression) column shows the slope m of the regression line f(x) = m*x + b, calculated by "
              "the kind chosen under Graph options > Drift regression (default: least squares) over all data of the "
              "signal. The Forecast column continues from the last measuring point: "
              "there x1 = 0 and f(x1) = b is the last y value. The end value y2 is Y max for a rising drift and Y min "
              "for a falling one. The result is x2 = (y2 - b) / m."),
        ("b", "Kinds of drift regression (Graph options > Drift regression), numbered: (1) linear regression (least "
              "squares of the vertical distances, default); (2) minimal squared distances (orthogonal: least squares "
              "of the perpendicular distances to the line, principal axis; since x and y count together the result "
              "depends on the units); (3) robust regression (Theil-Sen: median of the slopes of all point pairs, "
              "hardly affected by outliers); (4) linear regression over the last quarter (current trend, e.g. after a "
              "load change). The number appears in the column header of the value display, e.g. Drift (regression "
              "3), and changes immediately when switching; likewise in the detail window and the report's signal "
              "table. The choice applies "
              "to Drift (regression), Forecast, target time evaluation, regression lines, printing, export and "
              "report; it is remembered and saved with view and project."),
        ("b", "With the date/time axis: limit, target date/time and time from the last measuring point, e.g. "
              "\"max, 08.11.2026 20:02:01, 2 days 6 hrs 2 min\"."),
        ("b", "Without the date axis (seconds or rows): x2 in the unit of the X axis, e.g. \"min, x2 = 44.8218 s, "
              "0 days 0 hrs 1 min\"."),
        ("b", "\"already exceeded\": the last value already lies beyond the limit in the drift direction."),
        ("b", "\"no crossing\": the slope is 0 or there is no limit in the drift direction (e.g. rising, but only "
              "Y min set)."),
        ("p", "The markers do not affect the forecast; their drift (Drift column) applies only between M1 and M2."),
        ("h", "Regression lines in the graph"),
        ("p", "The check box \"Regression lines\" (second toolbar row, also in the detail window) shows the linear "
              "regression line over all data of each signal: dashed, in the signal's colour, across the signal's data "
              "range and on the signal's axis (left or right). It is the same line the columns Drift (regression) and "
              "Forecast are computed from."),
        ("b", "When zooming the dashes keep their length; the lines are not listed in the legend."),
        ("b", "Printing, export and both reports show the lines dashed as well. The setting is remembered and saved "
              "with view and project."),
        ("b", "Regression lines have no entries of their own in the legend of the graph: curve and line are one element. "
              "Clicking a signal's legend entry deactivates the signal together with its regression line, another click "
              "activates both again. Printing and export show only the lines of active signals."),
        ("h", "Target time"),
        ("p", "Next to Y max each signal has the field Target time: the time that should at least pass before the "
              "limit is reached, in days, hours and minutes, e.g. 2d 6h 30m (also 90min, 1.5h). Without unit: one "
              "number = hours, two numbers = hours minutes, three = days hours minutes. Empty = no target time."),
        ("b", "\"All\" next to the field applies this target time to all signals of all graphs (an empty field removes "
              "it everywhere); afterwards it can be changed per signal again."),
        ("b", "The target time is violated if the forecast reaches the limit earlier than the target time or the limit "
              "is already exceeded. The signal's row then gets a red background, the forecast is extended by "
              "\"(target time ... violated)\" and the graph showing the signal gets a faint red background. The red "
              "is matched to each colour scheme so lines and text stay readable."),
        ("b", "It is evaluated only with active markers, a limit and a target time set, and a time axis (date/time "
              "axis or X in s, min, h, d)."),
        ("b", "Applies equally in the detail window (graph and its own value display), when printing and exporting "
              "(faint red graph) and in both reports: table Limits and forecast with target time and target time "
              "status, red rows of the signal in all tables of the graph. Target times are saved in view and project "
              "and carried over when switching the file."),
        ("h", "Limit configuration (YAML) per mode"),
        ("p", "Graph options > Load limit configuration (*.yaml) reads a configuration file with limits and target distances "
              "per mode (structure: limits > modes > mode > steps and signals > signal > enabled, lower, upper; other "
              "sections of the file are not used). Without a configuration the manual values apply."),
        ("b", "The modes of the file are listed in the selection \"Mode\" in the header row of the value display "
              "(markers active); \"(manual)\" switches back to the manual values. Next to it are the name and extent "
              "of the loaded configuration."),
        ("b", "Signals are matched by name (exact, ignoring case, without a unit in brackets). Matched signals with "
              "enabled: true use the limits of the mode; their fields show the configured values. "
              "Signals the mode does not name or that do not match keep the manual limits and target times."),
        ("b", "steps is the target distance until the limit violation, as steps or as time: a number without unit "
              "(steps: 26306) means steps, i.e. measurement points (distance to the limit divided by the typical "
              "distance between two points); with units (steps: 7h 18m 26s, 45m, 90s, also d for days) it means time. "
              "If the forecast is shorter, the signal counts as violated (red row, "
              "faint red graph, as with the target time). A mode without steps (null) keeps the manual target times."),
        ("b", "The status line reports how many signals of the mode were matched. Configuration and mode are saved "
              "with view and project; the report lists them under settings and marks targets "
              "from the configuration with (YAML). Example: demo_data/demo_grenzen.yaml for demo_pruefstand.asc."),
        ("h", "Changing values in the value display and writing them back to the YAML"),
        ("p", "Once a configuration is applied, limits and steps can also be changed directly in the value display "
              "(also in the detail window). For signals from the configuration the change goes into the mode, not "
              "into the manual values: limit lines, forecast and evaluation follow immediately, an open configurator "
              "shows the new values and the header row reports \"* changed\"."),
        ("b", "If the mode has steps, this one value is the target for all signals of the value display, including "
              "signals without an entry in the configuration (as in the configurator: one setting per mode). The field "
              "Target time shows it for every signal (number = steps, with units = time); a change in any row applies "
              "to all, \"All\" is then hidden. A mode without steps keeps the manual target times."),
        ("b", "\"Save to YAML\" in the header row writes the changes back into the loaded file (other modes and "
              "sections are kept); a new configuration not yet saved asks for the file name."),
        ("b", "If both limits of a signal are cleared, it no longer counts as configured and uses the manual values "
              "again. Signals without an entry in the configuration stay manual."),
        ("h", "Limit configurator"),
        ("p", "Graph options > Limit configurator opens a window to create, edit, save with a name and load a limit "
              "configuration. If none is loaded yet, it creates a new one with the mode \"Standard\" and uses it "
              "right away."),
        ("img", "konfigurator", "Figure 12: limit configurator"),
        ("m", "1", "Name of the configuration (* = changed, not saved); New, Load, Save, Save as"),
        ("m", "2", "Choose, create, copy, rename or delete a mode (name in the field next to it)"),
        ("m", "3", "steps of the mode: number = steps, with units = time (e.g. 7h 18m 26s); next to it the interpretation and whether the mode is active in the program"),
        ("m", "4", "Suggest limits from data: This mode / All modes; the margin in percent of the span applies to both"),
        ("b", 'Limits from data - two variants with the same percentage margin: "This mode" applies only to the edited mode (visible active signals with data). "All modes" goes through all modes of the configuration (active signals with data, the search field applies): data per mode from the Auto analysis of all files of this mode (all DUTs), for modes without analysis from all loaded files. Existing limits are recalculated (data range plus margin); limits typed by hand in the table and inactive signals are kept. Changing the margin recalculates the visible active signals of the edited mode immediately. Modes without any data are named in the status line. Example 10 %: data 600..630 -> limits 597..633.'),
        ("m", "5", "All signals of the loaded files with data range: active, lower and upper limit"),
        ("b", "The table shows each signal of the loaded files once, with file and smallest and largest value. "
              "Signals only present in the configuration follow at the end (not in the data). Search and \"Active "
              "only\" narrow the list; \"Activate/Deactivate visible\" acts on the rows shown."),
        ("b", "A limit for a signal not yet configured activates it. Empty fields mean no limit on that side; a "
              "signal without an active limit keeps the manual values."),
        ("b", "Changes take effect immediately: if the edited mode is selected in the program (\"active in the "
              "program\"), limit lines, value display, forecast, target time evaluation, detail window and report "
              "follow directly. \"Use this mode in the program\" selects it there."),
        ("b", "Save writes the YAML with the same structure (limits > modes > ...); a new configuration asks for "
              "the file name. Other sections of a loaded file (e.g. plot, colors) and deactivated signals are kept. "
              "Loading works in the window or via Graph options > Load limit configuration."),
    ]),
    ("Limiter", [
        ("p", "The limiter reduces the data of individual files to the sections in which one or more guide signals "
              "lie within their limits. Example: a file contains a square-wave signal; only its upper part (e.g. value "
              "from 4.5) is to be the leading plot range - for all signals of that file."),
        ("img", "limiter", "Figure 13: limiter - only the upper phase of the square wave applies to all signals of the file"),
        ("m", "1", "Limiter menu: edit, load/save configuration, limiter active, remove limiter"),
        ("m", "2", "Limiter active, Load..., Save, Save as... and name of the configuration file"),
        ("m", "3", "Add rule"),
        ("m", "4", "Rule table: active, file (name, pattern or *), guide signal, limit min, limit max, delete"),
        ("m", "5", "Result per file: share of the measuring time within limits"),
        ("m", "6", "Hint in the file list"),
        ("m", "7", "Reduced data: current only in the upper square-wave phase, gaps separate the line"),
        ("h", "How to (example demo_rechteck.csv)"),
        ("b", "1. Open demo_data/demo_rechteck.csv and show Rechteck and Strom."),
        ("b", "2. Limiter > Edit limiter...: the first rule is preset with the file. Choose signal Rechteck, enter limit "
              "min 4.5, leave limit max empty."),
        ("b", "3. At once all graphs of the file show only the upper phase; file list and window show the share (here 50 % "
              "of the measuring time)."),
        ("b", "4. Further rules (e.g. temperature at most 80) act together with the first (AND); the active tick switches a "
              "rule off without deleting it."),
        ("b", "5. Save as... stores the rules as YAML (or Load: demo_data/demo_limiter.yaml)."),
        ("h", "Rules"),
        ("b", "Per rule: file, signal, limit min, limit max. An empty field means no limit on that side; the limits "
              "belong to the range (inclusive)."),
        ("b", "Several rules of the same file apply together (AND): only what all guide signals satisfy remains."),
        ("b", "File * applies to all files containing the signal; patterns like run_*.csv are possible. If a file lacks "
              "the signal, it stays unreduced (hint in the file list)."),
        ("b", "If the signals have different time bases (MF4), the state of the guide signal holds until its next "
              "sample. Guide signals from MF4 files are loaded automatically for this."),
        ("h", "Effect"),
        ("b", "Values outside are really dropped (smaller amount of data). At each gap an empty point separates the "
              "line, so nothing is connected across the removed sections."),
        ("b", "Everything works with the reduced data: graphs, markers and value display (min, max, mean, drift), "
              "detail window, printing, export and report."),
        ("b", "The file list shows, for each affected file, what percentage of the measuring time lies within limits."),
        ("h", "Limiter menu"),
        ("b", "Edit limiter...: window with the rule table. Changes take effect immediately (limits as numbers with comma "
              "or point). Files and signals offered come from the loaded files, from the automatic evaluations (after "
              "Analyse or a cycle: the group name, e.g. DES202609090470500176_DUT3, stands for all files of the "
              "evaluation, plus the single files) and from files chosen manually with Choose file... (only the signal "
              "names are read; the file is not displayed). In the Auto window, Choose file... starts in the source folder."),
        ("b", "Every file is offered only once (even if it occurs in several evaluations, regardless of case); an evaluation "
              "group made of exactly one file appears only as that file."),
        ("b", "Transfer rule: apply a defined rule (file, signal, limit min/max, active) to a selection of files. Choose the "
              "rule, tick the files via the button Files: ... (All, None, Only with signal; files without the signal are "
              "marked), Apply to selection. If a file already has a rule for this signal it takes over limits and active, "
              "otherwise a rule is added. All known files and evaluation groups are offered (loaded files, automatic "
              "evaluations, Choose file...)."),
        ("b", "Limits and limiter: Analyse and the proposals take the limiter into account - minimum, maximum and proposed "
              "limits come only from the sections within the limiter, cut-off peaks do not count. If a limiter rule is "
              "added or changed later, the Auto window shows a hint; Re-propose limits then recalculates the limits of "
              "the evaluation's mode from the reduced data (active/inactive and target time are kept). Check and save "
              "the limit configuration afterwards."),
        ("b", "Load limiter configuration (*.yaml)... / Save...: the rules are in the limiter section of a YAML file. "
              "Other sections are kept when saving, so limiter and limit modes can share one file."),
        ("b", "Limiter active: switches the reduction off and on without losing the rules. Remove limiter: all rules "
              "gone, all data visible again."),
        ("b", "The rules are saved with the view (*.mgraph) and applied again when it is loaded."),
        ("p", "File layout: section limiter with active (true/false) and rules, a list of rules with file (file "
              "name, pattern or *), signal, min, max (null = no limit) and enabled (true/false)."),
    ]),
    ("Automatic evaluation", [
        ("p", "Menu Auto > Set up automatic evaluation... evaluates a folder automatically and cyclically: read raw data "
              "(*.csv, *.asc, *.parquet), combine it per group by time stamp, apply the limiter, save one single graph "
              "per signal as PNG and evaluate the actual values against the limit configuration as Time_counter.json."),
        ("img", "auto", "Figure 14: automatic evaluation window (steps 1-3) and step 4 window"),
        ("m", "1", "Auto menu: set up, Start, Stop, Run one cycle now, Create report..., Show log"),
        ("m", "2", "Current step and Reset (all steps free again, start at step 1)"),
        ("m", "3", "Step 1: name of the new evaluation and Create"),
        ("m", "4", "Evaluation (selection only) and Delete"),
        ("m", "5", "Choose directory rule and Manage directory rule..."),
        ("m", "6", "Details of the rule for information: source, target, read or excluded files, target folders and modes"),
        ("m", "7", "Step 2: Modes and target times... with state"),
        ("m", "8", "Mode list: similar names grouped, tick = process, target time hh:mm:ss per mode"),
        ("m", "9", "Step 3: Analyse, limit configurator, limiter, re-suggest limits"),
        ("m", "10", "Step 4: Open step 4 window... (opens by itself when step 3 is completed)"),
        ("m", "11", "Step 4 window: cycle time, result file, Start, Stop, Run now, log, report - below the progress"),
        ("m", "12", "Result of all evaluations: evaluation, DUT/part, mode, group, actual, target, fulfilment (below the log)"),
        ("b", "Result table (step 4): per row evaluation, DUT/part, mode, group (serial number/DUT, image folder of the same "
              "name; the key count_<mode>_<group> of the result file is in the cell tooltip), actual and target (for a "
              "target time as h:mm:ss, e.g. 180:51:08 of 24:00:00, otherwise measuring points with thousands separator) "
              "and fulfilment in percent (green from 100 %, otherwise red). The table fills the window down to the log."),
        ("b", "Groups and image folders: if the files of a source folder lie in subfolders with a serial number (e.g. "
              "...\\HTOE22kW\\CSV\\DES202507230117500132\\*.csv), every serial number gets its own group and image folder - "
              "the serial numbers are no longer thrown together into one group \"CSV\". Without serial folders the group "
              "is named after DES number + DUT, otherwise after the serial number in the file name (e.g. "
              "DS202608200479700017), otherwise after the common file name; a meaningless folder name (CSV, Files, "
              "Report, Data ...) is never used, then the next folder above (e.g. HTOE22kW)."),
        ("h", "How it works - fixed order in four steps"),
        ("b", "Every step has a heading with state ([now], [done - locked], [next]), an explanatory text and detailed "
              "tooltips on all fields and buttons. Only the current step can be operated; Complete step checks it, locks "
              "it and frees the next one. Start (run started) frees all steps again, as does Reset (then start at step 1)."),
        ("b", "Step 1 - define the evaluation, field by field: (1) Name: enter the name of the new evaluation and confirm "
              "with Create; if the field is empty, an existing evaluation is chosen below; if there is none yet, a hint "
              "says that a name is required. (2) Evaluation: selection only; without entries a hint asks for a name. "
              "(3) Directory rule: choose one of the rules defined so far; if there is none yet, a hint says that a rule "
              "must be created. Manage directory rule... opens the directory manager and takes the name as the new rule "
              "(if the evaluation already has a rule, that rule is edited)."),
        ("b", "Below, the details of the rule are shown for information only (no input): source directory, target "
              "directory (base target folder + extended target folder), read (all files or number of exclusions) and how "
              "many target folders and modes the rule yields. Every target folder of the rule is a part of the evaluation "
              "(e.g. one DUT in one mode). Completing requires an evaluation with a rule that yields target folders with "
              "measurement files."),
        ("b", "Step 2 - modes and target times: Modes and target times... opens a window with all modes of the "
              "evaluation; modes with similar names are grouped (e.g. AC: AC_22kW_3ph_615V, AC_11kW_1ph_230V). Per mode a "
              "tick (process) and the target time hh:mm:ss (e.g. 24:00:00 or 07:18:26; applies to all DUTs of the mode). "
              "Modes not ticked need no target time. All/None and for all ticked set many at once. Completing requires a "
              "target time for every ticked mode."),
        ("b", 'Reset step: every step has a "Reset step" button (visible once it is completed or while the run is going). It resets this step and all following ones: step 1 = all steps, step 2 = steps 2 to 4 and so on. The steps are open again and must be completed anew; a running cycle is stopped. Settings, evaluations and results are kept.'),
        ("b", 'Counter per mode: the selected data do not define the counter themselves - a cyclic signal may need a time or an edge counter, or should not be evaluated at all. So in Modes and target times you choose per mode: Time (target hh:mm:ss; time counter and violation over time), Edge (target = number of edges; "Edges..." in the row sets the signals; violation over the number of edges) or Ignore (no evaluation: no counter, no violation; images and statistics are still created). Tick off = do not process at all. The choice applies immediately to all selected data of the mode and can be changed at any time, also after completing step 2 and during the cycle (the next cycle evaluates anew). New DUT folders of the rule take over counter and target of their mode. Empty target = infinite: no violation possible. Step 2 cannot be completed while a processed mode with counter Edge has no edge.'),
        ("b", "Step 3 - analyse and check limits: Analyse reads all files (all ticked modes and DUTs) and suggests limits "
              "per mode; check and save them in the limit configurator, set limiter rules and re-suggest limits if needed."),
        ("b", "Step 4 - own window: because of the amount of information, Complete step in step 3 opens a second window "
              "Automatic evaluation - step 4; the window with steps 1 to 3 stays open. Later Open step 4 window... (or "
              "Auto > Show log) opens it again. The progress appears in both windows."),
        ("b", "Step 4 - start the cycle: set cycle time (e.g. 2m), PNG and result file, then Start (cyclic) or Run now "
              "(one cycle at once). Results: PNG and statistics.json in the target folder, counters in the result file; "
              "report via Create report... (one per mode with all DUTs)."),
        ("h", "Several evaluations"),
        ("b", "Several evaluations can be created (one per name, each with its own directory rule). The cycle processes "
              "all evaluations one after the other; steps 2 and 3 refer to the selected evaluation."),
        ("b", "Mode and DUT come from the rule ({Mode}, {DUTx}); so all DUTs of a mode share its limits. The key in the "
              "result file is count_<mode>_<group>, the column in the report is named after the DUT."),
        ("b", "Target time (hh:mm:ss, also 24h, 7h 18m 26s or steps as a number): replaces the mode's target time "
              "(steps) for counters, steps in the result file, time to violation and the red background."),
        ("b", "Result file (all) = target directory\\Time_counter.json: the target directory is the base target folder of "
              "the directory rule (e.g. C:\\MessGraph\\_TestResult), not the extended folder per mode/DUT. The field holds "
              "only the file name: default Time_counter.json, other names possible (e.g. HTOE_time_counter.json; .json is "
              "added, \\ / : * ? \" < > | are not allowed). \"Standard\" resets the name; the full path is shown below. All "
              "modes and DUTs write one after the other into this one file in every cycle and add their entries; images "
              "and log are in the respective extended target folder."),
        ("b", "Parts without measurement files or without target folder are skipped with a hint, the others run. The "
              "table shows the counters of all evaluations, the progress bar names the one running."),
        ("b", "Older settings with manually entered source and target directory are kept as evaluations without a "
              "directory rule and keep running (info: Without directory rule)."),
        ("h", "Settings"),
        ("b", "Base folder of the program: program folder\\Test. The folder selection in the directory manager starts "
              "there (or at the folder already entered)."),
        ("b", "Advanced: grouping of the files (expandable in step 1): all files of a target folder = one evaluation "
              "(default) or groups by group pattern."),
        ("b", "Cycle time: 60s, 5m, 1h ... (at least 5 s). The first cycle starts immediately."),
        ("b", "Result file (default Time_counter.json), PNG per signal on/off, only modes with hits."),
        ("b", 'Result files: modes with counter Time write into the result file (default Time_counter.json), modes with counter Edge into the file next to it (Time_counter.json -> Flanken_counter.json, HTOE_time_counter.json -> HTOE_Flanken_counter.json, other names -> <name>_Flanken.json); Ignore writes no entries. "Edges..." sets the edges per mode: per signal Value1 (upper), Value2 (lower, either may stay empty), minimum count n and optionally an own target (otherwise the number of edges of the mode applies).'),
        ("b", 'Edge above Value1: the signal rises above Value1, stays above for at least n values and then falls below it again for at least n values. Edge below Value2: the signal falls below Value2, stays below for at least n values and then rises above it again for at least n values. Shorter outliers do not count; if the signal already starts beyond the threshold, this first section does not count; if the return is still open at the end, the table shows "(+1 open)". The result file is then Flanken_counter.json (key edges_<signal>_<group> with actual, edges_upper, edges_lower, steps, fulfillment_percent); own file names are kept. The table columns are then called Signal and Edges.'),
        ("b", 'Violation in the edge counter: if a number of edges is given as target (target of the edge under Edges... or number of edges of the mode), the violation does not refer to time but to edges. Per signal with limits: expected edges until the limit violation = counted edges + edge rate (counted / measuring time without gaps) * time to violation from the trend line. Less than the target = "Violation before target number of edges!" (red background). Limit already reached: counted edges against the target; trend not heading for a limit: infinite, no violation. Text block: target, counted edges, edges until violation. In the result file per entry violation, edges_to_violation, violation_signal and duration_s; in the table "fulfilment ... - Violation" with tooltip. Without an edge target there is no violation.'),
        ("b", "Group pattern: empty = automatic. File names with DES number and DUT (e.g. HTOE_PV_DES202609090470500176_"
              "AC_22kW_3ph_725V_DUT3) form the group DES202609090470500176_DUT3; otherwise the file name without "
              "appended counters and time stamps is used (Measurement_001, Measurement_002 -> Measurement). Own pattern: "
              "regular expression, all bracket groups are joined with _, e.g. (DES\\d+).*(DUT\\d+)."),
        ("h", "One cycle"),
        ("b", "Only new or changed files are read (modification time and size); data already read stays in memory. "
              "Deleted files drop out of their group. Unreadable files are only retried when they change."),
        ("b", "All files of the source folder = one evaluation (default): all files are combined into one measurement, "
              "even with different signals. Name of the evaluation: DES number + DUT from the file names, otherwise the "
              "common base name, otherwise the folder name. Switched off, the files form groups by file name (group "
              "pattern)."),
        ("b", "Joining by time stamp: while reading, the header line of each file is located (also behind a preamble) "
              "and the start time determined - in this order: date column in the data, date and time in the first data "
              "row, clock time of the first data row with the date from the preamble or file name, time stamp in the "
              "preamble (e.g. Start: 09.06.2026 10:00:00), time stamp in the file name, finally the file's modification "
              "time (note in the log). The files are then sorted by this time - not by name or modification time - and "
              "joined; duplicate times only once, gaps between files separate the line."),
        ("b", "The log lists the detected start time of each file and its origin; after the analysis the window shows a "
              "summary (e.g. 12x date column)."),
        ("b", "The limiter (Limiter menu) applies here too: rules whose file pattern matches the group name or a file "
              "of the group reduce the combined data."),
        ("b", "Evaluation per mode of the limit configuration: the samples in which all signals of the mode lie within "
              "their limits are counted. Result per mode and group under count_<Mode>_<Group>: actual (in the unit of "
              "the target: samples, seconds for steps given as time), actual_count (samples), steps (target from the "
              "configuration) and fulfillment_percent (actual / steps * 100). Existing entries of other groups in the "
              "file are kept."),
        ("h", "Analysing the source folder and setting values"),
        ("b", "Analyse (step 3) reads all files of the ticked modes and DUTs. The signals appear in the limit configurator "
              "(column File: Auto: n files, plus data min/max over all files)."),
        ("b", "If a limit configuration is loaded, it applies; the status line says how many signals have no entry yet. "
              "In the configurator they can be activated and filled with Suggest from the data."),
        ("b", "Without a configuration all signals are listed with proposals: mode Auto, all signals active, lower and "
              "upper limit from the data (1 % to 99 % value plus 10 % of the span), target time 24h (24h 00m 00s). "
              "Signals can be deactivated, limits and target time changed; Save creates the configuration file."),
        ("b", "Mode: every part of the evaluation uses exactly one mode ({Mode} of the directory rule). Its limits and "
              "target time apply to all files of this part."),
        ("img", "autograph", "Figure 15: single graph of the automatic evaluation (violation before target time)"),
        ("m", "1", "Upper limit line (Limit_max)"),
        ("m", "2", "Lower limit line (Limit_min)"),
        ("m", "3", "Trend line (dashed), extended beyond the end of the data"),
        ("m", "4", "Text block: signal, limits, regression with m, b and f(x) = m * x + b"),
        ("m", "5", "Target time, time to violation and assessment"),
        ("m", "6", "Red background: violation before target time"),
        ("b", "Background colour of the graph: light red = regression reaches a limit before the target time; light "
              "yellow = measured values (peaks) outside Limit_min/Limit_max (text line \"Peaks outside the limits!\"); "
              "light violet = both; white = OK."),
        ("b", "Images: one single graph per signal with all data of the evaluation in its subfolder. Without the Pillow "
              "package SVG is written instead of PNG. Contents of each graph:"),
        ("b", "upper and lower limit line (red dashed, from the mode) and the trend line (orange dashed, regression line of "
              "the kind chosen under Graph options > Drift regression, extended 20 % beyond the end of the data)."),
        ("b", "Text block on the right: signal name, Limit_max, Limit_min, regression used with its number, m and b and the "
              "line equation f(x) = m * x + b (x in seconds from the first sample), target time, time to violation (from "
              "the last sample along the trend line to the limit) and the assessment."),
        ("b", "If the violation lies before the target time (or the limit is already reached), the plot area is red and "
              "the text block reports Violation before target time!"),
        ("h", "Progress"),
        ("b", "During Analyse and during a cycle a progress bar in the Auto window and in the status line of the main "
              "window shows what is happening: Reading files 3/12: file name, Creating images 5/80: signal, Writing "
              "result file. Cancel stops after the current file or image; the rest follows in the next cycle."),
        ("h", "Report over several evaluations"),
        ("img", "report", "Figure 16: create report with schedule"),
        ("m", "1", "Tick evaluations (one DUT each)"),
        ("m", "2", "Title, project, mode"),
        ("m", "3", "Output folder (empty = common folder of the target folders)"),
        ("m", "4", "Watermark NOT RELEASED (on by default)"),
        ("m", "5", "Schedule on/off"),
        ("m", "6", "Times, daily or once"),
        ("m", "7", "Next date"),
        ("m", "8", "Create report now"),
        ("m", "9", "Progress (the report is not cancelled)"),
        ("b", "Auto > Create report...: each evaluation corresponds to one DUT. Tick the evaluations that go into the "
              "report (evaluations without outputs are unticked; All/None). Title, project, mode and output folder "
              "can be entered."),
        ("b", "Evaluation (top of the window): the report takes only the DUTs of the chosen evaluation (default: the one "
              "selected in Auto), i.e. only its target folders - parts of other or old evaluations with the same name are "
              "not mixed in. New modes and DUTs found later by the directory rule are ticked automatically (also for the "
              "scheduled report); only explicitly unticked target folders are remembered. \"All evaluations\" shows all "
              "parts prefixed with [evaluation]. For a DUT without outputs the note gives the reason (e.g. mode not "
              "selected for processing in step 2, source folder missing)."),
        ("b", "One report per mode: the ticked evaluations are grouped by mode; every mode gets its own report with all chosen "
              "DUTs of that mode. File name: Report_<mode>_<date_time>.pdf, e.g. "
              "Report_DC_Charge_V2L_540V_20261116_151230.pdf. Empty output folder = common folder of the mode's "
              "target folders (e.g. _TestResult), with one DUT its target folder. Empty mode = mode of the evaluations; an "
              "entered mode only applies when exactly one report is created."),
        ("b", "Every target folder is offered only once; duplicate evaluations (same source and target) are removed "
              "automatically when loading and creating."),
        ("b", "Without a previous cycle: chosen evaluations without outputs (e.g. only Analyse pressed) automatically get a "
              "cycle first when creating the report, then the reports are created. If an analysis or a cycle is running, "
              "the report follows afterwards. Evaluations without outputs are marked in the list."),
        ("b", "Watermark: \"NOT RELEASED\" diagonally on every page is on by default and can be unticked before creating."),
        ("b", "Graphs per page: 9 (3 x 3), 4 (2 x 2), 2 (side by side) or 1 (full page) - only for the mode part (images "
              "of each DUT); the comparison part always has 9 graphs per page. Each DUT section is headed \"Mode: <group>\"."),
        ("b", "Layout (A4 landscape): cover page (Test Report, Project, Mode, Date, DUTs) - Summary Comparison (per signal "
              "the mean per DUT, Average, Min % and Max % as deviation of the smallest/largest DUT value from the "
              "average, Limit Min, Limit Max) - Signal Plot Comparison (one page per signal with the PNGs of all DUTs) - per "
              "DUT a table (Min, Max, Mean, Std, Limit Min, Limit Max; Mean green within limits, red outside) and all PNGs "
              "of the DUT (3 x 3 per page)."),
        ("b", "It is based on the outputs of the cycles: per evaluation the PNGs and statistics.json in the target folder. "
              "The report runs in the background with a progress bar; the PNGs are embedded unchanged."),
        ("b", "Creating a report is never cancelled (there is no Cancel button): errors such as missing or broken images, "
              "unreadable statistics.json, evaluations without outputs, errors in a section or a busy file name are "
              "collected and everything else is produced. Such an incomplete report gets the red note INCOMPLETE REPORT "
              "on the cover page, the appendix \"Appendix: Incomplete Report\" with all reasons at the end and the file "
              "name suffix _err, e.g. Report_Precon_20261119_124400_err.pdf. If the file name cannot be written, "
              "the report is saved under a fallback name (same folder with time, otherwise the user folder); this is also "
              "listed in the appendix. The status line shows the number of incomplete reports."),
        ("h", "Scheduled report"),
        ("b", "The schedule is decoupled from the data cycle: data can be updated e.g. every 2 minutes, the report is "
              "still created only at fixed times, e.g. 00:00:00."),
        ("b", "Times: one or more, separated by commas (00:00:00, 12:00, 18:30). daily: every day at each time; once: only "
              "at the next date, then the schedule switches itself off."),
        ("b", "At the date the report is created with the saved settings (ticked evaluations, title, project, mode, output "
              "folder, watermark) - one per mode; thanks to the date/time in the name each run creates its own file "
              "(Report_<mode>_20261117_000000.pdf)."),
        ("b", "The next date is shown in the report window and in the Auto window; the log of the evaluations notes every "
              "scheduled report. The schedule runs while MessGraph is open and is kept for the next start."),
        ("img", "reportseite", "Figure 17: example report - Summary Comparison and Signal Plot Comparison"),
        ("m", "1", "Summary Comparison: mean per DUT and average"),
        ("m", "2", "Min % and Max %: deviation of the smallest/largest DUT value from the average"),
        ("m", "3", "Limit Min and Limit Max from the mode"),
        ("m", "4", "Signal Plot Comparison: the PNGs of all DUTs per signal"),
        ("m", "5", "Watermark NOT RELEASED"),
        ("h", "Directory manager"),
        ("img", "verzeichnis", "Figure 18: directory manager - directory rule in six steps"),
        ("m", "1", "Name of the rule (from the automatic evaluation: name of the evaluation), edit existing rule, delete"),
        ("m", "2", "Hint: NEW rule or EDIT of an existing rule"),
        ("m", "3", "Step 1: choose the source folder and analyse the structure - subfolders per level"),
        ("m", "4", "Step 2: data as a tree, expandable and collapsible, tick per file or folder"),
        ("m", "5", "Step 3: base target folder"),
        ("m", "6", "Step 4: detected placeholders, own value, insert"),
        ("m", "7", "Extended target folder from placeholders, freely combined"),
        ("m", "8", "Step 5: target folder = base target folder + ext. target folder, with example"),
        ("m", "9", "Step 6: preview per target folder with tick, mode, DUT, files, status"),
        ("m", "10", "Save rule: take over all details, create missing target folders"),
        ("b", "Opened via automatic evaluation, step 1, Manage directory rule... This is where the rule is defined. By "
              "default the name of the evaluation is the name of a new rule. If another (existing) rule is chosen at the "
              "top, it is an edit - the hint under the name clearly shows NEW rule or EDIT; saving changes the existing "
              "rule and all evaluations using it are updated."),
        ("b", "Step 1 - source folder: choose it and analyse the structure. Structure means the names of the subfolders "
              "per level, e.g. level 1: DUT1, DUT2 -> {DUTx}; level 3: AC_22kW_3ph_615V, Precon -> {Mode}."),
        ("b", "Step 2 - select data: all measurement files found as a tree; folders can be expanded and collapsed, "
              "default: all active. Untick files that are to be ignored (tick per file; per folder all files of this "
              "folder). With very many files (more than 3000) there are only ticks per folder."),
        ("b", "Step 3 - base target folder: choose it with the browser (e.g. ...\\MessGraph\\_TestResult)."),
        ("b", "Step 4 - placeholders: MessGraph detects from the names of the subfolders {Mode} (e.g. AC_22kW_3ph_615V; "
              "folder names like Precon by their level), {Testlauf} (test run: DV, PV), {Test-Variante} (test variant: "
              "HTOE_11kW, HTOE_22kW, HTOE_Mix, PTCE_...), {Seriennummer} (serial number DES202507230117500132 ...; "
              "otherwise from the file names), {DUTx} (puts the serial number into a fixed relation) plus {Datetime} "
              "(system time at the first save) and {Name} (name of the evaluation). Every element can optionally be "
              "given an own value (column own value). The extended target folder combines them freely, e.g. "
              "{Testlauf}_{Test-Variante}\\{Mode}\\{DUTx} or {Mode}\\{Name}; insert appends a placeholder."),
        ("b", "If the mode is not in a folder name but in the file name, it is detected there: example ...\\DV\\HTOE22kW\\"
              "CSV\\DES202507230117500132\\DES202507230117500132_AC_22kW_3ph_615V.csv (also _725V, _800V) -> {Testlauf} = "
              "DV (source folder), {Test-Variante} = HTOE22kW, {Seriennummer} = DES202507230117500132, {Mode} = "
              "AC_22kW_3ph_615V etc. from the file names; proposed is {Testlauf}_{Test-Variante}\\{Mode}\\{Seriennummer}. "
              "One folder is then split into several target folders (one per mode, each reads only its files). A file "
              "without a mode in its name (e.g. DES202507230117500132_.csv) is marked in the preview; deselect it in "
              "step 2. An own value for {Mode} applies to all files."),
        ("b", "Step 5 - target folder = base target folder + extended target folder; an example shows the first target folder."),
        ("b", "Step 6 - check the preview: one row per target folder with tick (All, None), mode, DUT or serial number, "
              "number of folders and files (excluded ones in brackets) and status (new, exists). Folders without a value "
              "for a placeholder (e.g. Logs without mode) are marked and left out; if several DUTs end up in one target "
              "folder, the status warns."),
        ("b", "Save rule: all details are saved in the rule; missing target folders are created. If that is not possible "
              "(e.g. missing permissions), a window with the error message appears and the rule is not saved. If the "
              "manager was opened from the automatic evaluation, the evaluation gets the new rule."),
        ("b", "Only new data are synchronised and processed: existing parts of an evaluation keep the data they have read "
              "when saving; new folders and files are added, deselected ones drop out. Before every cycle MessGraph picks "
              "up new folders of the rule (e.g. a new mode folder) and creates their target folders."),
        ("b", "Older rules (pattern and template) keep working; opened in the directory manager, source folder and target "
              "base are taken over and the placeholders are proposed anew."),
        ("h", "Sequence of a cycle in detail"),
        ("p", "A cycle starts immediately with Start and then after each cycle time, once with Run now. The active "
              "evaluations are processed one after the other (progress: [evaluation] step n/m); for each the following "
              "steps run. Then the shared result file is written."),
        ("b", "1. Due: if the previous cycle has not finished when the next one is due, the due one is skipped (note in "
              "the window and in the log); two cycles never run at the same time."),
        ("b", "2. Basis: mode of the evaluation from the limit configuration, target time of the evaluation (replaces the "
              "mode's steps), limiter rules, regression type. If one of them changed (or the target, the PNG setting), "
              "all groups are evaluated anew and all images redrawn."),
        ("b", "3. Compare the source folder: first new folders of the directory rule are picked up; read are the *.csv, "
              "*.asc and *.parquet of the part's folders without the files deselected in the directory manager; files in "
              "the target folder are never read. Per file modification time and size count. Deleted files are removed from "
              "their group (the group is evaluated anew)."),
        ("b", "4. Read: in the first run all files, then only new and changed ones, oldest first. While reading, header "
              "and columns are detected and the timestamp determined - in this order: date column, date/time in the first "
              "data row, time with date from the preamble, preamble, file name, modification time. All signals are put on "
              "absolute time. Broken files or files still being written are logged and only retried after a further change."),
        ("b", "5. Group: with All files of the source folder = one evaluation all files form one group; otherwise by file "
              "name (group pattern, DES..._DUTn or name without appended counters/timestamps)."),
        ("b", "6. Join: per group in which something changed all its files are put one after the other by timestamp. "
              "Overlapping time ranges count only once; gaps between files remain gaps (the line is split, the time not counted)."),
        ("b", "7. Limiter: rules whose file pattern matches the group or one of its files cut out the sections outside "
              "their limits - for all signals of the group. The share of measuring time within the limiter is logged."),
        ("b", "8. Evaluate: counted are the measuring points in which all signals of the mode lie within their limits at "
              "the same time. actual = this time in seconds (target time as time) or the number of points (target time as "
              "steps), actual_count = number of points, steps = target time, fulfillment_percent = actual / steps. Without "
              "a limit configuration a proposal is made from the data (limits and target time 24h) and shown in the limit "
              "configurator for checking."),
        ("b", "9. statistics.json: per group in the target folder (key figures, limits, trend, time to violation, peaks) - "
              "basis of the report."),
        ("b", "10. Images: one PNG per signal with limit lines, dashed trend line, text block and background colour (red = "
              "regression violates the target time, yellow = peaks outside the limits, violet = both) - only for groups "
              "with changes."),
        ("b", "11. Result file: the counters of all evaluations go into the shared Time_counter.json (key "
              "count_<mode>_<group>); existing entries of other evaluations remain. It is first written to a .tmp file "
              "which then replaces the old one - a reader never sees half a file."),
        ("b", "Result file in use: within MessGraph only one operation writes at a time (lock); several MessGraph "
              "instances coordinate via the lock file Time_counter.json.lock (an orphaned lock file of a program that "
              "has ended is removed). If the file still cannot be replaced (on Windows \"Access is denied\"), MessGraph "
              "determines the process holding it (e.g. virus scanner, Windows Search, OneDrive, editor, second "
              "instance), writes it to the log and retries for about 10 s; then the content is written directly into "
              "the file. Other processes are not terminated. The same applies to statistics.json, PNG and report."),
        ("b", "12. Log and display: MessGraph_Auto.log in the target folder (first run or following run, every file with "
              "start and timestamp source, limiter, notes, errors, duration); in the step 4 window status line, counter "
              "table and log."),
        ("b", "Cancel: stops after the current file or image; the next cycle continues with the open files and images."),
        ("b", "Memory: the data read stays in memory until the program ends (that is why a following run only reads new "
              "data). After a program start the next cycle is a first run again."),
        ("b", "Report schedule: runs independently of the data cycle at the set times; if a chosen evaluation still has "
              "no outputs, a cycle runs first."),
        ("h", "First run and following runs"),
        ("b", "First run (after Start, Run now or program start, or after changing source, subfolders or grouping): all "
              "files of the chosen source folder are processed - without time budget, even if this takes longer than the "
              "cycle time. The log says First run: all n files."),
        ("b", "From the second run on: only new and changed files (different modification time or size) are read; deleted "
              "ones drop out. The groups in which something changed are evaluated, each with all its data. The log says "
              "Following run: n new/changed files. Without changes nothing is read and nothing redrawn."),
        ("h", "Cycle time too short"),
        ("b", "From the second run on, a cycle works at most 70 % of the cycle time. What no longer fits (further files, images) is spread over "
              "the following cycles. If a cycle is still running when the next one is due, that one is skipped. In both "
              "cases a note appears in the window and in the log."),
        ("b", "Log: MessGraph_Auto.log in the target folder (start, stop, every cycle, notes, errors); Show log shows the "
              "last lines in the window."),
        ("b", "Start, Stop and Run one cycle now are in the Auto menu and in the window; the table shows the counters of "
              "the last cycle. The settings are kept for the next program start."),
        ("b", "Run one cycle now (also without Start): immediately and without time budget; all groups are evaluated "
              "anew, all images and the result file rewritten, even if no file is new. As always only new and changed files "
              "are read (all in the first run). The status line reports the result."),
        ("b", "If the limit configuration, mode or limiter changes, the next cycle evaluates all groups anew and redraws "
              "the images."),
    ]),
    ("Databases (DBC, ARXML, A2L, CDD)", [
        ("p", "A recorded log file often needs several definition files at once, e.g. a DBC for the powertrain CAN, "
              "an AUTOSAR ARXML for the vehicle CAN, two A2L files for two ECUs and a CDD. Any number of databases "
              "can therefore be combined for each MF4, MDF and BLF file: button \"Databases...\" in the file entry. "
              "If the recording contains raw CAN frames (CAN_DataFrame), the dialog opens on loading."),
        ("img", "datenbasen", "Figure 19: databases dialog with DBC, ARXML, two A2L files and a CDD"),
        ("m", "1", "DBC and ARXML files, each with CAN channel selection"),
        ("m", "2", "Add databases (several files at once, all types mixed)"),
        ("m", "3", "A2L files and conversion of raw values"),
        ("m", "4", "CDD files"),
        ("m", "5", "Take last used, apply, close"),
        ("m", "6", "Databases... button in the file entry"),
        ("m", "7", "Decode new bus recordings automatically"),
        ("h", "Selecting files"),
        ("p", "\"Add databases...\" opens the file browser with the filter \"Databases (dbc, arxml, a2l, cdd)\". "
              "Several files can be ticked, also from different folders one after another. They are sorted by "
              "extension; duplicates are skipped, other extensions are reported. \"Remove\" per row or "
              "\"Remove all\" changes the selection."),
        ("h", "Applied as needed"),
        ("p", "\"Apply\" uses all selected files. Files that do not fit the recording do no harm: a DBC or ARXML "
              "without a matching CAN ID, or an A2L without a matching measurement, is reported as \"Not needed\" "
              "in the detection info. A fixed collection of databases can thus serve many recordings. If two files "
              "describe the same message, the first one listed wins (DBC before ARXML)."),
        ("p", "With \"Decode new bus recordings ... automatically\", newly opened MF4/MDF/BLF files are decoded right "
              "away with the databases applied last, without showing the dialog. If one of the files is missing or "
              "decoding fails, the dialog opens with the message."),
        ("h", "DBC"),
        ("p", "For each DBC the drop-down sets the CAN channel it applies to: all channels or CAN 1 to CAN 8. "
              "\"Apply\" decodes the messages; the signals appear in the file's list. Signals with duplicate names "
              "get the suffix (DBC G...). If no message matches, a hint appears: check CAN IDs and channel."),
        ("h", "ARXML (AUTOSAR)"),
        ("p", "An ARXML file (AUTOSAR system description) is used like a DBC, also with channel selection. MessGraph "
              "reads it without additional packages: CAN frame triggerings (ID, standard/extended), frames with their "
              "PDUs, I-signal mappings (start bit, length, byte order), conversion from COMPU-METHOD (factor, offset), "
              "unit as well as sign and floating point from the base type. Multiplexed and container PDUs are skipped "
              "and reported. For MF4/MDF the ARXML is converted into a DBC internally."),
        ("h", "A2L"),
        ("p", "Channels whose name matches a MEASUREMENT in an A2L get its unit if the recording has none. With "
              "several A2L files the first file wins for a name. Suffixes such as \\XCP:1 in channel names are "
              "ignored when comparing. \"Convert raw values ...\" also applies the conversion (LINEAR, linear "
              "RAT_FUNC, TAB_INTP, TAB_NOINTP). Only switch it on if the recording holds raw ECU values, otherwise "
              "values are converted twice."),
        ("h", "CDD"),
        ("p", "CDD files are assigned and remembered. Evaluating diagnostic data is not built in yet."),
        ("h", "Applying and changing"),
        ("p", "Signals already shown stay in their graphs after \"Apply\", including their colour. An empty "
              "assignment restores the original channels. \"Take last used\" inserts the last assignment. The "
              "assignment is saved with the view and in definition files; views from older versions (one A2L, one "
              "CDD) are still read."),
        ("h", "MDF files"),
        ("p", "Files with the extension .mdf (ASAM MDF 3.x, occasionally MDF 4 under the old extension) are read "
              "like MF4, with the same features: loading channels when ticked, downsampling, databases, date/time "
              "axis. The detection info shows the MDF version."),
        ("h", "BLF files (Vector)"),
        ("p", "BLF (Binary Logging Format) is the logging format of Vector tools such as CANoe and CANalyzer. A BLF "
              "contains the CAN and CAN FD messages as they were on the bus, but no physical values. MessGraph "
              "reads BLF without additional packages:"),
        ("b", "Without a DBC, every data byte of each message (ID and bus) appears as a signal, e.g. \"0x100 (CAN 1) "
              "Byte 0\" with values 0 to 255. The detection info shows the number of messages, IDs and buses."),
        ("b", "With a DBC or ARXML (\"Databases...\" button below the file name, several can be combined) the signals are decoded: name, unit, "
              "factor/offset, Intel and Motorola byte order, sign, standard and extended IDs, multiplexing and CAN FD "
              "up to 64 bytes. Messages without a DBC entry remain visible as data bytes."),
        ("b", "The channel per DBC (All, CAN 1, CAN 2 ...) restricts decoding to one bus. If the same ID occurs on "
              "several buses, the signal name carries the bus, e.g. \"Speed (CAN 2)\"."),
        ("b", "The time axis starts at the measurement start from the BLF header, so the date/time axis works."),
        ("b", "A2L and CDD are not evaluated for BLF. The DBC assignment is saved with the view and in definition "
              "files; calculated signals from decoded signals are possible."),
        ("p", "Example: demo_data/demo_can.blf with demo_data/demo_can.dbc (engine, battery, vehicle speed with an "
              "extended ID, cell voltages as CAN FD on CAN 2). To combine several databases: demo_can_motor.dbc "
              "(engine, vehicle) together with demo_can_batterie.arxml (battery, cells)."),
    ]),
    ("Calculating signals", [
        ("p", "New signals can be calculated from the signals of a file, e.g. power from current and voltage. The "
              "result is a signal of its own with name, unit and values. It appears in the file's signal list (with = "
              "in front) and can be used like any other signal: drag into graphs, measure with markers, right Y axis, "
              "limits and forecast, file comparison, printing, export and report. Up to 10 calculated signals are "
              "possible per file."),
        ("img", "berechnen", "Figure 20: calculating a signal"),
        ("m", "1", "Calculate... button below the file name"),
        ("m", "2", "Calculated signals of the file with formula: edit, delete"),
        ("m", "3", "Name (free choice) and unit (empty = automatic)"),
        ("m", "4", "Formula"),
        ("m", "5", "Choose and insert a signal, operators + - * / and parentheses"),
        ("m", "6", "Calculate and add as a new signal"),
        ("m", "7", "The new signal in the signal list, shown in the graph here"),
        ("m", "8", "Save or load calculations as a definition file (*.def)"),
        ("h", "Formula"),
        ("p", "Signals are written in curly braces, numbers directly (decimal point or comma). Allowed are + - * /, "
              "parentheses and signs; multiplication and division before addition and subtraction. Examples:"),
        ("b", "{Current} * {Voltage}  (power, unit A*V becomes W)"),
        ("b", "{Current} * {Voltage} / 1000  (in kW, unit entered by hand: kW)"),
        ("b", "({U1} + {U2} + {U3}) / 3  (average of three signals)"),
        ("b", "{Power} * 0.25  (calculated signals can be used further)"),
        ("h", "Fourier analysis"),
        ("p", "With type \"Fourier analysis\" the dialog splits a signal into its harmonics. The result gets a freely "
              "chosen name and appears in the signal list like every calculated signal. Typical set-up: base signal in "
              "graph 1, harmonics in graph 2 - the markers in graph 1 select the oscillation(s) whose harmonics graph 2 "
              "shows as vertical bars."),
        ("img", "fourier", "Figure 20b: Fourier analysis - markers select the oscillation, bars show the harmonics"),
        ("m", "1", "Name of the result (free)"),
        ("m", "2", "Type: formula or Fourier analysis"),
        ("m", "3", "Base signal and window"),
        ("m", "4", "Harmonics (X = number) or frequency range (X = Hz), display share [%] or attenuation [dB]"),
        ("m", "5", "Frequency range from ... to ... Hz (to empty = half the sampling rate)"),
        ("m", "6", "Harmonics from ... to ... (1 to 15) and fundamental frequency f0 (auto or fixed in Hz)"),
        ("m", "7", "Calculate and add"),
        ("m", "8", "Graph 1: base signal, markers M1/M2 enclose one oscillation"),
        ("m", "9", "Graph 2: harmonics of this oscillation as bars (H1 = fundamental)"),
        ("b", "Numbering: harmonic 1 is the fundamental f0, harmonic n lies at n * f0. Example 50 Hz: H1 = 50 Hz, "
              "H3 = 150 Hz, H5 = 250 Hz. f0 = auto takes the strongest frequency (without DC)."),
        ("b", "Display: share [%] = amplitude of the harmonic in percent of the sum of all harmonics (sum 100 %): pure sine "
              "H1 = 100 %, all others 0; with harmonics H1 < 100 %. Attenuation [dB] = 20 * log10(A1 / An) relative to the "
              "fundamental: H1 = 0 dB, 20 dB = one tenth, 40 dB = one hundredth; missing harmonics 100 dB."),
        ("b", "Selection with the markers: if the markers are on and the base signal is in a graph, the bars show the "
              "oscillations (periods) whose middle lies between M1 and M2. Example: markers at 0.01 and 1.49 "
              "oscillations -> 1st oscillation; move them to 1.01 to 2.49 -> 2nd oscillation and so on. Several "
              "oscillations between the markers are evaluated together. Without markers: all oscillations."),
        ("b", "Markers apply to the base signal only: the graph with the Fourier result has no markers, \"Synchronous "
              "markers\" does not transfer them there and \"Link X axes\" skips this graph (its X axis is frequency or "
              "harmonic number). Moving the markers or zooming the base signal re-evaluates the Fourier analysis "
              "immediately; without markers the oscillations in the visible range of the base signal are used."),
        ("b", "Frequency range, display selectable: \"Bars at the harmonics\" (bars at all n * f0 between fmin and fmax, "
              "at most 50) or \"Spectrum (continuous)\" (line over all frequency lines). Display additionally "
              "\"Amplitude\" (peak in the unit of the signal); for the spectrum % and dB refer to the amplitude of the "
              "fundamental. The spectrum follows the markers too (one oscillation: resolution f0)."),
        ("b", "The analysis is stored as a formula, e.g. FFT({U_L1}; h=1..15; f0=auto; y=pct) or FFT({U_L1}; "
              "f=0..500; f0=auto; y=db). Older formulas with h=0.. are read as h=1.."),
        ("b", "Linear or logarithmic display: right-click into the graph > Axes: X logarithmic, Y logarithmic. Logarithmic axes show grid lines at 1 to 9 per decade (also in print, PDF and SVG)."),
        ("h", "Periodicity and table per period"),
        ("b", "Before the analysis MessGraph checks whether the signal is periodic (frequency or amplitude may change from "
              "oscillation to oscillation): at least 1 whole period, spread of the period duration at most 25 % and a "
              "similar waveform. Then only whole periods are analysed (no leakage), and every period separately."),
        ("b", "Zero crossings are not required: an alternating signal with an offset (e.g. speed 1500 +- 600 rpm in "
              "demo_lauf_*.csv) is divided at its rising crossings of the mean value. f0 comes from a sine fit with "
              "offset and trend, so it is accurate even with only 1 to 2 oscillations in the measurement; a linear "
              "trend is removed without distorting the oscillation. At least one whole oscillation is required."),
        ("b", "Tooltip of the result as a table: number of periods, current selection, row \"All\", \"Mean\"/\"Min\"/"
              "\"Max\" and every period (up to 30). Columns: start, duration, f, DC, A1 (amplitude of the fundamental), "
              "H1..Hn (shares), THD [%]. Double-click the result in the signal list (or \"Table...\") for the complete, "
              "scrollable table in its own window; \"Copy table\" copies it tab-separated."),
        ("h", "Demo data for the Fourier analysis"),
        ("b", "demo_fourier_netz_oberschwingungen.csv (50 Hz mains, rectifier current with harmonics 3, 5, 7 ...), "
              "demo_fourier_rechteck_saegezahn.csv, demo_fourier_frequenzrampe.csv (run-up 40 -> 60 Hz), "
              "demo_fourier_amplitude_wechselnd.csv (3rd harmonic from 0.5 s - compare with the markers), "
              "demo_fourier_nicht_periodisch.csv (not periodic), demo_fourier_ungleichmaessig.csv and demo_fourier.def."),
        ("h", "Definition file (*.def)"),
        ("p", "So that calculations need not be entered again after a restart, they can be stored in a definition "
              "file: Graph options > Save calculations (*.def)... or \"Save definition...\" in the calculation dialog. All "
              "calculated signals of all open files are saved:"),
        ("b", "the measurement file with path (absolute and relative to the .def) that holds the base signals,"),
        ("b", "for each signal name, unit, formula and comment,"),
        ("b", "plus title, author, comment and date of the definition."),
        ("p", "Load via Graph options > Load calculations (*.def)... or \"Load definition...\": the file browser shows *.def "
              "files, several can be selected at once. Measurement files not yet open are opened, then the signals "
              "are calculated (with their assigned DBC/A2L). If a measurement file was moved, it is looked for "
              "relative to the .def. If open files contain all signals used (e.g. another run with the same "
              "structure), a dialog asks where the formulas should go: into the stored file, into the open files or "
              "both. Calculated signals of the same name are replaced, measured signals "
              "never. The .def is a readable text file (JSON) and can also be edited by hand. Example: "
              "demo_data/demo_berechnung.def."),
        ("h", "Good to know"),
        ("b", "If the signals have different time axes (common with MF4), all are interpolated linearly onto the time "
              "axis of the first signal of the formula; outside its range gaps appear. The message names the "
              "interpolated signals."),
        ("b", "Division by 0 gives a gap instead of an infinite value."),
        ("b", "Edit changes name, unit or formula; graphs with the signal show the new values at once. When renaming, "
              "references in other formulas are updated. A signal still used in another formula can only be "
              "deleted after that formula is changed or deleted."),
        ("b", "The formulas are saved with the view and recalculated when loading, also after reloading with a "
              "changed downsampling setting."),
    ]),
    ("Comparing files", [
        ("p", "Several measurements with the same or a similar structure, such as several test runs, can be compared "
              "signal by signal as a table: one row per signal and statistic, one column per file. Open it with the "
              "\"Compare files...\" button in the toolbar or from the File menu. If files with a similar structure are "
              "loaded, the status line points this out."),
        ("img", "vergleich", "Figure 21: three test runs compared"),
        ("m", "1", "Files with their share of matching signal names (header)"),
        ("m", "2", "Select similar, All, None"),
        ("m", "3", "Statistics avg, min, max, each selectable"),
        ("m", "4", "Signal search, All/None for the filtered list, common signals only"),
        ("m", "5", "Tick the signals to compare"),
        ("m", "6", "Calculate, copy, save as CSV"),
        ("m", "7", "Result: rows signal [unit] and statistic, columns files"),
        ("m", "8", "Open the window"),
        ("m", "9", "Tolerance in % per signal"),
        ("m", "10", "Red row: deviation beyond the tolerance, deviating value in red"),
        ("h", "Similarity"),
        ("p", "Files are compared by their signal names. The percentage after each file is its share of names shared "
              "with the other selected files. From 50 % files count as similar. \"Select similar\" picks the largest "
              "group of similar files and suggests up to 20 common signals. Every file can still be ticked or "
              "unticked freely."),
        ("h", "Signals and statistics"),
        ("b", "Signals not present in all selected files show \"(in 2 of 3 files)\"; the table then shows \"-\" for "
              "the missing file."),
        ("b", "avg is the mean of all valid values, min and max the smallest and largest value, each over the whole "
              "recording. Gaps (empty cells, NaN) do not count."),
        ("b", "MF4 channels are read in full resolution for this, even if they are not displayed yet. For CSV and "
              "Parquet the loaded data is used. If a Parquet file was reduced while reading, the value carries a * "
              "(with min/max downsampling, min and max still stay exact)."),
        ("b", "The calculation runs in the background with a progress display and can be cancelled."),
        ("h", "Tolerance in %"),
        ("p", "The % column next to the signal name takes a tolerance per signal, e.g. 4 or 2.5. If a file value "
              "deviates by more than this percentage, the row of that statistic gets a red background, and the "
              "deviating value and the signal name are written in red. The status line counts the affected rows."),
        ("b", "The reference is the median of all file values of the statistic, so a single outlier stands out "
              "without dragging the other files along. With exactly two files the reference is the other value."),
        ("b", "If the reference is 0, every value other than 0 counts as a deviation."),
        ("b", "Empty field: no check. Tolerances are kept per signal name for the next start and appear in CSV and "
              "clipboard together with the \"Deviation\" column (deviating files). In the table the unit follows "
              "the signal name; in the export it has its own column."),
        ("h", "Passing it on"),
        ("p", "\"Copy to clipboard\" stores the table tab-separated for pasting straight into Excel. \"Save CSV\" "
              "writes it with semicolons. With the German interface the decimal comma is used, otherwise the point. "
              "The selected statistics are kept for the next start."),
    ]),
    ("Print, export and report", [
        ("p", "The context menu of a graph (right-click) offers three functions under \"Print and export\". The visible "
              "section is printed and exported as shown on screen: zoom, markers, limit lines, custom colours, right Y "
              "axis and the position of the legend. Hidden signals are left out. The output is vector graphics in the "
              "colours of the light appearance."),
        ("img", "drucken", "Figure 22: printing or exporting all graphs, legend top right"),
        ("m", "1", "Output: printer, PDF file or SVG vector graphic"),
        ("m", "2", "Orientation: automatic, portrait or landscape"),
        ("m", "3", "Paper: DIN A0 to A6"),
        ("m", "4", "Target file (not for the printer)"),
        ("m", "5", "Run"),
        ("m", "6", "Legend, here top right (position selectable by right-click)"),
        ("h", "Print / export this graph"),
        ("p", "The graph that was right-clicked fills one page of the chosen size."),
        ("h", "Print / export all graphs"),
        ("p", "All graphs with signals are arranged on the chosen DIN page: in the columns of the matrix if one is set, "
              "otherwise one below the other. Each graph stays at least about 5 cm high (more on larger paper); if not "
              "all fit on one page, further pages follow. \"Automatic\" chooses landscape for one or two rows of "
              "graphs, otherwise portrait. Fonts and lines grow with the paper size."),
        ("b", "Printer: the PDF is sent to the default printer (Windows: via the PDF program, Linux/macOS: lp or lpr). "
              "If that fails, the message says where the PDF is."),
        ("b", "PDF file: one file with page numbers."),
        ("b", "SVG vector graphic: one file per page (name.svg, with several pages name_1.svg, name_2.svg ...), for "
              "further editing e.g. in Inkscape or Office."),
        ("h", "Create report as PDF"),
        ("p", "The report combines all graphs in one document: cover page with title, author, date and files, table of "
              "contents, an overview chapter (comment, measurement files, settings, list of graphs) and one chapter "
              "per graph with the graphic and tables:"),
        ("b", "Y axes of the report graphics (PDF and HTML): the maximum lies at least 10 % above the largest, the "
              "minimum at least 10 % below the smallest value of all displayed signals (per axis, within the visible "
              "X range; limit lines count too). Example 396 to 400 V: axis 356.4 to 440 V. If an extreme value is 0, "
              "10 % of the span is used. Printing and exporting graphs keep the section shown in the program."),
        ("b", "Signal legend directly below the graphic: colour and name of each curve, in up to three columns "
              "depending on name length, continued on the next page for very many curves. In the report the graphic "
              "itself has no legend, so it stays readable with many curves."),
        ("b", "Signals: file, unit and the values selected in the dialog: minimum, maximum, average and drift "
              "(regression) over all data. Default: all four; the choice is remembered. If no value is selected, "
              "the report contains no signal tables."),
        ("b", "Marker measurement (if markers are active): X1, X2, value 1, value 2, delta X, delta Y, drift."),
        ("b", "Limits and forecast (if Y min or Y max is set), with target time and target time status; signals with a "
              "violated target time have red rows, their graph a faint red background."),
        ("p", "The dialog takes the title, author, a general comment and a separate comment for each graph. The "
              "general comment appears in the overview chapter, a graph's comment in its chapter below the "
              "graphic and signal legend. Both belong to the view and are saved with it; author, paper and output stay in the settings."),
        ("h", "Dynamic report (HTML)"),
        ("p", "Besides the fixed PDF there is a dynamic report as an HTML file. In the report dialog, \"Report\" "
              "chooses between \"PDF and dynamic (HTML)\" (default), \"PDF (fixed)\" and \"Dynamic (HTML)\"; both "
              "files get the same name with .pdf or .html. The HTML file opens in any browser, needs no internet "
              "and can be passed on."),
        ("p", "It has the same content as the PDF: report details, table of contents at the side, overview and for "
              "each graph the graphic, signal legend, comment and tables. In addition a signal can be highlighted:"),
        ("b", "Click a curve in the graph, an entry in the signal legend or a row of the value tables: this signal "
              "keeps its colour (curve slightly bolder, row and entry marked), all other curves, entries and rows "
              "of the chapter turn light grey."),
        ("b", "Ctrl-click (or Shift-click) adds further signals or removes them again."),
        ("b", "Clicking the selected signal again, \"Show all\" or Esc clears the highlight."),
        ("p", "Each chapter is highlighted on its own. Printing the HTML file prints it as it currently looks."),
        ("h", "Position of the legend"),
        ("p", "Right-clicking the legend of a graph opens the choice of position: top left, top centre, top right, "
              "bottom left, bottom centre or bottom right. The same choice is also in the graph's context menu. The "
              "position stays when the graphs are rebuilt, is saved with the view and is used for printing, export "
              "and the report. Clicking a legend entry hides and shows the signal on screen."),
    ]),
    ("Downsampling", [
        ("p", "Very long measurements from MF4 and Parquet can contain several million values per signal. "
              "Downsampling reduces them while reading, saves memory and keeps work smooth. Setting: "
              "File > Downsampling... The choice is kept for the next start and is part of the view. CSV files are "
              "not reduced."),
        ("h", "Mode"),
        ("b", "Off: full resolution, every value is kept."),
        ("b", "Automatic (default): only signals with more values than the threshold (default 2,000,000) are "
              "reduced to about the target count (default 500,000), always with min/max per block. Shorter signals "
              "stay unchanged."),
        ("b", "Manual: choose the method and factor or time grid yourself; applies to every signal."),
        ("h", "Methods"),
        ("b", "Min/max per block: for each block of n values the minimum and maximum are kept at their true time. "
              "Peaks and outliers stay visible and measurable. Recommended for most measurements."),
        ("b", "Mean per block: one mean per block. Smooths noise like a low-pass filter; short peaks are weakened."),
        ("b", "Every n-th value: fastest, but can lose short events. Good for slow, smooth signals."),
        ("b", "Fixed time grid: mean per time interval (e.g. 0.01 s). Gives an even grid, useful for comparing "
              "signals with different sample rates. Intervals without values stay gaps."),
        ("h", "Applying"),
        ("p", "\"Apply\" affects files opened afterwards. \"Apply and reload loaded files\" reloads open MF4 and "
              "Parquet files; graphs, names, colours and markers stay. When a reduced signal is added, the status "
              "line shows the count before and after, and the file's detection info shows the setting."),
        ("h", "Good to know"),
        ("b", "Marker measurements (value 1, value 2, delta, drift) use the reduced data. For exact values of "
              "individual samples, switch downsampling off and reload."),
        ("b", "Independently of this, MessGraph always reduces only the visible section when drawing; zooming in "
              "shows all available values."),
    ]),
    ("Resizing the window areas", [
        ("p", "Narrow splitters separate the areas (figure 1, number 5, and figure 6, number 5). They change colour "
              "when the mouse is over them."),
        ("b", "Vertical splitter to the right of the file list: drag left or right to change the width of the file "
              "list and thereby of the graphs."),
        ("b", "Horizontal splitter above the value display (visible with markers): drag up to enlarge the value "
              "display, down to enlarge the graphs."),
        ("p", "Minimum sizes prevent an area from disappearing. The sizes are kept for the next start and are part "
              "of a saved view."),
    ]),
    ("Projects and views", [
        ("p", "The arrangement of signals and graphs, calculations, databases and all other settings can be saved as "
              "a project (extension .mgproj) and reused later."),
        ("img", "ansicht", "Figure 23: saving a project"),
        ("m", "1", "File menu with the project commands"),
        ("m", "2", "Recent projects"),
        ("m", "3", "Project name and comment"),
        ("m", "4", "Project file (.mgproj)"),
        ("m", "5", "Save"),
        ("h", "What a project contains"),
        ("b", "measurement files with path (absolute and relative to the project file), per file the databases (DBC, "
              "ARXML, A2L, CDD with channel assignment and conversion option) and a user-defined ASCII structure,"),
        ("b", "calculated signals with formula, unit and comment,"),
        ("b", "matrix and graphs: title, signals, colours, right axis, limits, legend position, comments, marker "
              "positions,"),
        ("b", "options: couple X axes, markers, synchronous, date axis, colour scheme, font size, size of the window "
              "areas, downsampling, general report comment,"),
        ("b", "dialog settings: report and export (paper, signal table values, PDF/HTML, title, author), file "
              "comparison (values, tolerance), definition files, last used databases and automatic decoding, ASCII "
              "template,"),
        ("b", "search text and target graph as well as project name, comment and creation date."),
        ("p", "Personal settings such as language or last used folder are not part of the project."),
        ("h", "Saving a project"),
        ("p", "File > \"Save project as...\" asks for project name, comment and project file and shows what will be "
              "saved. File > \"Save project\" writes to the open project without asking (the first time like "
              "\"save as\"). The project name appears in the title bar."),
        ("h", "Opening a project"),
        ("p", "File > \"Open project...\" or \"Recent projects\" replaces the current state: files are loaded, "
              "databases applied, signals calculated and the graphs restored. A project file can also be passed at "
              "start: main.py Pruefstand3.mgproj."),
        ("p", "If the project folder is moved or passed on together with measurement data and databases, MessGraph "
              "finds the files again: first at the stored location, then relative to the project file, then by name "
              "next to the project file. Anything missing is named in the status line."),
        ("p", "\"Close project\" closes all files and starts empty."),
        ("h", "Transferring settings to other files"),
        ("p", "Opening a project or loading a view always opens the saved files. When a new measurement of the same "
              "structure arrives (next run, other device under test), File > \"Transfer settings to other "
              "files...\" transfers the evaluation to that file:"),
        ("b", "Source: \"Current state\", a saved view (.mgraph) or a project (.mgproj)."),
        ("b", "Assignment: for each saved file with graphs, calculations, databases or ASCII structure the target file "
              "is chosen: an open file or \"Choose other file...\". The open file with the most matching signal "
              "names is suggested. The column \"Signals in target\" shows how many of the displayed signals the "
              "target file has (calculated signals count too)."),
        ("b", "Transferred are graphs with title, signals, colours, right axis, limits, legend, comment and markers, "
              "matrix, options, calculated signals, databases (DBC, ARXML, A2L, CDD) and the ASCII structure. "
              "Signals are matched by name; missing ones are named in the status line."),
        ("b", "\"Keep previous files open as well\" keeps the source files open (without graphs), e.g. for a "
              "comparison. With a project as source its settings (report, export, comparison, downsampling ...) can "
              "be taken over too."),
        ("b", "Several saved files can be assigned to the same target file; their settings are merged."),
        ("p", "The result is a new evaluation: \"Save project\" asks for a new name, the source project stays "
              "unchanged. \"Load calculations (*.def)\" still transfers the formulas only."),
        ("h", "Saving and loading views"),
        ("p", "A view (extension .mgraph) is the lean form: files, databases, calculations, graphs and options, "
              "without project name and without the dialog settings. Views from older versions remain readable."),
        ("h", "Saving"),
        ("p", "\"File > Save view...\" asks for the file name; the last one used is suggested."),
        ("h", "Loading"),
        ("p", "\"File > Load view...\" selects a .mgraph file in the file browser. The current view is replaced "
              "and the files are loaded again. If a file is missing at the saved location, MessGraph looks for it "
              "relative to the view file, so folders with view and data can be passed on. Missing files or signals "
              "are listed in the status line."),
        ("h", "Last view on start"),
        ("p", "With \"File > Restore last view on start\" MessGraph saves the state on exit and "
              "restores it on the next start (not when files are passed on the command line)."),
    ]),
    ("Help, PDF and screenshots", [
        ("h", "Language"),
        ("p", "Interface and manual are available in German, English, Thai and Chinese (Mandarin, simplified characters). Switch on the right of the menu bar "
              "with \"Language\". All labels, messages and the manual change at once; loaded files, graphs, colours "
              "and settings are kept. The choice also applies to the PDF and is remembered for the next start."),
        ("p", "The detection details of a file (Detection, hover here) and the hints in the file list follow the "
              "selected language, also for files opened in another language. Thai only switches the interface texts and the manual; file and signal names, units and values stay as they are. "
              "This needs a font with Thai AND Latin characters, for example Leelawadee UI or Tahoma (Windows) or "
              "fonts-tlwg such as Loma (Linux). Thai-only fonts like Noto Sans Thai are skipped because they lack Latin "
              "letters; without a suitable font Thai cannot be selected. The PDF embeds the font. The included "
              "illustrations show the German interface; \"Create screenshots\" captures it in the selected language."),
        ("p", "Chinese likewise needs a font with Chinese AND Latin characters, for example Microsoft YaHei (included "
              "with Windows), DengXian or SimHei, on Linux fonts-wqy-microhei, fonts-wqy-zenhei or Noto Sans CJK, on "
              "macOS PingFang. File and signal names, units and values stay unchanged here too; without the font "
              "Chinese cannot be selected."),
        ("img", "hilfe", "Figure 24: help window"),
        ("m", "1", "Language switch at the right edge of the menu bar"),
        ("m", "2", "Save help as PDF"),
        ("m", "3", "Create screenshots"),
        ("m", "4", "Table of contents"),
        ("m", "5", "Image with numbered markers, explanation below"),
        ("m", "6", "Help menu: \"Show help\" opens this window"),
        ("p", "The manual is a separate window above the main window: \"Help > Show help\" opens it, the cross in "
              "its title bar closes it. It can be moved and resized; graphs and value display stay usable behind it."),
        ("h", "Manual as PDF"),
        ("p", "\"Save as PDF...\" in the help window or \"Help > Save help as PDF...\" creates an A4 "
              "manual with narrow margins, table of contents, page numbers and screenshots in the chosen language."),
        ("h", "Screenshots"),
        ("p", "The manual contains ten images with numbered markers; a list below each image explains the numbers. "
              "Redrawn illustrations of the program window are included (caption with the note \"illustration\")."),
        ("p", "\"Create screenshots\" replaces them with real captures of your window: the program uses the example "
              "data to set up the situations shown, adds the same markers and captures the window. This takes a few "
              "seconds; please do not operate the program meanwhile. The previous view returns afterwards. The "
              "captures are stored in the folder .messgraph_hilfe_bilder in the home folder and take precedence over "
              "the included images. The databases image needs demo_data/demo.mf4; open menus (figure 9) cannot be "
              "captured automatically."),
    ]),
    ("Troubleshooting", [
        ("h", "Common messages"),
        ("b", "\"MF4 needs asammdf\", \"Parquet needs pyarrow\", \"DBC decoding needs canmatrix\": "
              "run pip install -r requirements.txt."),
        ("b", "\"No data block with numeric values found.\": the CSV holds no recognisable "
              "numbers."),
        ("b", "Wrong columns or X axis: hover \"Detection\" in the file entry to see what was detected."),
        ("b", "X axis in seconds up to millions: the file spans several days; the date/time axis is clearer."),
        ("h", "Error log"),
        ("p", "Every loading or operating error is written with its full cause to messgraph_fehler.log in the home "
              "folder. The status line shows the path. This file helps to find the problem."),
        ("h", "Resetting settings"),
        ("p", "Appearance, folders, window sizes and language are stored in .messgraph.json in the home folder. "
              "Deleting the file restores the defaults."),
    ]),
]
