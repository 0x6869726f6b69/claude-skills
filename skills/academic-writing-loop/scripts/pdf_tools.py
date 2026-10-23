#!/usr/bin/env python3
"""PDF helpers for reviewing and for rebuilding a paper from its PDF.

  pdf_tools.py info    PDF
  pdf_tools.py text    PDF [-o OUT.txt]                       per-page text with "=== Page N ===" markers
  pdf_tools.py render  PDF -o DIR [--dpi 110] [--pages 1-3,7] [--grid]
                       --grid overlays a labelled 50pt grid so you can read off crop coordinates
  pdf_tools.py figures PDF -o DIR [--dpi 200] [--pages ...]   auto-crop figures found above "Figure N" captions
                       writes fig_<n>.pdf (vector) + fig_<n>.png (for checking) + figures.json
  pdf_tools.py crop    PDF --page N --bbox x0,y0,x1,y1 -o OUT.pdf|OUT.png [--dpi 200]
                       bbox in PDF points, origin top-left (same units as the --grid labels)
  pdf_tools.py check   PDF                                    page count, "??" / "[?]" markers, AUTHOR TODO count

PyMuPDF (`pip install pymupdf`) is used when present. Without it, `text` falls back to
pypdf or the pdftotext CLI and `render` to pdftoppm; `figures` and `crop` need PyMuPDF.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

CAPTION_RE = re.compile(r"^\s*(Figure|Fig\.|FIGURE|図)\s*([A-Z]?\d+(?:\.\d+)?)\s*[:.．：]?", re.I)
UNDEF_RE = re.compile(r"\?\?|\[\?\]|\(\?\)")


def need_fitz(what):
    if fitz is None:
        sys.exit(f"`{what}` needs PyMuPDF: pip install pymupdf")


def parse_pages(spec, n):
    if not spec:
        return list(range(n))
    out = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a) - 1, min(int(b), n)))
        elif part:
            out.append(int(part) - 1)
    return [p for p in out if 0 <= p < n]


def page_texts(pdf):
    """List of per-page strings, using whatever backend is available."""
    if not Path(pdf).exists():
        sys.exit(f"not found: {pdf}")
    if fitz is not None:
        with fitz.open(pdf) as doc:
            return [pg.get_text("text", sort=True) for pg in doc]
    try:
        from pypdf import PdfReader
        return [pg.extract_text() or "" for pg in PdfReader(pdf).pages]
    except ImportError:
        pass
    if shutil.which("pdftotext"):
        out = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True)
        pages = out.stdout.decode("utf-8", errors="replace").split("\f")
        return pages[:-1] if pages and not pages[-1].strip() else pages
    sys.exit("No PDF text backend: pip install pymupdf (or pypdf), or install poppler's pdftotext.")


# ---------------------------------------------------------------- commands

def cmd_info(a):
    texts = page_texts(a.pdf)
    words = sum(len(t.split()) for t in texts)
    info = {"pages": len(texts), "words": words}
    if fitz is not None:
        with fitz.open(a.pdf) as doc:
            r = doc[0].rect
            info.update(title=doc.metadata.get("title") or "", page_size_pt=[round(r.width), round(r.height)])
    print(json.dumps(info, ensure_ascii=False, indent=2))


def cmd_text(a):
    texts = page_texts(a.pdf)
    body = "".join(f"\n=== Page {i + 1} ===\n{t.rstrip()}\n" for i, t in enumerate(texts))
    if a.o:
        Path(a.o).parent.mkdir(parents=True, exist_ok=True)
        Path(a.o).write_text(body, encoding="utf-8")
        print(f"wrote {a.o} ({len(texts)} pages, {sum(len(t.split()) for t in texts)} words)")
    else:
        print(body)


def cmd_render(a):
    out = Path(a.o)
    out.mkdir(parents=True, exist_ok=True)
    if fitz is None:
        if not shutil.which("pdftoppm"):
            sys.exit("render needs PyMuPDF or pdftoppm")
        subprocess.run(["pdftoppm", "-png", "-r", str(a.dpi), str(a.pdf), str(out / "page")], check=True)
        print(f"rendered with pdftoppm into {out}")
        return
    doc = fitz.open(a.pdf)
    for pno in parse_pages(a.pages, len(doc)):
        page = doc[pno]
        if a.grid:
            W, H = page.rect.width, page.rect.height
            for x in range(0, int(W) + 1, 50):
                page.draw_line((x, 0), (x, H), color=(1, 0, 0), width=0.3)
                page.insert_text((x + 1, 7), str(x), fontsize=6, color=(1, 0, 0))
            for y in range(0, int(H) + 1, 50):
                page.draw_line((0, y), (W, y), color=(0, 0, 1), width=0.3)
                page.insert_text((1, y - 1), str(y), fontsize=6, color=(0, 0, 1))
        path = out / f"page_{pno + 1:03d}.png"
        page.get_pixmap(dpi=a.dpi).save(path)
        print(path)
    doc.close()  # grid edits are never saved to the source PDF


def save_crop(doc, pno, rect, stem, dpi):
    """Write a vector PDF crop and a PNG preview of `rect` on page `pno`."""
    out = fitz.open()
    pg = out.new_page(width=rect.width, height=rect.height)
    pg.show_pdf_page(pg.rect, doc, pno, clip=rect)
    out.save(f"{stem}.pdf", garbage=3, deflate=True)
    out.close()
    doc[pno].get_pixmap(dpi=dpi, clip=rect).save(f"{stem}.png")


def column_of(cap, W):
    mid = W / 2
    if cap.x0 < mid - 20 and cap.x1 > mid + 20:
        return 0, W
    return (0, mid) if cap.x1 <= mid + 10 else (mid, W)


def find_figure_rect(page, cap):
    W = page.rect.width
    cx0, cx1 = column_of(cap, W)
    half = cx1 - cx0 < W * 0.75

    def overlap(r):
        return max(0.0, min(r.x1, cx1) - max(r.x0, cx0))

    def in_col(r):  # mostly inside the caption's column
        return overlap(r) >= 0.6 * max(r.width, 1)

    graphics = [fitz.Rect(i["bbox"]) for i in page.get_image_info()]
    for d in page.get_drawings():
        r = fitz.Rect(d["rect"])
        if r.width >= 2 or r.height >= 2:
            graphics.append(r)
    graphics = [g for g in graphics if in_col(g) and g.y1 <= cap.y0 + 3 and g.height < page.rect.height * 0.95]

    blocks = [b for b in page.get_text("blocks") if b[6] == 0]
    # The figure sits between its caption and the nearest thing above it that is not part of
    # it: a body paragraph, an earlier caption, or (in a two-column layout) a block that
    # crosses the column gutter such as the title / author line.
    top = 0.0
    for b in blocks:
        r, text = fitz.Rect(b[:4]), b[4].strip()
        if r.y1 > cap.y0 - 1 or overlap(r) <= 0:
            continue
        crosses_gutter = half and r.x0 < W / 2 - 10 and r.x1 > W / 2 + 10
        if len(text) >= 80 or CAPTION_RE.match(text) or crosses_gutter:
            top = max(top, r.y1)
    parts = [g for g in graphics if g.y0 >= top - 2]
    labels = [fitz.Rect(b[:4]) for b in blocks
              if in_col(fitz.Rect(b[:4])) and b[1] >= top - 1 and b[3] <= cap.y0 + 1 and len(b[4].strip()) < 80]
    if not parts:
        return fitz.Rect(cx0 + 5, top, cx1 - 5, cap.y0 - 1), "low"
    rect = fitz.Rect(parts[0])
    for r in parts[1:] + labels:
        rect |= r
    rect = fitz.Rect(rect.x0 - 2, rect.y0 - 2, rect.x1 + 2, min(rect.y1 + 2, cap.y0)) & page.rect
    return rect, ("ok" if rect.height > 30 else "low")


def cmd_figures(a):
    need_fitz("figures")
    out = Path(a.o)
    out.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(a.pdf)
    # A paragraph may also start with "Figure 2 shows ...". Real captions are usually
    # "Figure 2:" / "Fig. 2." so prefer those, and fall back to the first plain match.
    best = {}
    for pno in parse_pages(a.pages, len(doc)):
        for b in doc[pno].get_text("blocks"):
            if b[6] != 0:
                continue
            m = CAPTION_RE.match(b[4].strip())
            if not m:
                continue
            strong = bool(re.match(r"\s*[:.．：]", b[4].strip()[m.end(2):]))
            label = m.group(2)
            if label not in best or (strong and not best[label][0]):
                best[label] = (strong, pno, b)
    manifest = []
    for label, (strong, pno, b) in best.items():
        rect, conf = find_figure_rect(doc[pno], fitz.Rect(b[:4]))
        stem = out / f"fig_{label.replace('.', '_')}"
        save_crop(doc, pno, rect, str(stem), a.dpi)
        manifest.append({
            "label": label, "page": pno + 1,
            "bbox": [round(v, 1) for v in rect],
            "confidence": conf if strong else "low",
            "pdf": f"{stem.name}.pdf", "png": f"{stem.name}.png",
            "caption": " ".join(b[4].split())[:300],
        })
    doc.close()
    (out / "figures.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    low = [m["label"] for m in manifest if m["confidence"] == "low"]
    print(f"{len(manifest)} figure(s) -> {out}" + (f"; check/redo with `crop`: {', '.join(low)}" if low else ""))
    print("Always look at the PNGs: a crop may cut off a legend or include neighbouring text.")


def cmd_crop(a):
    need_fitz("crop")
    doc = fitz.open(a.pdf)
    x0, y0, x1, y1 = (float(v) for v in a.bbox.split(","))
    rect = fitz.Rect(x0, y0, x1, y1) & doc[a.page - 1].rect
    o = Path(a.o)
    o.parent.mkdir(parents=True, exist_ok=True)
    if o.suffix.lower() == ".png":
        doc[a.page - 1].get_pixmap(dpi=a.dpi, clip=rect).save(o)
    else:
        save_crop(doc, a.page - 1, rect, str(o.with_suffix("")), a.dpi)
    doc.close()
    print(f"wrote {o}")


def cmd_check(a):
    texts = page_texts(a.pdf)
    full = "\n".join(texts)
    report = {
        "pages": len(texts),
        "undefined_markers": len(UNDEF_RE.findall(full)),
        "author_todo": full.count("AUTHOR TODO"),
    }
    hits = []
    for i, t in enumerate(texts):
        for m in UNDEF_RE.finditer(t):
            hits.append(f"p{i + 1}: …{t[max(0, m.start() - 40):m.end() + 20].strip()}…".replace("\n", " "))
    report["undefined_examples"] = hits[:10]
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("info"); s.add_argument("pdf"); s.set_defaults(fn=cmd_info)
    s = sub.add_parser("text"); s.add_argument("pdf"); s.add_argument("-o"); s.set_defaults(fn=cmd_text)
    s = sub.add_parser("render"); s.add_argument("pdf"); s.add_argument("-o", required=True)
    s.add_argument("--dpi", type=int, default=110); s.add_argument("--pages"); s.add_argument("--grid", action="store_true")
    s.set_defaults(fn=cmd_render)
    s = sub.add_parser("figures"); s.add_argument("pdf"); s.add_argument("-o", required=True)
    s.add_argument("--dpi", type=int, default=200); s.add_argument("--pages"); s.set_defaults(fn=cmd_figures)
    s = sub.add_parser("crop"); s.add_argument("pdf"); s.add_argument("--page", type=int, required=True)
    s.add_argument("--bbox", required=True); s.add_argument("-o", required=True); s.add_argument("--dpi", type=int, default=200)
    s.set_defaults(fn=cmd_crop)
    s = sub.add_parser("check"); s.add_argument("pdf"); s.set_defaults(fn=cmd_check)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
