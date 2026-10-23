#!/usr/bin/env python3
"""Compose existing panel files (PDF / SVG / PNG / JPG / TIFF) into one multi-panel figure PDF.

Vector inputs stay vector (PyMuPDF show_pdf_page); raster inputs are embedded at native
resolution. Use this when a panel cannot be re-plotted from data (schematics drawn elsewhere,
micrographs, plots whose data is gone). Re-plotting with nfig.py is preferred: only then do fonts,
line widths and colours match across panels.

  assemble.py layout.json [--out fig.pdf] [--png-dpi 300] [--debug]

layout.json (see assets/layout_example.json):
{
  "width": "double",            single | onehalf | double | <mm>
  "height_mm": 120,
  "gap_mm": 2.0,                space between sibling cells
  "label_mm": 3.0,              strip above each labelled panel for its label (0 = overlay)
  "label_pt": 8,
  "layout": {"row": [            nested row / col tree; "size" = relative share along the parent
      {"size": 2, "panel": "a", "file": "overview.pdf"},
      {"size": 1, "col": [
          {"panel": "b", "file": "acc.pdf", "trim": true},
          {"panel": "c", "file": "micrograph.png", "crop": [0, 0, 1, 0.8], "align": "center"}
      ]}
  ]},
  "output": "paper_figures/fig1.pdf"
}
Panel keys: file (relative to layout.json), panel (label or null), page (PDF page, 0-based), trim (auto-crop white margins,
default true), crop [x0, y0, x1, y1] as fractions of the trimmed content, align
(top-left | top | center | left), size.

The report lists per panel: scale factor, how much of its cell it fills, effective dpi (raster)
and the smallest / largest text after scaling (vector), so you can see which sources violate
5-7 pt / 300 dpi at the final size and which cells waste space.
"""
import argparse
import io
import json
import sys
from pathlib import Path

import fitz  # PyMuPDF

PT_PER_MM = 72 / 25.4
WIDTHS_MM = {"single": 89.0, "onehalf": 120.0, "double": 183.0}


def find_bold_font():
    try:
        from matplotlib import font_manager
        fp = font_manager.FontProperties(family=["Arial", "Helvetica", "Liberation Sans"], weight="bold")
        path = font_manager.findfont(fp, fallback_to_default=False)
        if path and "DejaVu" not in path:
            return path
    except Exception:
        pass
    for c in ["C:/Windows/Fonts/arialbd.ttf", "/Library/Fonts/Arial Bold.ttf",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
              "/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf"]:
        if Path(c).exists():
            return c
    return None


def content_bbox_pdf(page):
    """Union of everything drawn on the page, ignoring a full-page background fill."""
    area = page.rect.width * page.rect.height
    r = fitz.Rect()
    for kind, rect in page.get_bboxlog():
        rect = fitz.Rect(rect) & page.rect
        if rect.is_empty:
            continue
        if kind.startswith("fill") and rect.width * rect.height > 0.9 * area:
            continue
        r |= rect
    return r if not r.is_empty else page.rect


def load_source(spec, base):
    path = (base / spec["file"]).resolve()
    ext = path.suffix.lower()
    if ext == ".eps":
        raise SystemExit(f"{path.name}: convert EPS to PDF first (e.g. ps2pdf -dEPSCrop in.eps out.pdf)")
    if ext in (".pdf", ".svg"):
        doc = fitz.open(path)
        if ext == ".svg":
            doc = fitz.open("pdf", doc.convert_to_pdf())
        page = doc[spec.get("page", 0)]
        clip = content_bbox_pdf(page) if spec.get("trim", True) else page.rect
        if spec.get("crop"):
            x0, y0, x1, y1 = spec["crop"]
            clip = fitz.Rect(clip.x0 + x0 * clip.width, clip.y0 + y0 * clip.height,
                             clip.x0 + x1 * clip.width, clip.y0 + y1 * clip.height)
        return dict(kind="vector", doc=doc, page=page, clip=clip, w=clip.width, h=clip.height, path=path)
    from PIL import Image
    import numpy as np
    im = Image.open(path)
    im = im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB")
    if spec.get("trim", True):
        arr = np.asarray(im)
        ink = (255 - arr[..., :3].astype(int)).max(-1) > 8
        if arr.shape[-1] == 4:
            ink &= arr[..., 3] > 0
        ys, xs = np.nonzero(ink)
        if len(xs):
            im = im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    if spec.get("crop"):
        x0, y0, x1, y1 = spec["crop"]
        W, H = im.size
        im = im.crop((int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H)))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return dict(kind="raster", stream=buf.getvalue(), w=im.size[0], h=im.size[1], path=path)


