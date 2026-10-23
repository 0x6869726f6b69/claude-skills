#!/usr/bin/env python3
"""Turn a results CSV into a publication table: booktabs LaTeX (.tex) + Markdown (.md).

  make_table.py results.csv --out tables/table1
      [--groupby "dataset,method" --stat "RMSE (K)=rmse_K"]  long format (one row per seed /
                                                          sample) -> mean ± s.d. per group + n
      [--cols "Method,Accuracy (%),Time (s)"]           columns to keep, in order (after --pm)
      [--rename acc="Accuracy (%)"]                       repeatable
      [--pm "Accuracy (%)=acc_mean,acc_std"]              repeatable: 'mean ± s.d.' column
      [--best "Accuracy (%):max" --best "Time (s):min"]  bold the best value (ties all bold)
      [--decimals "Accuracy (%)=1" --default-decimals 2]
      [--group Dataset]                                   best per group, \\midrule between groups
      [--caption "..."] [--label tab:main] [--note "..."] repeatable notes under the table

Rules it follows: no vertical rules, only top/mid/bottom rules, units in the header, the same
number of decimals within a column, bold only for the best value per column, true minus sign,
numbers right-aligned. The CSV values are printed as they are rounded; nothing is recomputed.
"""
import argparse
import math
import numbers
import sys
from pathlib import Path

import pandas as pd

LATEX_ESC = {"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
             "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}


def esc(s):
    return "".join(LATEX_ESC.get(ch, ch) for ch in str(s))


def kv(items, sep="="):
    out = {}
    for it in items or []:
        k, v = it.split(sep, 1) if sep in it else it.rsplit(":", 1)
        out[k.strip().strip('"')] = v.strip().strip('"')
    return out


def fmt_num(x, d):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "–"
    s = f"{x:,.{d}f}" if abs(x) >= 1e4 else f"{x:.{d}f}"
    return s.replace("-", "−")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--out", required=True, help="output stem (writes .tex and .md)")
    ap.add_argument("--groupby", help="comma-separated key columns of long-format data")
    ap.add_argument("--stat", action="append", help="NAME=COLUMN aggregated as mean ± s.d. (with --groupby)")
    ap.add_argument("--cols")
    ap.add_argument("--rename", action="append")
    ap.add_argument("--pm", action="append")
    ap.add_argument("--best", action="append")
    ap.add_argument("--decimals", action="append")
    ap.add_argument("--default-decimals", type=int, default=2)
    ap.add_argument("--group")
    ap.add_argument("--caption", default="")
    ap.add_argument("--label", default="")
    ap.add_argument("--note", action="append")
    a = ap.parse_args()

    df = pd.read_csv(a.csv, sep=None, engine="python")
    df = df.rename(columns=kv(a.rename))
    if a.groupby:
        keys = [k.strip() for k in a.groupby.split(",")]
        stats = kv(a.stat)
        if not stats:
            sys.exit("--groupby needs at least one --stat NAME=COLUMN")
        grouped = df.groupby(keys, sort=False)
        agg = grouped.size().rename("n").to_frame()
        for name, col in stats.items():
            agg[name] = list(zip(grouped[col].mean(), grouped[col].std(ddof=1)))
        df = agg.reset_index()
    mean_of = {}
    pm = kv(a.pm)
    for name, pair in pm.items():
        m, s = [c.strip() for c in pair.split(",")]
        df[name] = list(zip(df[m], df[s]))
        mean_of[name] = m
    cols = [c.strip() for c in a.cols.split(",")] if a.cols else list(df.columns)
    missing = [c for c in cols if c not in df.columns]
    if missing:
        sys.exit(f"unknown column(s): {missing}; available: {list(df.columns)}")
    best = {k: v.lower() for k, v in kv(a.best, ":").items()}
    dec = {k: int(v) for k, v in kv(a.decimals).items()}

    def value(row, c):
        v = row[c]
        return v[0] if isinstance(v, tuple) else v

    groups = [g for _, g in df.groupby(a.group, sort=False)] if a.group else [df]
    bold = set()
    for g in groups:
        for c, how in best.items():
            vals = pd.to_numeric(g.apply(lambda r: value(r, c), axis=1), errors="coerce")
            if vals.notna().any():
                d = dec.get(c, a.default_decimals)
                target = round(vals.max() if how == "max" else vals.min(), d)
                for i in vals.index[vals.round(d) == target]:
                    bold.add((i, c))

    numeric = {c: df[c].map(lambda v: isinstance(v, (tuple, numbers.Real))).all() for c in cols}
    zero_sd = set()

    def cell(i, c, latex):
        v = df.at[i, c]
        d = dec.get(c, a.default_decimals)
        if isinstance(v, tuple):
            sd = fmt_num(v[1], d)
            if v[1] and float(sd.replace("−", "-").replace(",", "")) == 0:
                zero_sd.add(c)
            s = f"{fmt_num(v[0], d)} ± {sd}"
            if latex:
                s = s.replace(" ± ", r" $\pm$ ")
        elif isinstance(v, numbers.Real) and not isinstance(v, bool):
            s = fmt_num(v, d) if isinstance(v, float) else str(v)
        else:
            s = str(v)
        if latex:
            s = esc(s) if not isinstance(v, tuple) else s
            s = s.replace("−", "$-$")
            return rf"\textbf{{{s}}}" if (i, c) in bold else s
        return f"**{s}**" if (i, c) in bold else s

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    align = "".join("r" if numeric[c] else "l" for c in cols)
    tex = [r"\begin{table}[t]", r"\centering"]
    if a.caption:
        tex.append(rf"\caption{{{a.caption}}}")
    if a.label:
        tex.append(rf"\label{{{a.label}}}")
    tex += [rf"\begin{{tabular}}{{@{{}}{align}@{{}}}}", r"\toprule", " & ".join(esc(c) for c in cols) + r" \\", r"\midrule"]
    for gi, g in enumerate(groups):
        if gi:
            tex.append(r"\midrule")
        for i in g.index:
            tex.append(" & ".join(cell(i, c, True) for c in cols) + r" \\")
    tex += [r"\bottomrule", r"\end{tabular}"]
    notes = a.note or []
    if notes:
        tex.append(r"\par\smallskip{\footnotesize " + r"\par ".join(esc(n) for n in notes) + "}")
    tex.append(r"\end{table}")
    (out.with_suffix(".tex")).write_text("\n".join(tex) + "\n", encoding="utf-8")

    md = []
    if a.caption:
        md += [f"**{a.caption}**", ""]
    md.append("| " + " | ".join(cols) + " |")
    md.append("|" + "|".join("---:" if numeric[c] else ":---" for c in cols) + "|")
    for g in groups:
        for i in g.index:
            md.append("| " + " | ".join(cell(i, c, False) for c in cols) + " |")
    if notes:
        md += [""] + [f"{n}" for n in notes]
    (out.with_suffix(".md")).write_text("\n".join(md) + "\n", encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"wrote {out.with_suffix('.tex')} and {out.with_suffix('.md')}")
    print("\n".join(md))
    for c in sorted(zero_sd):
        print(f"!! '{c}': a non-zero s.d. rounds to 0 -> raise --decimals \"{c}=N\" or change the unit")


if __name__ == "__main__":
    main()
