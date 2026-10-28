"""One palette, one set of figure settings and one way to title and save every report figure.

The design-family hues are the package's own (`avalanche_research.palette.MECHANISM_COLORS`), with the rule before
ACP-285 in grey. A sweep manifest may give any column a label, a unit and a display scale, which replace the defaults
below for that run (`set_labels`).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from ..palette import MECHANISM_COLORS  # noqa: E402

INK, INK2, MUTED, GRID, PAPER, TINT = "#1b1b1b", "#4f545c", "#8a8f98", "#e6e7ea", "#ffffff", "#f5f6f7"
MODEL_BLUE = "#3566a3"
REWARD = "#b84055"  # rewards, failures and falls

DEFAULT_FAMILIES = {  # family key: (label, colour)
    "ramp": ("ACP-285 ramp", MECHANISM_COLORS["ACP-285 settings"]),
    "quadratic": ("Quadratic curve", MECHANISM_COLORS["Quadratic curve"]),
    "tenure": ("Tenure boost", MECHANISM_COLORS["Tenure boost"]),
    "before": ("Rule before ACP-285", "#6b7079"),
}
EXTRA_FAMILY_COLOURS = ["#b85c00", "#237a57", "#3566a3", "#b84055"]
SCENARIO_RAMP = ["#e3a76f", "#c97a30", "#9a4f12", "#5c2c05"]  # one hue, light to dark, for ordered scenario values
DEFAULT_FEATURES = {  # column: (label, unit, scale)
    "target_min_rate": ("Floor of the reward rate", "%", 100),
    "boost_max": ("Full-tenure boost", "% of reward", 100),
    "exponent": ("Duration exponent", "", 1),
    "renewal_response": ("Renewal response", "log-odds per point of reward gap", 1),
    "entry_response": ("Entry response", "log-rate per point of reward gap", 1),
    "yield_pp": ("Outside yield", "% a year", 1),
    "outside_yield_pp": ("Outside yield", "% a year", 1),
    "market_condition": ("Market condition", "", 1),
    "network_growth": ("Network growth", "", 1),
}
DEFAULT_PHRASES = {  # how a setting reads inside a sentence, followed by its value
    "target_min_rate": "a reward-rate floor of",
    "boost_max": "a full-tenure boost of",
    "exponent": "a duration exponent of",
}

FAMILY_STYLE = dict(DEFAULT_FAMILIES)
FEATURE_STYLE = dict(DEFAULT_FEATURES)
PHRASE = dict(DEFAULT_PHRASES)

SEQUENTIAL = LinearSegmentedColormap.from_list("bcrg_seq", [PAPER, "#d6e0ee", "#8fa9cf", MODEL_BLUE, "#1d3f6e"])
PASS_FAIL = LinearSegmentedColormap.from_list("bcrg_pass", [REWARD, "#f1d3d9", PAPER, "#d6e0ee", MODEL_BLUE])
DIVERGING = LinearSegmentedColormap.from_list("bcrg_div", [REWARD, "#f3d9de", PAPER, "#d6e0ee", MODEL_BLUE])

RC = {
    "font.family": ["Open Sans", "Noto Sans", "DejaVu Sans"], "font.size": 8.5, "axes.titlesize": 9,
    "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.labelsize": 8, "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5, "legend.fontsize": 8, "figure.facecolor": PAPER, "axes.facecolor": PAPER,
    "savefig.facecolor": PAPER, "axes.edgecolor": MUTED, "axes.linewidth": 0.7, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "text.color": INK, "axes.spines.top": False,
    "axes.spines.right": False, "legend.frameon": False, "svg.fonttype": "none",
}


def apply() -> None:
    """Set the house figure settings for this process."""
    plt.rcParams.update(RC)


def set_labels(features: dict | None = None, families: dict | None = None, phrases: dict | None = None) -> None:
    """Reset labels to the defaults, then apply a manifest's labels.

    `features` maps a column to {"label", "unit", "scale"}, `families` maps a family key to {"label", "colour"} and
    `phrases` maps a setting to the words that come before its value in a sentence.
    """
    FAMILY_STYLE.clear()
    FAMILY_STYLE.update(DEFAULT_FAMILIES)
    FEATURE_STYLE.clear()
    FEATURE_STYLE.update(DEFAULT_FEATURES)
    PHRASE.clear()
    PHRASE.update(DEFAULT_PHRASES)
    for name, value in (features or {}).items():
        old = FEATURE_STYLE.get(name, (name.replace("_", " ").capitalize(), "", 1))
        FEATURE_STYLE[name] = (value.get("label", old[0]), value.get("unit", old[1]), value.get("scale", old[2]))
    for name, value in (families or {}).items():
        old = FAMILY_STYLE.get(name, (str(name), None))
        FAMILY_STYLE[name] = (value.get("label", old[0]), value.get("colour", old[1]))
    PHRASE.update(phrases or {})


# Words ---------------------------------------------------------------------------------------------------------------


def family_label(f, mid=False):
    """The design's name, lower-cased after its first word when it sits inside a sentence."""
    label = FAMILY_STYLE.get(f, (str(f), None))[0]
    if not mid:
        return label
    return f"the {label[0].lower()}{label[1:]}" if label[1:2].islower() else f"the {label}"


