"""Berechnete Signale: Formeln mit + - * / und Klammern über Signale einer Datei.

Signale werden in geschweiften Klammern angegeben, z. B. {Strom} * {Spannung} oder ({U1} + {U2}) / 2.
Ausgewertet wird ohne eval: eigener Parser (rekursiver Abstieg). Haben die Signale unterschiedliche
Zeitachsen (MF4), werden sie linear auf die Zeitachse des ersten Signals der Formel interpoliert.
Sonderform Fourier-Analyse: FFT({Signal}; f=0..500) bzw. FFT({Signal}; h=0..15; f0=auto) -> Spektrum (fourier.py).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from . import fourier
from .data_model import Channel, Dataset, LoadError
from .i18n import t

MAX_COMPUTED = 10
OPERATORS = ["+", "-", "*", "/"]
_TOKEN = re.compile(r"\s*(?:(\{[^{}]*\})|(\d+(?:[.,]\d*)?(?:[eE][+-]?\d+)?|[.,]\d+(?:[eE][+-]?\d+)?)|([-+*/()]))")


class FormulaError(LoadError):
    """Formel ungültig oder nicht berechenbar (Text für den Nutzer)."""


@dataclass
class Node:
    kind: str            # num, sig, neg, op
    value: object = None # Zahl, Signalname oder Operator
    left: "Node | None" = None
    right: "Node | None" = None


def tokenize(text: str) -> list[tuple[str, str]]:
    tokens, pos = [], 0
    text = text.strip()
    while pos < len(text):
        match = _TOKEN.match(text, pos)
        if not match or match.end() == pos:
            raise FormulaError(t("Unerwartetes Zeichen an Stelle {pos}: {text}", pos=pos + 1, text=text[pos:pos + 10]))
        sig, num, op = match.groups()
        if sig is not None:
            name = sig[1:-1].strip()
            if not name:
                raise FormulaError(t("Leerer Signalname {}"))
            tokens.append(("sig", name))
        elif num is not None:
            tokens.append(("num", num.replace(",", ".")))
        else:
            tokens.append(("op", op))
        pos = match.end()
    return tokens


def parse(text: str) -> Node:
    if fourier.is_fft(text):                     # Fourier-Analyse: Knoten "fft" mit dem Signal als Kind
        try:
            spec = fourier.parse(text)
        except fourier.FourierError as exc:
            raise FormulaError(str(exc)) from None
        return Node("fft", spec, left=Node("sig", spec.signal))
    tokens = tokenize(text)
    if not tokens:
        raise FormulaError(t("Die Formel ist leer."))
    index = 0

    def peek():
        return tokens[index] if index < len(tokens) else (None, None)

    def take():
        nonlocal index
        index += 1
        return tokens[index - 1]

    def expr():
        node = term()
        while peek() in (("op", "+"), ("op", "-")):
            op = take()[1]
            node = Node("op", op, node, term())
        return node

    def term():
        node = factor()
        while peek() in (("op", "*"), ("op", "/")):
            op = take()[1]
            node = Node("op", op, node, factor())
        return node

    def factor():
        if peek() == ("op", "-"):
            take()
            return Node("neg", left=factor())
        if peek() == ("op", "+"):
            take()
            return factor()
        return primary()

    def primary():
        kind, value = peek()
        if kind == "num":
            take()
            return Node("num", float(value))
        if kind == "sig":
            take()
            return Node("sig", value)
        if (kind, value) == ("op", "("):
            take()
            node = expr()
            if peek() != ("op", ")"):
                raise FormulaError(t("Schließende Klammer fehlt."))
            take()
            return node
        if kind is None:
            raise FormulaError(t("Die Formel endet unerwartet."))
        raise FormulaError(t("Unerwartet: {token}", token=value))

    node = expr()
    if index != len(tokens):
        raise FormulaError(t("Unerwartet: {token}", token=tokens[index][1]))
    return node


def references(node: Node) -> list[str]:
    """Signalnamen in der Reihenfolge des ersten Auftretens."""
    out: list[str] = []

    def walk(n):
        if n is None:
            return
        if n.kind == "sig" and n.value not in out:
            out.append(n.value)
        walk(n.left)
        walk(n.right)
    walk(node)
    return out


def evaluate(node: Node, values: dict) -> np.ndarray | float:
    if node.kind == "num":
        return node.value
    if node.kind == "sig":
        return values[node.value]
    if node.kind == "neg":
        return -evaluate(node.left, values)
    a, b = evaluate(node.left, values), evaluate(node.right, values)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        if node.value == "+":
            return a + b
        if node.value == "-":
            return a - b
        if node.value == "*":
            return a * b
        result = np.divide(a, b)
        return np.where(np.isfinite(result), result, np.nan) if isinstance(result, np.ndarray) else (
            result if np.isfinite(result) else np.nan)


def guess_unit(node: Node, units: dict) -> str:
    """Einheit aus der Formel: gleiche Einheiten bei + und -, sonst Produkt bzw. Quotient der Einheiten."""
    def unit(n) -> str:
        if n.kind == "num":
            return ""
        if n.kind == "sig":
            return units.get(n.value, "")
        if n.kind == "fft" and n.value.scale != "amp":
            return "%" if n.value.scale == "pct" else "dB"   # Harmonische: Anteil bzw. Dämpfung
        if n.kind in ("neg", "fft"):
            return unit(n.left)
        a, b = unit(n.left), unit(n.right)
        if n.value in "+-":
            return a or b if (a == b or not a or not b) else f"{a}{n.value}{b}"
        if n.value == "*":
            return f"{a}*{b}" if a and b else a or b
        if not b:
            return a
        return f"{a or '1'}/{b}"
    text = unit(node)
    return {"V*A": "W", "A*V": "W"}.get(text, text)


def _channel_by_name(dataset: Dataset, name: str) -> Channel | None:
    return next((c for c in dataset.channels if c.name == name), None) or \
        next((c for c in dataset.channels if c.label == name), None) or \
        next((c for c in dataset.channels if name in c.aliases), None)


def compute(dataset: Dataset, name: str, unit: str, text: str, exclude: Channel | None = None) -> Channel:
    """Berechnet das Signal (lädt dazu nötige MF4-Kanäle). exclude: bisheriges Signal beim Bearbeiten."""
    name = name.strip()
    if not name or any(ch in name for ch in "{}"):
        raise FormulaError(t("Bitte einen Namen ohne geschweifte Klammern angeben."))
    if any(c.name == name and c is not exclude for c in dataset.channels):
        raise FormulaError(t("Ein Signal \"{name}\" gibt es in dieser Datei schon.", name=name))
    node = parse(text)
    names = references(node)
    if not names:
        raise FormulaError(t("Die Formel braucht mindestens ein Signal, z. B. {Strom} * {Spannung}."))
    channels = []
    for ref in names:
        channel = _channel_by_name(dataset, ref)
        if channel is None or channel is exclude:
            raise FormulaError(t("Signal nicht gefunden: {name}", name=ref))
        if not channel.loaded:
            channel.load()
        channels.append(channel)
    base = channels[0]
    if node.kind == "fft":                       # Spektrum statt Zeitverlauf: eigene X-Achse (Frequenz bzw. Ordnung)
        try:
            result = fourier.compute(base.x, base.y, base.x_unit, node.value)
        except fourier.FourierError as exc:
            raise FormulaError(str(exc)) from None
        y_unit = result.get("y_unit")                 # Harmonische: Anteil ohne Einheit
        out = Channel(name=name, unit=unit.strip() or (base.unit if y_unit is None else y_unit),
                      x_name=result["x_name"], x_unit=result["x_unit"],
                      source=dataset.path, x=result["x"], y=result["y"], x_epoch=None)
        out.formula = text.strip()
        out.ds_note = base.ds_note
        out.interpolated = []
        out.fourier = result["info"]
        out.plot_style = result.get("plot_style", "bar")   # Balken an den Harmonischen oder Spektrum (Linie)
        out.bar_width = result.get("bar_width", 0.6)
        out.fourier["signal"] = node.value.signal
        out.fourier["orders"] = list(result["info"]["shown"])
        return out
    x = np.array(base.x, dtype=np.float64)
    values, notes = {}, []
    for ref, channel in zip(names, channels):
        if channel.x.shape == x.shape and np.array_equal(channel.x, x):
            values[ref] = channel.y
        else:  # andere Zeitachse: auf die des ersten Signals interpolieren, außerhalb keine Werte
            values[ref] = np.interp(x, channel.x, channel.y, left=np.nan, right=np.nan)
            notes.append(ref)
        if (channel.x_epoch or 0) != (base.x_epoch or 0) and channel.x_epoch is not None and base.x_epoch is not None:
            values[ref] = np.interp(x, channel.x + (channel.x_epoch - base.x_epoch), channel.y, left=np.nan, right=np.nan)
    result = evaluate(node, values)
    y = np.full(x.shape, float(result)) if np.isscalar(result) else np.asarray(result, dtype=np.float64)
    units = {ref: ch.unit for ref, ch in zip(names, channels)}
    out = Channel(name=name, unit=unit.strip() or guess_unit(node, units), x_name=base.x_name, x_unit=base.x_unit,
                  source=dataset.path, x=x, y=y, x_epoch=base.x_epoch)
    out.formula = text.strip()
    reduced = [ch.ds_note for ch in channels if ch.ds_note]
    out.ds_note = reduced[0] if reduced else ""
    out.interpolated = notes
    return out


def computed(dataset: Dataset) -> list[Channel]:
    return [c for c in dataset.channels if getattr(c, "formula", "")]


def add_or_replace(dataset: Dataset, channel: Channel, previous: Channel | None = None) -> Channel:
    """Neues Signal anhängen oder das bisherige an Ort und Stelle ersetzen (Graphen behalten es)."""
    if previous is not None and previous in dataset.channels:
        for field_name in ("name", "unit", "x_name", "x_unit", "x", "y", "x_epoch", "ds_note", "formula", "interpolated",
                           "note"):
            setattr(previous, field_name, getattr(channel, field_name))
        previous.fourier = getattr(channel, "fourier", None)
        previous.plot_style = getattr(channel, "plot_style", "line")
        previous.bar_width = getattr(channel, "bar_width", 0.6)
        previous._regression = None
        return previous
    if len(computed(dataset)) >= MAX_COMPUTED:
        raise FormulaError(t("Höchstens {count} berechnete Signale je Datei.", count=MAX_COMPUTED))
    dataset.channels.append(channel)
    return channel


def dependents(dataset: Dataset, name: str) -> list[Channel]:
    """Berechnete Signale, deren Formel das Signal name verwendet."""
    out = []
    for channel in computed(dataset):
        try:
            if name in references(parse(channel.formula)):
                out.append(channel)
        except FormulaError:
            continue
    return out


def rename_references(dataset: Dataset, old: str, new: str) -> None:
    for channel in dependents(dataset, old):
        channel.formula = re.sub(r"\{\s*" + re.escape(old) + r"\s*\}", "{" + new + "}", channel.formula)
