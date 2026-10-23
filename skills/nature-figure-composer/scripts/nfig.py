#!/usr/bin/env python3
"""nfig — Nature-style multi-panel figures with matplotlib.

Copy this file next to the figure scripts (e.g. paper_figures/src/nfig.py) so they stay runnable
without the skill.

    import nfig
    nfig.use_style()
    pal = nfig.Palette.load_or_build("paper_figures/figure_style.json",
                                     proposed=["Ours"], baselines=["BaseA", "BaseB"],
                                     references=["Oracle"])
    fig, axd = nfig.figure("double", 110, mosaic="aab;cde")
    axd["b"].plot(x, y, **pal.line("Ours"))
    nfig.shared_legend(fig, pal.handles(["Ours", "BaseA", "BaseB"]))
    nfig.label_panels(fig, axd)            # last, after everything else is drawn
    nfig.save(fig, "paper_figures/fig2")         # fig2.pdf / .svg / .png + QA report

Specs (Nature research figure guide): width 89 mm (single) / 183 mm (double), height <= 170 mm,
Arial/Helvetica 5-7 pt, panel labels 8 pt bold lowercase upright, fonts embedded as TrueType
(pdf.fonttype 42), raster images >= 300 dpi, axis lines + ticks, units in parentheses,
no gridlines / shadows, colour-blind-safe colours (Wong 2011), no coloured text.
Never save with bbox_inches="tight": it changes the width away from the column size.
"""
from __future__ import annotations

import colorsys
import json
import math
import sys
import warnings
from pathlib import Path

import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from cycler import cycler
from matplotlib import colors as mcolors
from matplotlib import font_manager
from matplotlib.image import AxesImage
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch, Rectangle
from matplotlib.text import Text

MM = 1 / 25.4                      # inches per mm
WIDTHS_MM = {"single": 89.0, "onehalf": 120.0, "double": 183.0}
ONEHALF_RANGE_MM = (120.0, 136.0)
MAX_HEIGHT_MM = 170.0
FONT_MIN_PT, FONT_MAX_PT, LABEL_PT = 5.0, 7.0, 8.0
MIN_LINE_PT = 0.25
MIN_DPI = 300

# Wong (2011) colour-blind-safe hues, slightly desaturated. Each colour has one meaning per paper.
COLORS = {
    "accent": "#D0601F",   # proposed method / the key result (muted vermillion)
    "blue": "#2B6CA3",     # second highlighted condition, e.g. strongest competitor
    "sky": "#6AADD5",
    "orange": "#D99A2B",
    "green": "#2A9073",
    "purple": "#B9779F",
    "black": "#000000",
}
GREYS = ["#404040", "#9A9A9A", "#BDBDBD", "#6E6E6E"]   # baselines, most important first; lightness
                                                        # kept away from accent / blue for grey print
GREY_FAINT = "#E5E5E5"
CATEGORICAL = [COLORS[k] for k in ("blue", "accent", "sky", "green", "orange", "purple")]
MARKERS = ["o", "s", "^", "D", "v", "P", "X", "<", ">", "h"]
LINESTYLES = ["-", "--", "-.", ":", (0, (5, 1, 1, 1, 1, 1)), (0, (1, 2))]
SEQ_CMAP = "viridis"               # perceptually uniform; never jet / rainbow
DIV_CMAP = "RdBu_r"                # centre it on the meaningful reference (TwoSlopeNorm)

_FONT_FAMILIES = ["Arial", "Helvetica", "Liberation Sans", "Nimbus Sans", "TeX Gyre Heros"]


# ---------------------------------------------------------------- style

def use_style(base_pt: float = 7, small_pt: float = 6, font: str | None = None) -> str:
    """Apply the house style. Returns the font family actually used."""
    families = ([font] if font else []) + _FONT_FAMILIES
    family = _first_available(families)
    if family is None:
        warnings.warn("Arial/Helvetica not found; falling back to DejaVu Sans. "
                      "Install Arial or Liberation Sans for submission files.")
        family = "DejaVu Sans"
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": [family, "DejaVu Sans"],
        "font.size": base_pt,
        "axes.titlesize": base_pt,
        "axes.labelsize": base_pt,
        "xtick.labelsize": small_pt,
        "ytick.labelsize": small_pt,
        "legend.fontsize": small_pt,
        "legend.title_fontsize": small_pt,
        "figure.titlesize": base_pt,
        "mathtext.fontset": "custom",
        "mathtext.rm": family,
        "mathtext.it": f"{family}:italic",
        "mathtext.bf": f"{family}:bold",
        "mathtext.sf": family,
        "mathtext.default": "regular",
        "axes.linewidth": 0.5,
        "axes.edgecolor": "black",
        "axes.labelcolor": "black",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "axes.titlepad": 3,
        "axes.labelpad": 2,
        "axes.prop_cycle": cycler(color=CATEGORICAL),
        "axes.unicode_minus": True,
        "xtick.color": "black",
        "ytick.color": "black",
        "xtick.direction": "out",
        "ytick.direction": "out",
        "xtick.major.size": 2.5,
        "ytick.major.size": 2.5,
        "xtick.minor.size": 1.5,
        "ytick.minor.size": 1.5,
        "xtick.major.width": 0.5,
        "ytick.major.width": 0.5,
        "xtick.minor.width": 0.4,
        "ytick.minor.width": 0.4,
        "xtick.major.pad": 1.5,
        "ytick.major.pad": 1.5,
        "lines.linewidth": 1.0,
        "lines.markersize": 3,
        "lines.markeredgewidth": 0.5,
        "patch.linewidth": 0.5,
        "hatch.linewidth": 0.5,
        "errorbar.capsize": 1.5,
        "boxplot.boxprops.linewidth": 0.5,
        "boxplot.whiskerprops.linewidth": 0.5,
        "boxplot.capprops.linewidth": 0.5,
        "boxplot.medianprops.linewidth": 0.8,
        "boxplot.medianprops.color": "black",
        "boxplot.flierprops.markersize": 2,
        "legend.frameon": False,
        "legend.handlelength": 1.6,
        "legend.handletextpad": 0.4,
        "legend.borderaxespad": 0.2,
        "legend.borderpad": 0.2,
        "legend.columnspacing": 1.0,
        "legend.labelspacing": 0.3,
        "figure.dpi": 150,
        "figure.facecolor": "white",
        "savefig.dpi": 600,
        "savefig.facecolor": "white",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "image.cmap": SEQ_CMAP,
    })
    try:  # mathtext shrinks super/subscripts to 70 %; keep them >= 5 pt at the small text size
        import matplotlib._mathtext as _mt
        _mt.SHRINK_FACTOR = max(0.7, FONT_MIN_PT / small_pt + 0.01)
    except Exception:
        pass
    return family


def _first_available(families):
    for fam in families:
        try:
            path = font_manager.findfont(font_manager.FontProperties(family=fam),
                                         fallback_to_default=False)
        except Exception:
            continue
        if path:
            return fam
    return None


