#!/usr/bin/env python3
"""Check a finished figure file against the Nature specs and render previews for visual review.

  check_figure.py FIG.pdf [FIG2.pdf ...] [--previews DIR] [--dpi 300] [--width single|double|<mm>]

PDF / SVG checks
  size        width 89 / 120-136 / 183 mm, height <= 170 mm
  fonts       embedded TrueType (no Type 3, no unembedded), Arial/Helvetica family
  text        all text 5-7 pt; panel labels 8 pt bold lowercase; no coloured text
  lines       strokes thinner than 0.25 pt
  colours     number of distinct hues (3-5 is the target), red + green together
  rasters     embedded images below 300 dpi at final size
  margins     empty border wider than 3 mm (wasted space)
PNG / JPG / TIFF: only pixel size -> dpi at the intended --width.

Previews (for the Read tool): <stem>_preview.png at --dpi, and <stem>_access.png with the figure as
seen with deuteranopia, protanopia and in greyscale, to verify that colour is not the only cue.
Exit code 1 if any ERROR was found.
"""
import argparse
import colorsys
import re
import sys
from pathlib import Path

import numpy as np

PT_PER_MM = 72 / 25.4
WIDTHS_MM = {"single": 89.0, "onehalf": 120.0, "double": 183.0}
MAX_H_MM = 170.0
CVD = {
    "deuteranopia": np.array([[0.367322, 0.860646, -0.227968],
                              [0.280085, 0.672501, 0.047413],
                              [-0.011820, 0.042940, 0.968881]]),
    "protanopia": np.array([[0.152286, 1.052583, -0.204868],
                            [0.114503, 0.786281, 0.099216],
                            [-0.003882, -0.048116, 1.051998]]),
}


def to_lin(x):
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def to_srgb(x):
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.clip(x, 0, 1) ** (1 / 2.4) - 0.055)


def access_sheet(rgb_u8, out):
    from PIL import Image, ImageDraw, ImageFont
    rgb = rgb_u8[..., :3].astype(float) / 255
    lin = to_lin(rgb)
    views = [("original", rgb)]
    for name, m in CVD.items():
        views.append((name, to_srgb(np.clip(lin @ m.T, 0, 1))))
    gray = lin @ np.array([0.2126, 0.7152, 0.0722])
    views.append(("greyscale", np.repeat(to_srgb(gray)[..., None], 3, -1)))
    h, w = rgb.shape[:2]
    sheet = Image.new("RGB", (w * 2 + 30, (h + 40) * 2 + 10), "white")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except Exception:
        font = ImageFont.load_default()
    for k, (name, arr) in enumerate(views):
        x, y = (k % 2) * (w + 30), (k // 2) * (h + 40)
        sheet.paste(Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8)), (x, y + 36))
        draw.text((x + 4, y + 2), name, fill="black", font=font)
    sheet.save(out)


def hue_of(rgb):
    h, l, s = colorsys.rgb_to_hls(*rgb)
    return h * 360, l, s


