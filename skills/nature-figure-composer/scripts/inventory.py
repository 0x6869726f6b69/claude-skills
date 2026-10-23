#!/usr/bin/env python3
"""List the analysis results in a project so they can be grouped into figures.

  inventory.py [ROOT] [--out inventory.md] [--sheet DIR] [--exclude DIR ...] [--max-files 3000]

Reports, with a running index (#1, #2, ...):
  figures   PNG/JPG/TIFF/PDF/SVG/EPS: size, pixel size, effective dpi at 89 / 183 mm width,
            vector or raster, Type 3 fonts (matplotlib default -> must be re-exported)
  data      CSV/TSV/XLSX/JSON/NPY/NPZ/H5/Parquet: shape, columns / keys
  code      .py/.ipynb/.R/.m: files it saves (savefig, ggsave, to_csv ...) and reads, so a plot can
            be traced back to the script and data that produced it; notebooks: embedded plot count
  docs      .tex/.md/.docx: manuscript drafts and notes that explain the story

--sheet DIR writes contact sheets (contact_sheet_1.png, ...) with numbered thumbnails of every
figure and every plot embedded in notebooks (extracted to DIR/notebook_images/). Look at them with
the Read tool to see what each result shows before planning the figures.
Pickle files are listed but never unpickled.
"""
import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path

IMG = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp"}
VEC = {".pdf", ".svg", ".eps"}
DATA = {".csv", ".tsv", ".xlsx", ".xls", ".json", ".npy", ".npz", ".h5", ".hdf5", ".parquet",
        ".feather", ".mat", ".pkl", ".pickle", ".txt", ".dat"}
CODE = {".py", ".ipynb", ".r", ".m", ".jl"}
DOCS = {".tex", ".md", ".docx", ".rst"}
SKIP_DIRS = {"node_modules", "__pycache__", "venv", ".venv", "env", "site-packages", ".git",
             ".ipynb_checkpoints", ".mypy_cache", ".pytest_cache", "wandb", "mlruns"}
MM_PER_IN = 25.4

SAVE_RE = re.compile(r"""(?:savefig|ggsave|imwrite|imsave|to_csv|to_excel|to_parquet|np\.save[z]?|"""
                     r"""save|write_image|export|print)\s*\(\s*(?:[\w.]+\s*,\s*)?[rbf]*["']([^"']+\.\w{2,5})["']""")
READ_RE = re.compile(r"""(?:read_csv|read_table|read_excel|read_parquet|read_json|np\.load|load|"""
                     r"""loadtxt|genfromtxt|open|imread|Image\.open|fitz\.open|h5py\.File)\s*\(\s*[rbf]*["']([^"']+\.\w{2,5})["']""")


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def walk(root, max_files, exclude=()):
    out = []
    exclude = {Path(e).resolve() for e in exclude}
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS and not x.startswith(".")
                         and (Path(d) / x).resolve() not in exclude)
        for f in sorted(files):
            p = Path(d) / f
            if p.suffix.lower() in IMG | VEC | DATA | CODE | DOCS:
                out.append(p)
                if len(out) >= max_files:
                    return out, True
    return out, False


def describe_image(p):
    try:
        from PIL import Image
        with Image.open(p) as im:
            w, h = im.size
            meta = im.info.get("dpi")
        dpi89 = w / (89 / MM_PER_IN)
        dpi183 = w / (183 / MM_PER_IN)
        note = f"{w}x{h} px; eff. dpi @89 mm {dpi89:.0f}, @183 mm {dpi183:.0f}"
        if meta:
            note += f"; file dpi {meta[0]:.0f}"
        return note
    except Exception as e:
        return f"unreadable ({e.__class__.__name__})"