def family_colour(f, families):
    if FAMILY_STYLE.get(f, (None, None))[1]:
        return FAMILY_STYLE[f][1]
    extras = [x for x in families if not FAMILY_STYLE.get(x, (None, None))[1]]
    return EXTRA_FAMILY_COLOURS[extras.index(f) % len(EXTRA_FAMILY_COLOURS)]


def feature_label(name, with_unit=True):
    label, unit, _ = FEATURE_STYLE.get(name, (name.replace("_", " ").capitalize(), "", 1))
    return f"{label}, {unit}" if with_unit and unit else label


def feature_scale(name):
    return FEATURE_STYLE.get(name, ("", "", 1))[2]


def feature_value(name, v):
    """A setting as the reader sees it, such as 7.5% for a floor of 0.075."""
    label, unit, scale = FEATURE_STYLE.get(name, (name, "", 1))
    if isinstance(v, str):
        return v
    x = v * scale
    text = f"{x:.3g}" if abs(x) >= 0.01 or x == 0 else f"{x:.2g}"
    return f"{text}%" if unit.startswith("%") else text


def setting_phrase(name):
    return PHRASE.get(name, f"{feature_label(name, False).lower()} of")


def scenario_text(axis, v):
    if isinstance(v, str):
        return f"{feature_label(axis, False)} {v}"
    label, unit, scale = FEATURE_STYLE.get(axis, (axis, "", 1))
    return f"{label} {v * scale:g}{'%' if unit.startswith('%') else ''}"


def fmt_horizon(h):
    return f"{h} days" if not isinstance(h, str) else h


# Titles and files ----------------------------------------------------------------------------------------------------


def headline(fig, title, subtitle):
    """The finding as a bold left-aligned title above the figure, and below it a line that says what is shown."""
    fig.canvas.draw()
    h = fig.get_figheight()
    top = fig.get_tightbbox(fig.canvas.get_renderer()).y1
    y = (top + 0.1) / h
    width = max(60, int(fig.get_figwidth() * 15))
    subtitle = "\n".join(textwrap.fill(part, width) for part in subtitle.split("\n"))
    sub = fig.text(0.0, y, subtitle, ha="left", va="bottom", fontsize=8, color=INK2, wrap=False)
    box = sub.get_window_extent(renderer=fig.canvas.get_renderer())
    y += box.height / fig.dpi / h + 0.06 / h
    fig.text(0.0, y, textwrap.fill(title, max(70, int(fig.get_figwidth() * 12))), ha="left", va="bottom",
             fontsize=11, weight="bold", color=INK)


def save(fig, folder: Path, name: str, data=None) -> list[Path]:
    """Write the figure as PNG at 200 dpi and SVG, and the drawn data as CSV when given."""
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for ext, kw in (("png", {"dpi": 200}), ("svg", {})):
        path = folder / f"{name}.{ext}"
        fig.savefig(path, bbox_inches="tight", pad_inches=0.1, **kw)
        written.append(path)
    plt.close(fig)
    if data is not None:
        path = folder / f"{name}.csv"
        data.to_csv(path, index=False)
        written.append(path)
    return written


def colour_values(frame, axis):
    """Each value of a scenario axis, in order, and its colour on the one-hue ramp."""
    vals = sorted(frame[axis].dropna().unique(), key=lambda v: (isinstance(v, str), v))
    ramp = SCENARIO_RAMP if len(vals) <= len(SCENARIO_RAMP) else [
        matplotlib.colors.to_hex(plt.get_cmap("copper_r")(0.25 + 0.7 * k / max(1, len(vals) - 1)))
        for k in range(len(vals))]
    return vals, dict(zip(vals, ramp))