def check_pdf(path, previews, dpi):
    import fitz
    issues = []
    doc = fitz.open(path)
    if path.suffix.lower() == ".svg":
        doc = fitz.open("pdf", doc.convert_to_pdf())
    if len(doc) > 1:
        issues.append(("WARN", f"{len(doc)} pages; one figure per file is expected"))
    page = doc[0]
    w_mm, h_mm = page.rect.width / PT_PER_MM, page.rect.height / PT_PER_MM
    info = [f"size {w_mm:.1f} x {h_mm:.1f} mm"]
    if not (any(abs(w_mm - v) <= 1 for v in WIDTHS_MM.values()) or 119 <= w_mm <= 137):
        issues.append(("WARN", f"width {w_mm:.1f} mm is not 89 / 120-136 / 183 mm"))
    if h_mm > MAX_H_MM + 0.5:
        issues.append(("ERROR", f"height {h_mm:.0f} mm > {MAX_H_MM:.0f} mm"))

    # fonts
    for xref, ext, ftype, basefont, *_ in page.get_fonts(full=True):
        name = basefont.split("+")[-1]
        if ftype == "Type3":
            issues.append(("ERROR", f"Type 3 font {name} (matplotlib: rcParams['pdf.fonttype'] = 42)"))
        elif ext == "n/a":
            issues.append(("WARN", f"font {name} is not embedded"))
        if not re.search(r"Arial|Helvetica|Liberation|Nimbus|Heros|Symbol|Courier", name, re.I):
            issues.append(("WARN", f"font {name}: use Arial/Helvetica"))

    # text
    small, big, coloured, labels = [], [], [], []
    text_rects = []
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            for s in line["spans"]:
                t = s["text"].strip()
                if not t:
                    continue
                text_rects.append(fitz.Rect(s["bbox"]))
                size, bold = s["size"], bool(s["flags"] & 16) or "Bold" in s["font"]
                if bold and re.fullmatch(r"[A-Za-z]", t) and size >= 7.5:
                    labels.append(t)
                    if t.isupper():
                        issues.append(("WARN", f"panel label '{t}' should be lowercase"))
                    if abs(size - 8) > 0.3:
                        issues.append(("WARN", f"panel label '{t}' is {size:.1f} pt (8 pt expected)"))
                    continue
                if size < 4.95:
                    small.append(f"'{t[:20]}' {size:.1f}")
                elif size > 7.05:
                    big.append(f"'{t[:20]}' {size:.1f}")
                c = s["color"]
                rgb = ((c >> 16) & 255, (c >> 8) & 255, c & 255)
                if max(rgb) - min(rgb) > 25 and rgb != (255, 255, 255):
                    coloured.append(f"'{t[:15]}'")
    if small:
        issues.append(("ERROR", f"{len(small)} text span(s) below 5 pt: " + ", ".join(small[:6])))
    if big:
        issues.append(("WARN", f"{len(big)} text span(s) above 7 pt: " + ", ".join(big[:6])))
    if coloured:
        issues.append(("WARN", f"{len(coloured)} coloured text span(s): " + ", ".join(coloured[:6])))
    info.append(f"panel labels: {''.join(labels) or 'none found'}")

    # drawings: line widths and colours
    thin, chroma, rects = 0, [], []
    drawings = page.get_drawings()
    area = page.rect.width * page.rect.height
    for d in drawings:
        r = fitz.Rect(d["rect"])
        if not (d.get("fill") and r.width * r.height > 0.9 * area):
            rects.append(r)
        wdt = d.get("width")
        if d.get("color") is not None and wdt is not None and wdt < 0.25:
            thin += 1
        for key in ("color", "fill"):
            c = d.get(key)
            if c and len(c) == 3:
                h, l, s = hue_of(c)
                if s > 0.18 and 0.08 < l < 0.97:
                    chroma.append(h)
    if thin:
        issues.append(("WARN", f"{thin} stroke(s) thinner than 0.25 pt (hairlines vanish in print)"))
    uniq = {round(h / 24) % 15 for h in chroma}
    if len(set(np.round(chroma, 0))) > 40:
        info.append("colour-mapped content detected; hue count and red/green check skipped")
    else:
        if len(uniq) > 5:
            issues.append(("WARN", f"{len(uniq)} distinct hues; keep 3-5 meaningful colours plus greys"))
        if any(h < 15 or h > 345 for h in chroma) and any(90 <= h <= 160 for h in chroma):
            issues.append(("WARN", "red and green used together (colour-blind readers)"))

    # rasters
    for im in page.get_image_info():
        bb = fitz.Rect(im["bbox"])
        rects.append(bb)
        if bb.width <= 0:
            continue
        d = im["width"] / (bb.width / 72)
        if d < 150:
            issues.append(("ERROR", f"raster image {im['width']}x{im['height']} px at {d:.0f} dpi"))
        elif d < 300:
            issues.append(("WARN", f"raster image {im['width']}x{im['height']} px at {d:.0f} dpi (< 300)"))

    # margins
    content = fitz.Rect()
    for r in rects + text_rects:
        r = r & page.rect
        if not r.is_empty:
            content |= r
    if not content.is_empty:
        m = [(content.x0 - page.rect.x0), (page.rect.x1 - content.x1),
             (content.y0 - page.rect.y0), (page.rect.y1 - content.y1)]
        m = [v / PT_PER_MM for v in m]
        if max(m) > 3:
            issues.append(("WARN", "empty margin (mm) left/right/top/bottom = "
                           + "/".join(f"{v:.1f}" for v in m) + " -> reduce the figure size"))

    # previews
    previews.mkdir(parents=True, exist_ok=True)
    pv = previews / f"{path.stem}_preview.png"
    page.get_pixmap(dpi=dpi, alpha=False).save(pv)
    pix = page.get_pixmap(dpi=min(dpi, 150), alpha=False)
    arr = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)
    ac = previews / f"{path.stem}_access.png"
    access_sheet(arr, ac)
    info.append(f"previews: {pv.as_posix()}, {ac.as_posix()}")
    seen, unique = set(), []
    for it in issues:
        if it not in seen:
            seen.add(it)
            unique.append(it)
    return unique, info


def check_raster(path, previews, width):
    from PIL import Image
    issues = []
    im = Image.open(path)
    w_mm = WIDTHS_MM.get(width, None) or float(width)
    d = im.size[0] / (w_mm / 25.4)
    info = [f"{im.size[0]}x{im.size[1]} px -> {d:.0f} dpi at {w_mm:.0f} mm width"]
    if d < 300:
        issues.append(("WARN", f"only {d:.0f} dpi at {w_mm:.0f} mm; Nature main figures should be vector PDF/EPS"))
    issues.append(("WARN", "raster figure: Nature prefers vector files (.pdf/.eps/.ai) with editable text"))
    previews.mkdir(parents=True, exist_ok=True)
    ac = previews / f"{path.stem}_access.png"
    rgb = np.asarray(im.convert("RGB"))
    if rgb.shape[1] > 1600:
        f = 1600 / rgb.shape[1]
        rgb = np.asarray(im.convert("RGB").resize((1600, int(rgb.shape[0] * f))))
    access_sheet(rgb, ac)
    info.append(f"preview: {ac.as_posix()}")
    return issues, info


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--previews", help="directory for previews (default: <file dir>/qa)")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--width", default="double", help="intended width for raster inputs")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    worst = 0
    for f in a.files:
        p = Path(f)
        previews = Path(a.previews) if a.previews else p.parent / "qa"
        if p.suffix.lower() in (".pdf", ".svg"):
            issues, info = check_pdf(p, previews, a.dpi)
        else:
            issues, info = check_raster(p, previews, a.width)
        print(f"== {p.name}")
        for i in info:
            print(f"   {i}")
        for lvl, msg in issues:
            print(f"   {lvl:5s} {msg}")
        if not issues:
            print("   OK    no automatic issues (now inspect the preview at final size)")
        worst = max(worst, 1 if any(l == "ERROR" for l, _ in issues) else 0)
    sys.exit(worst)


if __name__ == "__main__":
    main()