def tint(color, amount: float = 0.5) -> str:
    """Mix a colour with white (amount 0 = unchanged, 1 = white)."""
    r, g, b = mcolors.to_rgb(color)
    return mcolors.to_hex((r + (1 - r) * amount, g + (1 - g) * amount, b + (1 - b) * amount))


# ---------------------------------------------------------------- palette

class Palette:
    """Fixed meaning of colours for the whole paper: name -> colour, marker, line style.

    Roles
      proposed   accent colour; further entries (variants, ablations) are tints of it
      highlight  baselines that deserve their own hue (strongest competitor): muted blue, sky, ...
      baseline   greys, darkest first, each with its own marker and dash so they survive grey print
      reference  black dashed/dotted lines: oracle, chance level, ground truth, theory
    Save it to paper_figures/figure_style.json and load it in every figure script; existing entries are
    never reassigned, new names are appended.
    """

    def __init__(self, styles: dict | None = None):
        self.styles: dict[str, dict] = dict(styles or {})

    # construction ---------------------------------------------------------
    @classmethod
    def build(cls, proposed=(), baselines=(), references=(), highlight=()):
        pal = cls()
        pal.add(proposed=proposed, baselines=baselines, references=references, highlight=highlight)
        return pal

    def add(self, proposed=(), baselines=(), references=(), highlight=()):
        used_markers = {s["marker"] for s in self.styles.values()}
        markers = [m for m in MARKERS if m not in used_markers] + MARKERS

        def count(role):
            return sum(1 for s in self.styles.values() if s["role"] == role)

        for name in proposed:
            if name in self.styles:
                continue
            i = count("proposed")
            color = COLORS["accent"] if i == 0 else tint(COLORS["accent"], min(0.15 + 0.2 * i, 0.6))
            self.styles[name] = dict(role="proposed", color=color, marker=markers.pop(0),
                                     ls=LINESTYLES[0] if i == 0 else LINESTYLES[min(i, 3)], zorder=5)
        hl_colors = [COLORS[k] for k in ("blue", "sky", "purple", "green")]
        for name in highlight:
            if name in self.styles:
                continue
            i = count("highlight")
            self.styles[name] = dict(role="highlight", color=hl_colors[i % len(hl_colors)],
                                     marker=markers.pop(0), ls=LINESTYLES[0], zorder=4)
        for name in baselines:
            if name in self.styles:
                continue
            i = count("baseline")
            self.styles[name] = dict(role="baseline", color=GREYS[min(i, len(GREYS) - 1)],
                                     marker=markers.pop(0),
                                     ls=LINESTYLES[1 + i % (len(LINESTYLES) - 1)],  # never solid
                                     zorder=3)
        for name in references:
            if name in self.styles:
                continue
            i = count("reference")
            self.styles[name] = dict(role="reference", color=COLORS["black"], marker="",
                                     ls=["--", ":", "-."][i % 3], zorder=2)
        self._warn_if_too_many_hues()
        return self

    def _warn_if_too_many_hues(self):
        hues = {s["color"] for s in self.styles.values() if s["role"] in ("proposed", "highlight")}
        hues = {_hue_bin(c) for c in hues if _is_chromatic(c)}
        if len(hues) > 5:
            warnings.warn(f"{len(hues)} distinct hues in the palette; keep 3-5 meaningful colours.")

    # persistence ------------------------------------------------------------
    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.styles, indent=2, ensure_ascii=False, default=list),
                        encoding="utf-8")
        return path

    @classmethod
    def load(cls, path):
        styles = json.loads(Path(path).read_text(encoding="utf-8"))
        for s in styles.values():
            if isinstance(s.get("ls"), list):          # JSON turns dash tuples into lists
                s["ls"] = (s["ls"][0], tuple(s["ls"][1]))
        return cls(styles)

    @classmethod
    def load_or_build(cls, path, proposed=(), baselines=(), references=(), highlight=()):
        path = Path(path)
        pal = cls.load(path) if path.exists() else cls()
        before = dict(pal.styles)
        pal.add(proposed=proposed, baselines=baselines, references=references, highlight=highlight)
        if pal.styles != before or not path.exists():
            pal.save(path)
        return pal

    # access -----------------------------------------------------------------
    def __contains__(self, name):
        return name in self.styles

    def __getitem__(self, name):
        return self.styles[name]

    def names(self, role=None):
        return [n for n, s in self.styles.items() if role is None or s["role"] == role]

    def color(self, name, default=GREYS[1]):
        return self.styles.get(name, {}).get("color", default)

    def line(self, name, label=True, **override):
        """kwargs for ax.plot / ax.errorbar."""
        s = self.styles[name]
        kw = dict(color=s["color"], linestyle=s["ls"], marker=s["marker"] or None,
                  markerfacecolor=s["color"], markeredgecolor="white" if s["marker"] else None,
                  markeredgewidth=0.4, zorder=s["zorder"],
                  linewidth=1.25 if s["role"] == "proposed" else 0.9)
        if s["role"] == "reference":
            kw.update(linewidth=0.75)
        if label:
            kw["label"] = name
        kw.update(override)
        return {k: v for k, v in kw.items() if v is not None}

    def scatter(self, name, label=True, **override):
        """kwargs for ax.scatter."""
        s = self.styles[name]
        kw = dict(color=s["color"], marker=s["marker"] or "o", s=12, edgecolors="white",
                  linewidths=0.3, zorder=s["zorder"])
        if label:
            kw["label"] = name
        kw.update(override)
        return kw

    def handles(self, names=None, kind="line", **override):
        """Legend handles in a fixed order (for nfig.shared_legend).

        kind: "line" (line + marker), "marker" (marker only, for dot plots / scatter),
        "patch" (filled box, for bars / areas). override: extra Line2D kwargs, e.g. marker=None.
        """
        names = names or list(self.styles)
        out = []
        for n in names:
            s = self.styles[n]
            if kind == "patch":
                out.append(Patch(facecolor=s["color"], edgecolor="none", label=n))
                continue
            kw = self.line(n, markersize=4 if kind == "marker" else None)
            if kind == "marker":
                kw.update(linestyle="none", marker=s["marker"] or "o")
            kw.update(override)
            out.append(Line2D([], [], **{k: v for k, v in kw.items() if v is not None}))
        return out


def _is_chromatic(color, min_sat=0.18):
    r, g, b = mcolors.to_rgb(color)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return s >= min_sat and 0.08 < l < 0.97


