"""Zusammengefasste Graphbereiche in der Matrix (z. B. 4*3: 3, 3, 2+1, 1)."""
import pytest

from messgraph import plotexport, session
from messgraph.layout import (PlotLayout, format_layout, normalize_spans, parse_layout, parse_row)


@pytest.mark.parametrize("text, cols, expected", [
    ("3", 3, [1, 1, 1]), ("1", 3, [3]), ("2+1", 3, [2, 1]), ("1+2", 3, [1, 2]), ("", 2, [1, 1]),
    ("2", 4, [2, 2]), (" 1 + 1 + 2 ", 4, [1, 1, 2])])
def test_parse_row(text, cols, expected):
    assert parse_row(text, cols) == expected


@pytest.mark.parametrize("text", ["2", "2+2", "0", "a", "1+x", "4"])
def test_parse_row_invalid(text):
    with pytest.raises(ValueError):
        parse_row(text, 3)


def test_parse_layout_example_from_request():
    matrix, spans = parse_layout("4*3: 3, 3, 2+1, 1")
    assert matrix == (4, 3) and spans == [[1, 1, 1], [1, 1, 1], [2, 1], [3]]
    assert format_layout(matrix, spans) == "4*3: 3, 3, 2+1, 1"
    assert parse_layout("4*3") == ((4, 3), None) and parse_layout("4*3: 3; 3") == ((4, 3), None)
    assert parse_layout("2x2: 1") == ((2, 2), [[2], [1, 1]])            # fehlende Zeilen: Einzelgraphen
    assert parse_layout("") == (None, None)
    with pytest.raises(ValueError, match="3 Zeilenangaben"):
        parse_layout("2*3: 3, 3, 3")
    assert normalize_spans((2, 3), [[2, 2], [3]]) is None                 # ungültig: verworfen


def test_layout_cells_names_and_keeps_signals():
    lay = PlotLayout()
    lay.set_matrix((2, 2))
    for i, slot in enumerate(lay.slots):
        slot.signals.append(f"s{i}")
    lay.set_matrix((2, 2), [[2], [1, 1]])                                  # 4 -> 3 Graphen
    assert len(lay.slots) == 3 and lay.merged
    assert lay.cells() == [(0, 0, 2), (1, 0, 1), (1, 1, 1)]
    assert sorted(lay.signals()) == ["s0", "s1", "s2", "s3"]               # überzähliger Graph verteilt
    assert lay.target_names()[1:] == ["Graph 1 (Z1/S1-2)", "Graph 2 (Z2/S1)", "Graph 3 (Z2/S2)"]
    lay.set_matrix((2, 2))
    assert len(lay.slots) == 4 and not lay.merged


def test_session_roundtrip_spans():
    lay = PlotLayout()
    lay.set_matrix((4, 3), [[1, 1, 1], [1, 1, 1], [2, 1], [3]])
    data = session.build_session([], lay, {})
    assert data["spans"] == [[1, 1, 1], [1, 1, 1], [2, 1], [3]]
    restored, _missing = session.restore_layout(data, {})
    assert restored.spans == lay.spans and len(restored.slots) == 9
    data["spans"] = [[5]]                                                  # beschädigt: Einzelgraphen
    restored, _missing = session.restore_layout(data, {})
    assert restored.spans is None and len(restored.slots) == 12


def test_export_cells_follow_spans():
    pages = plotexport.layout_cells(9, (4, 3), 842, 595, margin=20, header=0, gap=10, min_h=50,
                                    spans=[[1, 1, 1], [1, 1, 1], [2, 1], [3]])
    cells = pages[0]
    assert len(pages) == 1 and [c[0] for c in cells] == list(range(9))
    single = cells[0][3]
    assert cells[6][3] == pytest.approx(2 * single + 10)                  # Zeile 3: zwei Spalten breit
    assert cells[8][3] == pytest.approx(3 * single + 20) and cells[8][1] == cells[0][1]
    assert cells[7][1] == pytest.approx(cells[2][1])                       # rechter Graph in Spalte 3
    pages = plotexport.layout_cells(9, (4, 3), 842, 595, margin=20, header=0, gap=10, min_h=200,
                                    spans=[[1, 1, 1], [1, 1, 1], [2, 1], [3]])
    assert [len(p) for p in pages] == [6, 3]                               # Zeilen werden nicht getrennt