def describe_vector(p):
    ext = p.suffix.lower()
    if ext == ".eps":
        return "EPS (convert to PDF to compose: ps2pdf -dEPSCrop)"
    try:
        import fitz
        doc = fitz.open(p)
        if ext == ".svg":
            doc = fitz.open("pdf", doc.convert_to_pdf())
        page = doc[0]
        w, h = page.rect.width * MM_PER_IN / 72, page.rect.height * MM_PER_IN / 72
        fonts = page.get_fonts(full=True)
        type3 = any(f[2] == "Type3" for f in fonts)
        rasters = len(page.get_images())
        parts = [f"{len(doc)} page(s), {w:.0f}x{h:.0f} mm"]
        if rasters:
            parts.append(f"{rasters} embedded raster(s)")
        if type3:
            parts.append("Type 3 fonts (re-export with pdf.fonttype=42)")
        if not page.get_text().strip():
            parts.append("no text layer")
        return "; ".join(parts)
    except Exception as e:
        return f"vector ({e.__class__.__name__})"


def describe_data(p):
    ext = p.suffix.lower()
    size = p.stat().st_size
    try:
        if ext in (".csv", ".tsv", ".txt", ".dat"):
            import pandas as pd
            sep = "\t" if ext == ".tsv" else None
            df = pd.read_csv(p, sep=sep, engine="python", nrows=5)
            rows = "?"
            if size < 200 * 1024 ** 2:
                with open(p, "rb") as f:
                    rows = sum(1 for _ in f) - 1
            cols = list(map(str, df.columns))
            more = f" +{len(cols) - 15} more" if len(cols) > 15 else ""
            out = f"{rows} rows x {len(cols)} cols: {', '.join(cols[:15])}{more}"
            if size < 30 * 1024 ** 2:      # categorical columns -> groups and n per group
                full = pd.read_csv(p, sep=sep, engine="python")
                cats = []
                for c in full.columns:
                    vc = full[c].value_counts(sort=False)
                    if full[c].dtype == object and 1 < len(vc) <= 30 or c.lower() in ("seed", "run", "fold", "rep", "replicate") and len(vc) <= 50:
                        shown = ", ".join(f"{k} ({v})" for k, v in list(vc.items())[:8])
                        cats.append(f"{c}: {len(vc)} values [{shown}{', …' if len(vc) > 8 else ''}]")
                if cats:
                    out += "<br>" + "<br>".join(cats[:5])
            return out
        if ext in (".xlsx", ".xls"):
            import pandas as pd
            xl = pd.ExcelFile(p)
            parts = []
            for sh in xl.sheet_names[:6]:
                df = xl.parse(sh, nrows=3)
                parts.append(f"[{sh}] {', '.join(map(str, df.columns[:10]))}")
            return "; ".join(parts)
        if ext == ".json":
            if size > 20 * 1024 ** 2:
                return "large JSON"
            obj = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(obj, dict):
                return "keys: " + ", ".join(list(map(str, obj))[:15])
            if isinstance(obj, list):
                return f"list of {len(obj)}" + (f"; item keys: {', '.join(list(obj[0])[:10])}"
                                               if obj and isinstance(obj[0], dict) else "")
            return type(obj).__name__
        if ext == ".npy":
            import numpy as np
            a = np.load(p, mmap_mode="r", allow_pickle=False)
            return f"array {a.shape} {a.dtype}"
        if ext == ".npz":
            import numpy as np
            with np.load(p, allow_pickle=False) as z:
                return "; ".join(f"{k} {z[k].shape}" for k in list(z.keys())[:12])
        if ext in (".h5", ".hdf5"):
            try:
                import h5py
            except ImportError:
                return "HDF5 (h5py not installed)"
            items = []
            with h5py.File(p, "r") as f:
                f.visititems(lambda n, o: items.append(f"{n} {o.shape}") if hasattr(o, "shape") else None)
            return "; ".join(items[:12])
        if ext in (".parquet", ".feather"):
            import pandas as pd
            df = pd.read_parquet(p) if ext == ".parquet" else pd.read_feather(p)
            return f"{len(df)} rows: {', '.join(map(str, df.columns[:15]))}"
        if ext in (".pkl", ".pickle"):
            return "pickle (not opened)"
        if ext == ".mat":
            return "MATLAB file"
    except Exception as e:
        return f"unreadable ({e.__class__.__name__}: {str(e)[:60]})"
    return ""