def _hue_bin(color, width=24):
    r, g, b = mcolors.to_rgb(color)
    h, _, _ = colorsys.rgb_to_hls(r, g, b)
    return int(((h * 360) + width / 2) // width) % int(360 / width)


# ---------------------------------------------------------------- figure & layout

def figure(width="double", height_mm: float | None = None, mosaic=None, *, rows=None, **mosaic_kw):
    """Figure at the final printed size, constrained layout.

    width: "single" (89 mm) | "onehalf" (120 mm) | "double" (183 mm) | number in mm
    mosaic: e.g. "aab;cde" -> returns (fig, {"a": ax, ...}); keys that are single lowercase letters
            become panel labels. Use other keys (e.g. "c2", "cbar") for unlabeled helper axes.
    rows: list of (mosaic, height_share) or (mosaic, height_share, mosaic_kw) -> one subfigure per
          row, returned as one merged dict. Use it whenever rows hold different kinds of panels
          (schematic banner / image strip with colorbars / plots): in a single grid, constrained
          layout gives every column the margins of the widest tick labels in that column, which
          squeezes image strips and small panels.
    """
    w_mm = WIDTHS_MM[width] if isinstance(width, str) else float(width)
    h_mm = float(height_mm) if height_mm is not None else round(w_mm * 0.6)
    if h_mm > MAX_HEIGHT_MM:
        warnings.warn(f"height {h_mm:.0f} mm exceeds {MAX_HEIGHT_MM:.0f} mm (Nature max incl. "
                      "room for the legend); split the figure or move panels to SI.")
    fig = plt.figure(figsize=(w_mm * MM, h_mm * MM), layout="constrained")
    fig.get_layout_engine().set(w_pad=0.6 * MM, h_pad=0.6 * MM, wspace=0.02, hspace=0.02)
    if rows is not None:
        subfigs = np.atleast_1d(fig.subfigures(len(rows), 1, height_ratios=[r[1] for r in rows]))
        axd = {}
        for sf, row in zip(subfigs, rows):
            d = sf.subplot_mosaic(row[0], **(row[2] if len(row) > 2 else {}))
            if set(d) & set(axd):
                raise ValueError(f"panel key(s) {sorted(set(d) & set(axd))} used in two rows")
            axd.update(d)
        return fig, axd
    if mosaic is None:
        return fig
    axd = fig.subplot_mosaic(mosaic, **mosaic_kw)
    return fig, axd


def _panel_items(axes, labels=None):
    if isinstance(axes, dict):
        keys = sorted(k for k in axes if isinstance(k, str) and len(k) == 1 and k.isalpha())
        return [(axes[k], k.lower()) for k in keys]
    axes = list(np.ravel(axes))
    labels = labels or [chr(ord("a") + i) for i in range(len(axes))]
    return list(zip(axes, labels))


def _grid_cell(ax):
    ss = ax.get_subplotspec() if hasattr(ax, "get_subplotspec") else None
    if ss is None:
        return None
    return id(ss.get_gridspec()), ss.rowspan.start, ss.colspan.start


def label_panels(fig, axes, labels=None, *, size=LABEL_PT, pad_mm=0.6, align=True, passes=3,
                 freeze=True):
    """Bold lowercase panel labels just above the top-left of each panel's content box.

    The label's left edge sits on the leftmost ink of the panel (usually the y-axis label) and
    labels in the same row / column are aligned. Call it last: it runs the layout, places the labels
    inside the layout (so constrained layout reserves room) and then freezes the layout so the saved
    file matches what was measured.
    """
    items = _panel_items(axes, labels)
    texts = []
    for ax, lab in items:
        t = ax.text(0, 1, lab, transform=ax.transAxes, fontsize=size, fontweight="bold",
                    ha="left", va="bottom", clip_on=False, color="black")
        t._nfig_panel_label = True
        texts.append(t)
    pad_px = pad_mm * MM * fig.dpi
    tol_px = 2.5 * MM * fig.dpi
    for _ in range(passes):
        fig.canvas.draw()
        _relayout(fig)
        renderer = fig.canvas.get_renderer()
        boxes = []
        for (ax, _), t in zip(items, texts):
            t.set_visible(False)
            boxes.append(ax.get_tightbbox(renderer))
            t.set_visible(True)
        xs = [bb.x0 for bb in boxes]
        ys = [bb.y1 + pad_px for bb in boxes]
        if align:
            # same grid row / column -> same label y / x; axes outside a grid fall back to position
            pos = [ax.get_window_extent(renderer) for ax, _ in items]
            cells = [_grid_cell(ax) for ax, _ in items]

            def same(i, j, k):
                if cells[i] and cells[j] and cells[i][0] == cells[j][0]:
                    return cells[i][k] == cells[j][k]
                return (abs(pos[j].y1 - pos[i].y1) if k == 1 else abs(pos[j].x0 - pos[i].x0)) < tol_px

            n = len(items)
            ys = [max(ys[j] for j in range(n) if same(i, j, 1)) for i in range(n)]
            xs = [min(xs[j] for j in range(n) if same(i, j, 2)) for i in range(n)]
        for (ax, _), t, x, y in zip(items, texts, xs, ys):
            t.set_position(ax.transAxes.inverted().transform((x, y)))
    if freeze:
        fig.canvas.draw()
        _relayout(fig)
        fig.set_layout_engine("none")
    return texts


def shared_legend(fig, handles, labels=None, *, loc="outside upper center", ncol=None, **kw):
    """One legend for the whole figure (instead of repeating it in each panel)."""
    labels = labels or [h.get_label() for h in handles]
    return fig.legend(handles, labels, loc=loc, ncol=ncol or len(handles), frameon=False,
                      handlelength=1.8, columnspacing=1.2, **kw)


def end_labels(ax, items, *, dx_pt=2.0, min_gap_pt=6.5, fontsize=None, **kw):
    """Direct labels at line ends (black text; no colour-coded text).

    items: list of (x, y, text) in data coordinates. Labels are pushed apart vertically so they
    never overlap. Prefer this to a legend when there are <= 5 lines. Reference lines drawn with
    axhline span the whole axes, so label them above the line instead (ax.text(..., va="bottom")).
    """
    fig = ax.figure
    items = sorted(items, key=lambda it: it[1])
    out = [ax.annotate(s, (x, y), xytext=(dx_pt, 0), textcoords="offset points", va="center",
                       ha="left", fontsize=fontsize or mpl.rcParams["legend.fontsize"],
                       annotation_clip=False, **kw) for x, y, s in items]

    def place():
        # spacing is computed in points from the current axes size, so it is redone after every
        # layout pass (label_panels / save call it): the layout shrinks axes after this call
        ys_pt = [ax.transData.transform((x, y))[1] * 72 / fig.dpi for x, y, _ in items]
        new = list(ys_pt)
        for i in range(1, len(new)):
            new[i] = max(new[i], new[i - 1] + min_gap_pt)
        shift = (new[-1] - ys_pt[-1]) / 2 if new else 0
        for ann, y0, y1 in zip(out, ys_pt, new):
            ann.xyann = (dx_pt, y1 - y0 - shift)

    fig.canvas.draw()
    place()
    root = _root_figure(fig)
    root._nfig_relayout = getattr(root, "_nfig_relayout", []) + [place]
    return out


def _root_figure(fig):
    while getattr(fig, "_parent", None) is not None and fig._parent is not fig:
        fig = fig._parent
    return fig


def _relayout(fig):
    for f in getattr(_root_figure(fig), "_nfig_relayout", []):
        f()


# ---------------------------------------------------------------- plot helpers

def _summary(v, kind):
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    n = len(v)
    if kind == "median_iqr":
        q1, med, q3 = np.percentile(v, [25, 50, 75])
        return med, med - q1, q3 - med
    m = v.mean()
    sd = v.std(ddof=1) if n > 1 else 0.0
    if kind == "mean_sd":
        e = sd
    elif kind == "mean_sem":
        e = sd / math.sqrt(n) if n else 0.0
    elif kind == "mean_ci95":
        from scipy import stats
        e = stats.t.ppf(0.975, n - 1) * sd / math.sqrt(n) if n > 1 else 0.0
    else:
        raise ValueError(kind)
    return m, e, e


def points_summary(ax, data: dict, order=None, *, pal: Palette | None = None, colors=None,
                   summary="mean_sd", bar=False, jitter=0.12, size=7, alpha=0.75, seed=0,
                   width=0.6):
    """Individual data points + mean +/- error per group (Nature: show the points, not bars alone).

    data: {group: values}. summary: mean_sd | mean_sem | mean_ci95 | median_iqr (state it in the
    caption). bar=True draws a light bar from zero underneath (only for quantities with a true zero).
    """
    rng = np.random.default_rng(seed)
    order = list(order or data)
    for i, g in enumerate(order):
        v = np.asarray(data[g], float)
        c = (colors or {}).get(g) or (pal.color(g) if pal and g in pal else GREYS[1])
        m, lo, hi = _summary(v, summary)
        if bar:
            ax.bar(i, m, width=width, color=tint(c, 0.65), edgecolor=c, linewidth=0.5, zorder=1)
        x = i + rng.uniform(-jitter, jitter, len(v))
        ax.scatter(x, v, s=size, color=c, alpha=alpha, edgecolors="none", zorder=2)
        ax.errorbar(i, m, yerr=[[lo], [hi]], fmt="none", ecolor="black", elinewidth=0.6,
                    capsize=2, capthick=0.6, zorder=3)
        ax.plot([i - width / 3, i + width / 3], [m, m], color="black", lw=0.9, zorder=3,
                solid_capstyle="butt")
    ax.set_xticks(range(len(order)), order)
    ax.set_xlim(-0.6, len(order) - 0.4)
    return ax


def box_strip(ax, data: dict, order=None, *, pal: Palette | None = None, colors=None,
              jitter=0.12, size=5, seed=0, width=0.55, showfliers=False):
    """Box plot (median, IQR, 1.5 IQR whiskers) with every observation overlaid."""
    rng = np.random.default_rng(seed)
    order = list(order or data)
    vals = [np.asarray(data[g], float) for g in order]
    bp = ax.boxplot(vals, positions=range(len(order)), widths=width, patch_artist=True,
                    showfliers=showfliers, zorder=1)
    for i, (g, patch) in enumerate(zip(order, bp["boxes"])):
        c = (colors or {}).get(g) or (pal.color(g) if pal and g in pal else GREYS[1])
        patch.set(facecolor=tint(c, 0.7), edgecolor=c)
        for k in ("whiskers", "caps"):
            for art in bp[k][2 * i:2 * i + 2]:
                art.set_color(c)
        x = i + rng.uniform(-jitter, jitter, len(vals[i]))
        ax.scatter(x, vals[i], s=size, color=c, alpha=0.8, edgecolors="none", zorder=2)
    ax.set_xticks(range(len(order)), order)
    return bp


def line_band(ax, x, y, *, band="sd", style: dict | None = None, err=None, alpha=0.18, **kw):
    """Mean line with an uncertainty band.

    y: (n_repeats, n_x) array -> mean +/- sd | sem | ci95 across repeats, or 1-D y with err=(lo, hi)
    style: e.g. pal.line("Ours").
    """
    style = dict(style or {})
    style.update(kw)
    y = np.asarray(y, float)
    if y.ndim == 2:
        m = np.nanmean(y, 0)
        n = np.sum(np.isfinite(y), 0)
        sd = np.nanstd(y, 0, ddof=1)
        if band == "sd":
            e = sd
        elif band == "sem":
            e = sd / np.sqrt(n)
        elif band == "ci95":
            from scipy import stats
            e = stats.t.ppf(0.975, n - 1) * sd / np.sqrt(n)
        else:
            raise ValueError(band)
        lo, hi = m - e, m + e
    else:
        m = y
        lo, hi = err if err is not None else (y, y)
    (line,) = ax.plot(x, m, **style)
    ax.fill_between(x, lo, hi, color=line.get_color(), alpha=alpha, linewidth=0, zorder=line.get_zorder() - 1)
    return line


def scatter_identity(ax, x, y, *, style: dict | None = None, metrics=("r2", "mae"), lims=None,
                     hexbin_above=4000, unit=""):
    """Prediction vs ground truth with the y = x line and agreement metrics in the corner."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    lo = min(x.min(), y.min()) if lims is None else lims[0]
    hi = max(x.max(), y.max()) if lims is None else lims[1]
    pad = 0.03 * (hi - lo)
    lo, hi = lo - pad, hi + pad
    if len(x) > hexbin_above:
        hb = ax.hexbin(x, y, gridsize=60, cmap=SEQ_CMAP, mincnt=1, bins="log", linewidths=0)
    else:
        kw = dict(s=6, color=COLORS["accent"], alpha=0.6, edgecolors="none")
        kw.update(style or {})
        kw.pop("label", None)
        hb = ax.scatter(x, y, **kw)
    ax.plot([lo, hi], [lo, hi], color="black", lw=0.6, ls="--", zorder=0)
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_aspect("equal", adjustable="box")
    lines = []
    if "r2" in metrics:
        ss_res = np.sum((y - x) ** 2)
        ss_tot = np.sum((x - x.mean()) ** 2)
        lines.append(rf"$\mathit{{R}}^2$ = {1 - ss_res / ss_tot:.3f}")
    if "r" in metrics:
        lines.append(rf"$\mathit{{r}}$ = {np.corrcoef(x, y)[0, 1]:.3f}")
    if "mae" in metrics:
        lines.append(f"MAE = {np.mean(np.abs(y - x)):.3g}{(' ' + unit) if unit else ''}")
    if "rmse" in metrics:
        lines.append(f"RMSE = {np.sqrt(np.mean((y - x) ** 2)):.3g}{(' ' + unit) if unit else ''}")
    lines.append(rf"$\mathit{{n}}$ = {len(x):,}")
    ax.text(0.04, 0.96, "\n".join(lines), transform=ax.transAxes, va="top", ha="left",
            fontsize=mpl.rcParams["legend.fontsize"], linespacing=1.3)
    return hb


def heatmap(ax, M, row_labels=None, col_labels=None, *, cmap=None, center=None, vmin=None,
            vmax=None, annotate=False, fmt="{:.2f}", cbar_label=None, cbar=True, cbar_kw=None):
    """Matrix heatmap; diverging colours only when `center` (the reference value) is given."""
    M = np.asarray(M, float)
    norm = None
    if center is not None:
        span = np.nanmax(np.abs(M - center)) if vmin is None and vmax is None else None
        lo = vmin if vmin is not None else center - span
        hi = vmax if vmax is not None else center + span
        norm = mcolors.TwoSlopeNorm(vcenter=center, vmin=lo, vmax=hi)
        cmap = cmap or DIV_CMAP
        vmin = vmax = None
    im = ax.imshow(M, cmap=cmap or SEQ_CMAP, norm=norm, vmin=vmin, vmax=vmax, aspect="auto",
                   interpolation="nearest")
    if row_labels is not None:
        ax.set_yticks(range(M.shape[0]), row_labels)
    if col_labels is not None:
        ax.set_xticks(range(M.shape[1]), col_labels)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    if annotate:
        cm = im.cmap
        for i in range(M.shape[0]):
            for j in range(M.shape[1]):
                if not np.isfinite(M[i, j]):
                    continue
                r, g, b, _ = cm(im.norm(M[i, j]))
                lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
                ax.text(j, i, fmt.format(M[i, j]).replace("-", "−"), ha="center", va="center",
                        color="black" if lum > 0.45 else "white",
                        fontsize=mpl.rcParams["xtick.labelsize"] - 0.5)
    cb = colorbar(im, ax, cbar_label, **(cbar_kw or {})) if cbar else None
    return im, cb


def field(ax, Z, *, extent=None, cmap=None, vmin=None, vmax=None, center=None, origin="lower",
          axis=False, title=None, aspect=None):
    """2-D scalar field / map (temperature, error, density, prediction) drawn as data cells.

    - Drawn with imshow(interpolation="nearest"): crisp cells, resampled at 600 dpi in the PDF, no
      seams. (pcolormesh is only for irregular grids; then pass rasterized=True to avoid white
      hairlines between cells.)
    - Maps that share a quantity share vmin/vmax - inside a figure and across figures. Keep those
      limits in paper_figures/src/style.py and add ONE colorbar per shared scale (nfig.colorbar).
    - extent=(x0, x1, y0, y1) in physical units keeps the true aspect ratio; axis=True shows them.
      For axes with different units (distance x time waterfalls) pass aspect="auto".
    - center=0 for signed quantities (diverging colours); magnitudes use a sequential map.
    Low pixel counts are fine here: the 300 dpi rule is for photographs, not data cells.
    """
    Z = np.asarray(Z, float)
    norm = None
    if center is not None:
        span = np.nanmax(np.abs(Z - center))
        norm = mcolors.TwoSlopeNorm(vcenter=center, vmin=center - span if vmin is None else vmin,
                                    vmax=center + span if vmax is None else vmax)
        cmap = cmap or DIV_CMAP
        vmin = vmax = None
    im = ax.imshow(Z, cmap=cmap or SEQ_CMAP, norm=norm, vmin=vmin, vmax=vmax, extent=extent,
                   origin=origin, interpolation="nearest",
                   aspect=aspect or ("equal" if extent is not None else "auto"))
    if not axis:
        ax.set_axis_off()
    if title:
        ax.set_title(title)
    return im


def colorbar(im, axes, label=None, *, shrink=0.9, aspect=18, pad=0.02, **kw):
    """One thin colorbar for one or several axes that share the scale of `im`."""
    axes = list(np.atleast_1d(axes))
    cb = axes[0].figure.colorbar(im, ax=axes if len(axes) > 1 else axes[0], shrink=shrink,
                                 aspect=aspect, pad=pad, **kw)
    cb.outline.set_linewidth(0.5)
    cb.ax.tick_params(width=0.5, length=2)
    if label:
        cb.set_label(label)
    return cb


def _load_image(path, dpi=600):
    path = Path(path)
    if path.suffix.lower() in (".pdf", ".svg"):
        import fitz  # PyMuPDF
        doc = fitz.open(path)
        if path.suffix.lower() == ".svg":
            doc = fitz.open("pdf", doc.convert_to_pdf())
        pix = doc[0].get_pixmap(dpi=dpi, alpha=False)
        return np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)
    from PIL import Image
    im = Image.open(path)
    im = im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB")
    return np.asarray(im)


def trim_whitespace(img, tol=8):
    """Crop uniform near-white borders of an RGB(A) array."""
    rgb = img[..., :3].astype(int)
    ink = (255 - rgb).max(-1) > tol
    if img.shape[-1] == 4:
        ink &= img[..., 3] > 0
    ys, xs = np.nonzero(ink)
    if not len(xs):
        return img
    return img[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def image_panel(ax, path_or_array, *, crop=None, trim=True, scalebar=None, dpi=600):
    """Show a photo / micrograph / externally drawn schematic in a panel (raster).

    crop: (x0, y0, x1, y1) as fractions of the (trimmed) image. scalebar: (length_px, "10 um").
    Vector schematics lose their vectors here; for vector-preserving composition use assemble.py.
    Image integrity: crop and rescale only; never retouch, splice or adjust parts of an image.
    """
    img = _load_image(path_or_array, dpi) if not isinstance(path_or_array, np.ndarray) else path_or_array
    if trim:
        img = trim_whitespace(img)
    if crop:
        h, w = img.shape[:2]
        x0, y0, x1, y1 = crop
        img = img[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]
    im = ax.imshow(img, interpolation="antialiased")
    ax.set_axis_off()
    if scalebar:
        length, text = scalebar
        h, w = img.shape[:2]
        x1, y = w * 0.95, h * 0.93
        dark = img[int(h * 0.85):, int(w * 0.7):, :3].mean() < 128
        c = "white" if dark else "black"
        ax.plot([x1 - length, x1], [y, y], color=c, lw=1.5, solid_capstyle="butt")
        ax.text(x1 - length / 2, y - h * 0.02, text, color=c, ha="center", va="bottom",
                fontsize=mpl.rcParams["xtick.labelsize"])
    return im


def sig_bracket(ax, x1, x2, y, text, *, h_frac=0.02, color="black"):
    """Significance bracket between two x positions; text like fmt_p(p) or 'n.s.'."""
    span = ax.get_ylim()[1] - ax.get_ylim()[0]
    h = h_frac * span
    ax.plot([x1, x1, x2, x2], [y, y + h, y + h, y], color=color, lw=0.5, clip_on=False)
    ax.text((x1 + x2) / 2, y + h, text, ha="center", va="bottom",
            fontsize=mpl.rcParams["xtick.labelsize"], color=color)


def fmt_p(p: float) -> str:
    """Nature style exact P value with italic P: 'P = 0.003', 'P = 2 x 10^-5', 'P < 1 x 10^-16'."""
    if p < 1e-16:
        return r"$\mathit{P}$ < 1 × 10$^{-16}$"
    if p < 1e-3:
        mant, exp = f"{p:.1e}".split("e")
        return rf"$\mathit{{P}}$ = {mant} × 10$^{{{int(exp)}}}$"
    return rf"$\mathit{{P}}$ = {p:.2g}" if p < 0.01 else rf"$\mathit{{P}}$ = {p:.2f}"


def pipeline(ax, stages, *, highlight=(), y=0.5, height=0.5, gap=0.06, fontsize=None,
             lane_label=None, colors=None):
    """A left-to-right chain of rounded boxes with arrows, for overview / concept panels.

    stages: list of str (use "\\n" to wrap). highlight: indices drawn in the accent colour (what is
    new). Call twice with different y for a 'conventional vs proposed' two-lane comparison; the
    lane_label is written above the lane, so leave ~0.1 of the axes height free above each lane.
    """
    n = len(stages)
    x0 = 0.0
    w = (1 - x0 - gap * (n - 1)) / n
    fs = fontsize or mpl.rcParams["font.size"]
    boxes = []
    for i, s in enumerate(stages):
        c = (colors or {}).get(i) or (COLORS["accent"] if i in highlight else GREYS[1])
        fill = tint(c, 0.85) if i in highlight else "white"
        bx = x0 + i * (w + gap)
        p = FancyBboxPatch((bx, y - height / 2), w, height, boxstyle="round,pad=0,rounding_size=0.03",
                           transform=ax.transAxes, facecolor=fill, edgecolor=c,
                           linewidth=0.9 if i in highlight else 0.6, clip_on=False)
        ax.add_patch(p)
        ax.text(bx + w / 2, y, s, transform=ax.transAxes, ha="center", va="center", fontsize=fs,
                fontweight="bold" if i in highlight else "normal")
        boxes.append(p)
        if i:
            ax.add_patch(FancyArrowPatch((bx - gap + 0.008, y), (bx - 0.008, y),
                                         transform=ax.transAxes, arrowstyle="-|>,head_length=2.5,head_width=1.5",
                                         mutation_scale=1, linewidth=0.6, color="black", clip_on=False))
    if lane_label:
        ax.text(0, y + height / 2 + 0.03, lane_label, transform=ax.transAxes, ha="left",
                va="bottom", fontsize=fs, fontweight="bold")
    ax.set_axis_off()
    return boxes


# ---------------------------------------------------------------- save & QA

def save(fig, stem, formats=("pdf", "svg", "png"), png_dpi=600, check=True, quiet=False):
    """Save at the exact figure size (no bbox_inches='tight') and print the QA report."""
    stem = Path(stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    fig.canvas.draw()
    _relayout(fig)
    issues = qa(fig) if check else []
    for fmt in formats:
        fig.savefig(stem.with_suffix("." + fmt), dpi=png_dpi if fmt in ("png", "tif", "tiff", "jpg") else None)
    if check and not quiet:
        _utf8_stdout()
        w, h = fig.get_size_inches() / MM
        print(f"[nfig] {stem.name}: {w:.0f} x {h:.0f} mm -> " + ", ".join(f".{f}" for f in formats))
        print(format_issues(issues))
    return issues


def _utf8_stdout():
    """Windows consoles default to cp932 etc.; print '×', 'µ', '−' as UTF-8 like the other tools."""
    stream = sys.stdout
    enc = (getattr(stream, "encoding", "") or "").lower().replace("-", "")
    if enc and enc != "utf8" and hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def format_issues(issues):
    if not issues:
        return "  QA: no issues found (still inspect the PNG at final size)."
    return "\n".join(f"  {lvl:5s} {msg}" for lvl, msg in issues)


def _axis_texts(ax):
    """(drawn, not drawn) tick/axis-label texts of an axes."""
    drawn, hidden = [], []
    for axis in (ax.xaxis, ax.yaxis):
        all_labels = []
        for tick in axis.majorTicks + axis.minorTicks:
            all_labels += [tick.label1, tick.label2]
        all_labels += [axis.label, axis.offsetText]
        if not ax.axison or not axis.get_visible():
            hidden += all_labels
            continue
        try:
            ticks = axis._update_ticks()
        except Exception:
            ticks = axis.majorTicks + axis.minorTicks
        shown = set()
        for tick in ticks:
            for lab in (tick.label1, tick.label2):
                if lab.get_visible():
                    shown.add(id(lab))
        for lab in all_labels:
            (drawn if (id(lab) in shown or lab in (axis.label, axis.offsetText)) else hidden).append(lab)
    return drawn, hidden


def _drawn_texts(fig):
    hidden = set()
    axes = fig.findobj(lambda a: isinstance(a, mpl.axes.Axes))
    for ax in axes:
        _, h = _axis_texts(ax)
        hidden.update(id(t) for t in h)
    out = []
    for t in fig.findobj(Text):
        if id(t) in hidden or not t.get_visible() or not t.get_text().strip():
            continue
        if t.axes is not None and not t.axes.get_visible():
            continue
        out.append(t)
    return out


def _greyish(color):
    r, g, b = mcolors.to_rgb(color)
    return max(r, g, b) - min(r, g, b) < 0.08


def qa(fig, max_hues=5):
    """Automatic checks against the Nature specs. Returns [(level, message)]."""
    issues = []
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    w_mm, h_mm = fig.get_size_inches() / MM
    if not (any(abs(w_mm - v) < 1 for v in WIDTHS_MM.values())
            or ONEHALF_RANGE_MM[0] - 1 <= w_mm <= ONEHALF_RANGE_MM[1] + 1):
        issues.append(("WARN", f"width {w_mm:.1f} mm is not 89 / 120-136 / 183 mm"))
    if h_mm > MAX_HEIGHT_MM + 0.5:
        issues.append(("ERROR", f"height {h_mm:.0f} mm > {MAX_HEIGHT_MM:.0f} mm"))

    texts = _drawn_texts(fig)
    fw, fh = fig.bbox.width, fig.bbox.height
    small, big, coloured, outside, fonts = [], [], [], [], set()
    boxes = []
    for t in texts:
        size = t.get_fontsize()
        s = t.get_text().strip().replace("\n", " ")
        label = getattr(t, "_nfig_panel_label", False)
        if "$" in s and ("^" in s or "_" in s):
            try:
                import matplotlib._mathtext as _mt
                size = size * _mt.SHRINK_FACTOR      # the super/subscript is the smallest glyph
            except Exception:
                pass
        if label:
            if abs(t.get_fontsize() - LABEL_PT) > 0.1 or t.get_fontweight() not in ("bold", 700):
                issues.append(("WARN", f"panel label '{s}' should be {LABEL_PT:g} pt bold"))
        elif size < FONT_MIN_PT - 1e-6:
            small.append(f"'{s[:25]}' {size:.1f} pt")
        elif size > FONT_MAX_PT + 1e-6:
            big.append(f"'{s[:25]}' {size:.1f} pt")
        if not label and not _greyish(t.get_color()) and t.get_color() not in ("white", "#ffffff"):
            coloured.append(f"'{s[:20]}'")
        fonts.add(t.get_fontname())
        bb = t.get_window_extent(r)
        if bb.x0 < -1 or bb.y0 < -1 or bb.x1 > fw + 1 or bb.y1 > fh + 1:
            outside.append(f"'{s[:25]}'")
        boxes.append((bb, s, t))
    if small:
        issues.append(("ERROR", f"{len(small)} text(s) below {FONT_MIN_PT:g} pt: " + ", ".join(small[:5])))
    if big:
        issues.append(("WARN", f"{len(big)} text(s) above {FONT_MAX_PT:g} pt: " + ", ".join(big[:5])))
    if coloured:
        issues.append(("WARN", "coloured text (Nature prefers black text + coloured keys): "
                       + ", ".join(coloured[:5])))
    if outside:
        issues.append(("ERROR", "text cut off at the figure edge: " + ", ".join(outside[:5])))
    odd_fonts = {f for f in fonts if not any(k in f for k in ("Arial", "Helvetica", "Liberation", "Nimbus", "Heros"))}
    if odd_fonts:
        issues.append(("WARN", f"non-Arial/Helvetica fonts in use: {sorted(odd_fonts)}"))

    overlaps = []
    for i in range(len(boxes)):
        bi = boxes[i][0]
        for j in range(i + 1, len(boxes)):
            bj = boxes[j][0]
            ix = min(bi.x1, bj.x1) - max(bi.x0, bj.x0)
            iy = min(bi.y1, bj.y1) - max(bi.y0, bj.y0)
            if ix > 1.0 and iy > 1.0:
                overlaps.append(f"'{boxes[i][1][:18]}' x '{boxes[j][1][:18]}'")
    if overlaps:
        issues.append(("ERROR", f"{len(overlaps)} overlapping text pair(s): " + "; ".join(overlaps[:6])))

    thin, colours = 0, []
    for ln in fig.findobj(Line2D):
        if not ln.get_visible() or ln.axes is None and ln.figure is None:
            continue
        if ln.get_linestyle() not in ("None", "", " ") and 0 < ln.get_linewidth() < MIN_LINE_PT:
            thin += 1
        if ln.get_linestyle() not in ("None", "", " ") or ln.get_marker() not in ("None", "", None):
            colours.append(ln.get_color())
    for p in fig.findobj(Patch):
        if not p.get_visible() or p is fig.patch or isinstance(p.axes, mpl.axes.Axes) and p is p.axes.patch:
            continue
        lw = p.get_linewidth()
        if p.get_edgecolor()[3] > 0 and 0 < lw < MIN_LINE_PT:
            thin += 1
        if p.get_facecolor()[3] > 0:
            colours.append(p.get_facecolor())
    for c in fig.findobj(mpl.collections.Collection):
        if not c.get_visible() or c.get_array() is not None:
            continue  # colour-mapped collections (heatmaps, hexbin) are not categorical colours
        fc = c.get_facecolor()
        if len(fc) <= 50:
            colours += [tuple(x) for x in fc if x[3] > 0]
    if thin:
        issues.append(("WARN", f"{thin} line(s) thinner than {MIN_LINE_PT} pt"))
    chroma = [c for c in colours if _is_chromatic(c)]
    bins = {_hue_bin(c) for c in chroma}
    if len(bins) > max_hues:
        issues.append(("WARN", f"{len(bins)} distinct hues; use 3-5 meaningful colours plus greys"))
    hues = [colorsys.rgb_to_hls(*mcolors.to_rgb(c))[0] * 360 for c in chroma]
    if any(h < 15 or h > 345 for h in hues) and any(90 <= h <= 160 for h in hues):
        issues.append(("WARN", "red and green used together (avoid for colour-blind readers)"))

    for im in fig.findobj(AxesImage):
        if not im.get_visible():
            continue
        arr = im.get_array()
        if arr is None or arr.ndim != 3:
            continue  # 2-D scalar data (heatmap / field) = data cells; the dpi rule is for photos
        bb = im.get_window_extent(r)
        if bb.width <= 0:
            continue
        dpi = arr.shape[1] / (bb.width / fig.dpi)
        if dpi < MIN_DPI:
            issues.append(("WARN", f"photo/RGB image at {dpi:.0f} dpi at final size (< {MIN_DPI}); "
                           "use a higher-resolution source or a smaller panel"))
    all_axes = [a for a in fig.findobj(lambda a: isinstance(a, mpl.axes.Axes)) if a.get_visible()]
    if any(g.get_visible() for ax in all_axes for g in ax.get_xgridlines() + ax.get_ygridlines()):
        issues.append(("WARN", "background gridlines present (Nature: avoid)"))
    squeezed = []
    for ax in all_axes:
        cell = _cell_size(ax)
        if cell and cell[0] * cell[1] > 0:
            used = ax.bbox.width * ax.bbox.height / (cell[0] * cell[1])
            if used < 0.35:
                squeezed.append(f"{_panel_name(ax)} {used:.0%}")
    if squeezed:
        issues.append(("WARN", "panel(s) squeezed to a small part of their grid cell: " + ", ".join(squeezed)
                       + " -> margins from other rows leak into this column; build rows separately "
                       "with nfig.figure(rows=[...]) or change ratios"))
    crowded = []
    for ax in all_axes:
        crowded += _text_over_data(ax, r)
    if crowded:
        issues.append(("WARN", "text on top of data lines/points: " + "; ".join(crowded[:6])))
    blanks = _blank_areas(fig, all_axes)
    if blanks:
        where = ", ".join(f"{w:.0f}x{h:.0f} mm at ({x:.0f}, {y:.0f}) mm" for x, y, w, h in blanks[:4])
        issues.append(("WARN", f"empty area(s) outside the plots: {where} (x, y from top-left) -> "
                       "enlarge neighbouring panels, change width/height ratios or reduce the height"))
    return issues


def _blank_areas(fig, axes, size_mm=15.0, dpi=50):
    """Empty squares >= size_mm outside the data areas (wasted space), as (x, y, w, h) in mm."""
    import io
    buf = io.BytesIO()
    fig.savefig(buf, format="rgba", dpi=dpi)
    w = int(round(fig.get_size_inches()[0] * dpi))
    img = np.frombuffer(buf.getvalue(), np.uint8)
    img = img.reshape(-1, w, 4) if img.size % (4 * w) == 0 else None
    if img is None:
        return []
    ink = (255 - img[..., :3].astype(int)).max(-1) > 12
    H = ink.shape[0]
    scale = dpi / fig.dpi
    for ax in axes:
        if ax.axison:
            bb = ax.get_window_extent()
            x0, x1 = int(bb.x0 * scale), int(np.ceil(bb.x1 * scale))
            y0, y1 = H - int(np.ceil(bb.y1 * scale)), H - int(bb.y0 * scale)
            ink[max(y0, 0):max(y1, 0), max(x0, 0):max(x1, 0)] = True
    T = int(round(size_mm * MM * dpi))
    if T < 2 or ink.shape[0] <= T or ink.shape[1] <= T:
        return []
    ii = np.pad((~ink).astype(np.int32).cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    win = ii[T:, T:] - ii[:-T, T:] - ii[T:, :-T] + ii[:-T, :-T]
    ok = win == T * T
    if not ok.any():
        return []
    try:
        from scipy import ndimage
        lab, _ = ndimage.label(ok)
        objs = ndimage.find_objects(lab)
    except ImportError:
        ys, xs = np.nonzero(ok)
        objs = [(slice(ys.min(), ys.max() + 1), slice(xs.min(), xs.max() + 1))]
    px = 1 / (dpi * MM)
    out = [(sl[1].start * px, sl[0].start * px, (sl[1].stop - sl[1].start + T - 1) * px,
            (sl[0].stop - sl[0].start + T - 1) * px) for sl in objs]
    return sorted(out, key=lambda b: -b[2] * b[3])


def _cell_size(ax):
    """(width, height) in display px of the grid cell an axes was given (before margins)."""
    ss = ax.get_subplotspec() if hasattr(ax, "get_subplotspec") else None
    if ss is None:
        return None
    fw = fh = 1.0
    while ss is not None:
        gs = ss.get_gridspec()
        nrows, ncols = gs.get_geometry()
        hr = np.asarray(gs.get_height_ratios() or [1] * nrows, float)
        wr = np.asarray(gs.get_width_ratios() or [1] * ncols, float)
        fh *= hr[ss.rowspan.start:ss.rowspan.stop].sum() / hr.sum()
        fw *= wr[ss.colspan.start:ss.colspan.stop].sum() / wr.sum()
        ss = getattr(gs, "_subplot_spec", None)    # nested subgridspec -> continue with its parent cell
    parent = ax.figure.bbox
    return parent.width * fw, parent.height * fh


def _panel_name(ax):
    for t in ax.texts:
        if getattr(t, "_nfig_panel_label", False):
            return t.get_text()
    return ax.get_label() or "axes"


def _text_over_data(ax, renderer):
    """Annotations / ax.text / an in-axes legend placed on top of lines or markers of the axes."""
    from matplotlib.path import Path as MPath
    boxes = []
    for t in ax.texts:
        if not t.get_visible() or not t.get_text().strip() or getattr(t, "_nfig_panel_label", False):
            continue
        bb = t.get_window_extent(renderer).padded(-1.5)
        if bb.width > 0 and bb.height > 0:
            boxes.append((bb, t.get_text().strip().replace("\n", " ")))
    leg = ax.get_legend()
    if leg is not None and leg.get_visible():
        bb = leg.get_window_extent(renderer).padded(-1.5)
        if bb.width > 0 and bb.height > 0:
            boxes.append((bb, "legend"))
    if not boxes:
        return []
    shapes = []
    for ln in ax.get_lines():
        if not ln.get_visible():
            continue
        xy = ln.get_transform().transform(np.asarray(ln.get_xydata(), float))
        xy = xy[np.isfinite(xy).all(1)]
        if len(xy) > 1 and ln.get_linestyle() not in ("None", "", " "):
            shapes.append(("line", MPath(xy)))
        if len(xy) and ln.get_marker() not in ("None", "", " ", None):
            shapes.append(("pts", xy))
    for c in ax.collections:
        if isinstance(c, mpl.collections.PathCollection) and c.get_visible() and len(c.get_offsets()):
            shapes.append(("pts", c.get_offset_transform().transform(c.get_offsets())))
    out = []
    for bb, s in boxes:
        for kind, obj in shapes:
            if kind == "line":
                hit = obj.intersects_bbox(bb, filled=False)
            else:
                hit = np.any((obj[:, 0] > bb.x0) & (obj[:, 0] < bb.x1) & (obj[:, 1] > bb.y0) & (obj[:, 1] < bb.y1))
            if hit:
                out.append(f"{_panel_name(ax)}: '{s[:20]}'")
                break
    return out


def cvd_report(colors, min_delta_e=12.0):
    """Smallest CIE76 colour difference between the given colours under deutan / protan vision.

    'bad' lists only deutan / protan pairs below min_delta_e. The greyscale value is informational:
    pairs that are close in grey must differ by marker or line style (Palette does this).
    """
    names = list(colors)
    rgb = np.array([mcolors.to_rgb(colors[n]) if isinstance(colors, dict) else mcolors.to_rgb(n)
                    for n in names])
    out = {}
    for kind in ("normal", "deutan", "protan", "gray"):
        lab = _to_lab(simulate_cvd(rgb[None], kind)[0])
        best = (np.inf, None)
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                d = float(np.linalg.norm(lab[i] - lab[j]))
                if d < best[0]:
                    best = (d, (names[i], names[j]))
        out[kind] = best
    bad = {k: v for k, v in out.items() if v[0] < min_delta_e and k != "gray"}
    return out, bad


_CVD = {
    "deutan": np.array([[0.367322, 0.860646, -0.227968],
                        [0.280085, 0.672501, 0.047413],
                        [-0.011820, 0.042940, 0.968881]]),
    "protan": np.array([[0.152286, 1.052583, -0.204868],
                        [0.114503, 0.786281, 0.099216],
                        [-0.003882, -0.048116, 1.051998]]),
    "tritan": np.array([[1.255528, -0.076749, -0.178779],
                        [-0.078411, 0.930809, 0.147602],
                        [0.004733, 0.691367, 0.303900]]),
}


def simulate_cvd(rgb, kind):
    """Machado et al. (2009) full-severity simulation on an (..., 3) float sRGB array in [0, 1]."""
    rgb = np.asarray(rgb, float)
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    if kind == "normal":
        out = lin
    elif kind == "gray":
        y = lin @ np.array([0.2126, 0.7152, 0.0722])
        out = np.repeat(y[..., None], 3, -1)
    else:
        out = np.clip(lin @ _CVD[kind].T, 0, 1)
    return np.where(out <= 0.0031308, out * 12.92, 1.055 * out ** (1 / 2.4) - 0.055)


def _to_lab(rgb):
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = lin @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


if __name__ == "__main__":
    use_style()
    pal = Palette.build(proposed=["Ours", "Ours w/o A"], highlight=["SOTA"],
                        baselines=["Base 1", "Base 2", "Base 3"], references=["Oracle"])
    report, bad = cvd_report({n: pal.color(n) for n in pal.names()})
    for k, (d, pair) in report.items():
        print(f"{k:7s} min dE = {d:5.1f}  {pair}")
    print("problems:", bad or "none")