def split(node, rect, gap, out):
    """Assign a rect (PDF points, origin top-left) to every panel of the tree."""
    if "panel" in node or "file" in node:
        out.append((node, rect))
        return
    kind = "row" if "row" in node else "col"
    kids = node[kind]
    g = node.get("gap_mm", None)
    g = gap if g is None else g * PT_PER_MM
    sizes = [float(k.get("size", 1)) for k in kids]
    total = sum(sizes)
    span = (rect.width if kind == "row" else rect.height) - g * (len(kids) - 1)
    pos = rect.x0 if kind == "row" else rect.y0
    for k, s in zip(kids, sizes):
        ext = span * s / total
        r = (fitz.Rect(pos, rect.y0, pos + ext, rect.y1) if kind == "row"
             else fitz.Rect(rect.x0, pos, rect.x1, pos + ext))
        split(k, r, gap, out)
        pos += ext + g


def text_sizes(page, clip):
    sizes = []
    for b in page.get_text("dict", clip=clip)["blocks"]:
        for line in b.get("lines", []):
            for s in line["spans"]:
                if s["text"].strip():
                    sizes.append(s["size"])
    return sizes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("layout")
    ap.add_argument("--out")
    ap.add_argument("--png-dpi", type=int, default=300)
    ap.add_argument("--debug", action="store_true", help="draw cell outlines")
    a = ap.parse_args()

    lay_path = Path(a.layout).resolve()
    spec = json.loads(lay_path.read_text(encoding="utf-8"))
    base = lay_path.parent
    w = spec.get("width", "double")
    w_mm = WIDTHS_MM[w] if isinstance(w, str) else float(w)
    h_mm = float(spec["height_mm"])
    out = Path(a.out or spec.get("output") or lay_path.with_suffix(".pdf"))
    if not out.is_absolute() and not a.out:
        out = base / out
    gap = float(spec.get("gap_mm", 2.0)) * PT_PER_MM
    label_h = float(spec.get("label_mm", 3.0)) * PT_PER_MM
    label_pt = float(spec.get("label_pt", 8))
    margin = float(spec.get("margin_mm", 0.5)) * PT_PER_MM

    doc = fitz.open()
    page = doc.new_page(width=w_mm * PT_PER_MM, height=h_mm * PT_PER_MM)
    font = find_bold_font()
    if font:
        page.insert_font(fontname="LBL", fontfile=font)
    cells = []
    split(spec["layout"], fitz.Rect(margin, margin, page.rect.width - margin, page.rect.height - margin), gap, cells)

    report, problems = [], 0
    for node, cell in cells:
        src = load_source(node, base)
        label = node.get("panel")
        content = fitz.Rect(cell.x0, cell.y0 + (label_h if label else 0), cell.x1, cell.y1)
        scale = min(content.width / src["w"], content.height / src["h"])
        pw, ph = src["w"] * scale, src["h"] * scale
        align = node.get("align", "top-left")
        x = content.x0 + ((content.width - pw) / 2 if align in ("top", "center") else 0)
        y = content.y0 + ((content.height - ph) / 2 if align in ("center", "left") else 0)
        target = fitz.Rect(x, y, x + pw, y + ph)
        if src["kind"] == "vector":
            page.show_pdf_page(target, src["doc"], src["page"].number, clip=src["clip"])
        else:
            page.insert_image(target, stream=src["stream"])
        if label:
            ly = cell.y0 + label_pt * 0.75 if label_h else y + label_pt * 0.75
            kw = dict(fontname="LBL") if font else dict(fontname="hebo")
            page.insert_text((x, ly), label, fontsize=label_pt, color=(0, 0, 0), **kw)
        if a.debug:
            page.draw_rect(cell, color=(1, 0, 0), width=0.3)
        fill = (pw * ph) / (cell.width * cell.height)
        line = f"{label or '-'} {src['path'].name}: scale {scale:.2f}, fills {fill:.0%} of cell"
        notes = []
        if src["kind"] == "raster":
            dpi = src["w"] / (pw / 72)
            line += f", {dpi:.0f} dpi"
            if dpi < 300:
                notes.append("below 300 dpi at final size")
        else:
            sizes = [s * scale for s in text_sizes(src["page"], src["clip"])]
            if sizes:
                line += f", text {min(sizes):.1f}-{max(sizes):.1f} pt"
                if min(sizes) < 5:
                    notes.append("text below 5 pt -> enlarge this cell or re-plot")
                if max(sizes) > 7.5:
                    notes.append("text above 7 pt -> inconsistent with other panels")
            if any(f[2] == "Type3" for f in src["page"].get_fonts(full=True)):
                notes.append("Type 3 fonts in source (re-export with pdf.fonttype=42)")
        if fill < 0.7:
            notes.append("cell mostly empty -> change size ratios or figure height")
        problems += bool(notes)
        report.append(line + ("  !! " + "; ".join(notes) if notes else ""))

    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out, garbage=3, deflate=True)
    png = out.with_suffix(".png")
    page.get_pixmap(dpi=a.png_dpi, alpha=False).save(png)
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"wrote {out} ({w_mm:.0f} x {h_mm:.0f} mm) and {png.name}")
    print("\n".join("  " + r for r in report))
    if not font:
        print("  !! Arial/Helvetica Bold not found; labels use non-embedded Helvetica-Bold")
    print(f"  {problems} panel(s) need attention" if problems else "  all panels within spec")


if __name__ == "__main__":
    main()