def code_text(p):
    if p.suffix.lower() == ".ipynb":
        try:
            nb = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return "", nb_empty()
        src = "\n".join("".join(c.get("source", [])) for c in nb.get("cells", []) if c.get("cell_type") == "code")
        return src, nb
    try:
        return p.read_text(encoding="utf-8", errors="replace"), None
    except Exception:
        return "", None


def nb_empty():
    return {"cells": []}


def notebook_images(nb):
    out = []
    for ci, cell in enumerate(nb.get("cells", [])):
        for oi, o in enumerate(cell.get("outputs", []) or []):
            data = o.get("data", {})
            if "image/png" in data:
                b = data["image/png"]
                out.append((ci, oi, base64.b64decode("".join(b) if isinstance(b, list) else b)))
    return out


def find_font():
    cands = ["C:/Windows/Fonts/meiryo.ttc", "C:/Windows/Fonts/YuGothM.ttc", "C:/Windows/Fonts/msgothic.ttc",
             "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc", "/System/Library/Fonts/Hiragino Sans GB.ttc",
             "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf"]
    for c in cands:
        if Path(c).exists():
            return c
    return None


def thumb(path_or_bytes, box):
    from PIL import Image
    import io
    if isinstance(path_or_bytes, bytes):
        im = Image.open(io.BytesIO(path_or_bytes))
    else:
        p = Path(path_or_bytes)
        if p.suffix.lower() in (".pdf", ".svg"):
            import fitz
            doc = fitz.open(p)
            if p.suffix.lower() == ".svg":
                doc = fitz.open("pdf", doc.convert_to_pdf())
            pix = doc[0].get_pixmap(dpi=110, alpha=False)
            im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        else:
            im = Image.open(p)
            try:
                im.seek(0)
            except Exception:
                pass
    im = im.convert("RGBA")
    bg = Image.new("RGBA", im.size, "white")
    bg.alpha_composite(im)
    im = bg.convert("RGB")
    im.thumbnail(box)
    return im


def contact_sheets(entries, outdir, per_sheet=20, cols=4, cell=(420, 340)):
    from PIL import Image, ImageDraw, ImageFont
    outdir.mkdir(parents=True, exist_ok=True)
    font_path = find_font()
    font = ImageFont.truetype(font_path, 15) if font_path else ImageFont.load_default()
    paths = []
    for s in range(0, len(entries), per_sheet):
        chunk = entries[s:s + per_sheet]
        rows = (len(chunk) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * cell[0], rows * cell[1]), "white")
        draw = ImageDraw.Draw(sheet)
        for k, (idx, name, src) in enumerate(chunk):
            x, y = (k % cols) * cell[0], (k // cols) * cell[1]
            try:
                im = thumb(src, (cell[0] - 16, cell[1] - 44))
                sheet.paste(im, (x + 8 + (cell[0] - 16 - im.width) // 2, y + 8))
            except Exception as e:
                draw.text((x + 10, y + 40), f"cannot render: {e.__class__.__name__}", fill="red", font=font)
            draw.rectangle([x + 2, y + 2, x + cell[0] - 3, y + cell[1] - 3], outline="#cccccc")
            label = f"#{idx} {name}"
            if len(label) > 44:
                label = label[:20] + "…" + label[-23:]
            draw.text((x + 8, y + cell[1] - 30), label, fill="black", font=font)
        path = outdir / f"contact_sheet_{s // per_sheet + 1}.png"
        sheet.save(path)
        paths.append(path)
    return paths


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--out", help="write the markdown report here (default: stdout)")
    ap.add_argument("--sheet", help="directory for contact sheets of all figures")
    ap.add_argument("--exclude", action="append", default=[], help="directory to skip (repeatable)")
    ap.add_argument("--max-files", type=int, default=3000)
    a = ap.parse_args()

    root = Path(a.root).resolve()
    files, truncated = walk(root, a.max_files, exclude=a.exclude + ([a.sheet] if a.sheet else []))
    rel = lambda p: p.relative_to(root).as_posix()

    figs = [p for p in files if p.suffix.lower() in IMG | VEC]
    data = [p for p in files if p.suffix.lower() in DATA]
    code = [p for p in files if p.suffix.lower() in CODE]
    docs = [p for p in files if p.suffix.lower() in DOCS]

    producers, consumers, nb_imgs = {}, {}, []
    for p in code:
        src, nb = code_text(p)
        for m in SAVE_RE.findall(src):
            producers.setdefault(Path(m).name, set()).add(rel(p))
        for m in READ_RE.findall(src):
            consumers.setdefault(rel(p), set()).add(Path(m).name)
        if nb:
            for ci, oi, png in notebook_images(nb):
                nb_imgs.append((p, ci, oi, png))

    lines = [f"# Results inventory: {root}", "",
             f"{len(figs)} figure files, {len(data)} data files, {len(code)} code files, "
             f"{len(docs)} documents, {len(nb_imgs)} plots embedded in notebooks"
             + (f" (stopped at {a.max_files} files)" if truncated else ""), ""]
    sheet_entries = []
    idx = 0

    lines += ["## Figures", "", "| # | file | size | details | made by |", "|---|---|---|---|---|"]
    for p in figs:
        idx += 1
        det = describe_image(p) if p.suffix.lower() in IMG else describe_vector(p)
        made = ", ".join(sorted(producers.get(p.name, []))) or ""
        lines.append(f"| {idx} | {rel(p)} | {human(p.stat().st_size)} | {det} | {made} |")
        if p.suffix.lower() != ".eps":
            sheet_entries.append((idx, rel(p), p))

    if nb_imgs:
        lines += ["", "## Plots embedded in notebooks", "", "| # | notebook | cell | saved as |", "|---|---|---|---|"]
        nb_dir = Path(a.sheet) / "notebook_images" if a.sheet else None
        for p, ci, oi, png in nb_imgs:
            idx += 1
            saved = ""
            if nb_dir:
                nb_dir.mkdir(parents=True, exist_ok=True)
                out = nb_dir / f"{p.stem}_cell{ci}_{oi}.png"
                out.write_bytes(png)
                saved = out.as_posix()
            lines.append(f"| {idx} | {rel(p)} | {ci} | {saved} |")
            sheet_entries.append((idx, f"{p.name} cell {ci}", png))

    lines += ["", "## Data", "", "| # | file | size | contents | made by | read by |",
              "|---|---|---|---|---|---|"]
    readers = {}
    for script, names in consumers.items():
        for n in names:
            readers.setdefault(n, set()).add(script)
    for p in data:
        idx += 1
        lines.append(f"| {idx} | {rel(p)} | {human(p.stat().st_size)} | {describe_data(p)} | "
                     f"{', '.join(sorted(producers.get(p.name, [])))} | "
                     f"{', '.join(sorted(readers.get(p.name, [])))} |")
    lines += ["", "Figures and data written by the same script usually show the same numbers: "
              "re-plot from the data file instead of reusing the image."]

    lines += ["", "## Code", "", "| # | file | writes | reads |", "|---|---|---|---|"]
    writes = {}
    for name, scripts in producers.items():
        for s in scripts:
            writes.setdefault(s, set()).add(name)
    for p in code:
        idx += 1
        r = rel(p)
        w = ", ".join(sorted(writes.get(r, [])))[:160]
        rd = ", ".join(sorted(consumers.get(r, [])))[:160]
        lines.append(f"| {idx} | {r} | {w} | {rd} |")

    if docs:
        lines += ["", "## Documents (story / manuscript)", ""]
        for p in docs:
            idx += 1
            lines.append(f"- #{idx} {rel(p)} ({human(p.stat().st_size)})")

    if a.sheet and sheet_entries:
        paths = contact_sheets(sheet_entries, Path(a.sheet))
        lines += ["", "## Contact sheets", ""] + [f"- {q.as_posix()}" for q in paths]

    report = "\n".join(lines) + "\n"
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(report, encoding="utf-8")
        print(f"wrote {a.out}")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(report)


if __name__ == "__main__":
    main()
