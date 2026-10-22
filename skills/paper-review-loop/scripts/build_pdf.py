#!/usr/bin/env python3
"""Compile the working manuscript to PDF and report what a reviewer would trip over.

  build_pdf.py MAIN.tex  [--out PDF] [--engine auto|pdflatex|xelatex|lualatex|platex|uplatex|tectonic] [--no-latexmk]
  build_pdf.py MAIN.html [--out PDF]    headless Chrome / Edge / Chromium print-to-pdf
  build_pdf.py MAIN.md   [--out PDF]    pandoc

The engine is picked from the source (magic comment `% !TEX program = ...`, fontspec,
luatexja, jsarticle, ...). latexmk is used when it and perl are available, otherwise the
engine/bibtex/biber passes are run by hand.

Exit code is 0 only if a PDF was produced. The report lists LaTeX errors, undefined
references and citations, missing files, overfull boxes, page count and [AUTHOR TODO]s.
"""
import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

TIMEOUT = 300


def run(cmd, cwd, timeout=TIMEOUT):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT after {timeout}s: {' '.join(cmd)} (a TeX package-install dialog may be waiting)"
    except FileNotFoundError:
        return 127, f"not found: {cmd[0]}"


# ---------------------------------------------------------------- LaTeX

def pick_engine(tex):
    m = re.search(r"%\s*!TEX\s+(?:TS-)?program\s*=\s*(\w+)", tex, re.I)
    if m:
        return m.group(1).lower()
    cls = re.search(r"\\documentclass(?:\[([^\]]*)\])?\{([^}]+)\}", tex)
    opts, name = (cls.group(1) or "", cls.group(2)) if cls else ("", "")
    if re.fullmatch(r"u?(js|j|t)(article|book|report)|jsarticle|jsbook", name):
        return "uplatex" if (name.startswith("u") or "uplatex" in opts) else "platex"
    if name.startswith("ltjs") or re.search(r"\\usepackage(\[[^\]]*\])?\{luatexja", tex) or name == "jlreq":
        return "lualatex"
    if re.search(r"\\usepackage(\[[^\]]*\])?\{(fontspec|xeCJK|unicode-math|polyglossia)\}", tex):
        return "xelatex"
    return "pdflatex"


LATEXMK_FLAG = {"pdflatex": ["-pdf"], "xelatex": ["-xelatex"], "lualatex": ["-lualatex"]}
TEX_OPTS = ["-interaction=nonstopmode", "-file-line-error", "-halt-on-error"]


def latexmk(src, stem, engine):
    cmd = ["latexmk", *TEX_OPTS]
    rc_text = "".join(p.read_text(errors="ignore") for p in (src / ".latexmkrc", src / "latexmkrc") if p.exists())
    if "$pdf_mode" not in rc_text:
        if engine in LATEXMK_FLAG:
            cmd += LATEXMK_FLAG[engine]
        else:  # platex / uplatex -> dvi -> dvipdfmx
            cmd += ["-pdfdvi", f"-latex={engine} %O %S", "-e", "$dvipdf='dvipdfmx %O -o %D %S'"]
    return run(cmd + [f"{stem}.tex"], src, timeout=TIMEOUT * 3)


def manual(src, stem, engine):
    logs = []

    def tex():
        rc, out = run([engine, *TEX_OPTS, f"{stem}.tex"], src)
        logs.append(out)
        return rc

    if tex() != 0:
        return 1, "\n".join(logs)
    aux = (src / f"{stem}.aux").read_text(errors="ignore") if (src / f"{stem}.aux").exists() else ""
    if (src / f"{stem}.bcf").exists():
        logs.append(run(["biber", stem], src)[1])
    elif "\\bibdata" in aux:
        bib = "upbibtex" if engine == "uplatex" else ("pbibtex" if engine == "platex" else "bibtex")
        logs.append(run([bib if shutil.which(bib) else "bibtex", stem], src)[1])
    for _ in range(2):
        if tex() != 0:
            return 1, "\n".join(logs)
    if engine in ("platex", "uplatex"):
        rc, out = run(["dvipdfmx", f"{stem}.dvi"], src)
        logs.append(out)
        if rc != 0:
            return rc, "\n".join(logs)
    return 0, "\n".join(logs)


def parse_log(log):
    errors = []
    lines = log.splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith("! ") or re.match(r"^[^\s:][^:]*:\d+: ", ln):
            errors.append(" | ".join(x.strip() for x in lines[i:i + 3] if x.strip()))
    return {
        "errors": list(dict.fromkeys(errors))[:15],
        "undef_refs": sorted(set(re.findall(r"Reference `([^']+)' on page \d+\s*undefined", log))),
        "undef_cites": sorted(set(re.findall(r"Citation `([^']+)' on page \d+\s*undefined", log))),
        "missing": sorted(set(re.findall(r"File `([^']+)' not found", log))),
        "overfull": len(re.findall(r"^Overfull \\hbox", log, re.M)),
    }


def build_tex(main, engine, use_latexmk):
    src, stem = main.parent, main.stem
    tex = main.read_text(encoding="utf-8", errors="ignore")
    engine = pick_engine(tex) if engine == "auto" else engine
    if engine == "tectonic":
        rc, out = run(["tectonic", "--keep-logs", main.name], src, timeout=TIMEOUT * 3)
        how = "tectonic"
    elif use_latexmk and shutil.which("latexmk") and shutil.which("perl"):
        rc, out = latexmk(src, stem, engine)
        how = f"{engine} via latexmk"
        if rc != 0 and not (src / f"{stem}.log").exists():
            rc, out = manual(src, stem, engine)
            how = f"{engine} (manual passes)"
    else:
        if not shutil.which(engine):
            alt = next((e for e in ("tectonic",) if shutil.which(e)), None)
            if alt:
                return build_tex(main, alt, use_latexmk)
            return None, f"{engine} not found", {}
        rc, out = manual(src, stem, engine)
        how = f"{engine} (manual passes)"
    logf = src / f"{stem}.log"
    log = logf.read_text(encoding="utf-8", errors="replace") if logf.exists() else out
    info = parse_log(log)
    pdf = src / f"{stem}.pdf"
    ok = pdf.exists() and pdf.stat().st_mtime >= main.stat().st_mtime - 1 and not info["errors"]
    if rc == 124:
        info["errors"].insert(0, out.strip())
    return (pdf if ok else None), how, info


# ---------------------------------------------------------------- HTML / Markdown

def find_browser():
    names = ["chrome", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "msedge", "microsoft-edge"]
    found = [shutil.which(n) for n in names]
    pf = [os.environ.get(k, "") for k in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
    found += [str(Path(b) / rel) for b in pf if b for rel in (
        "Google/Chrome/Application/chrome.exe", "Microsoft/Edge/Application/msedge.exe", "Chromium/Application/chrome.exe")]
    found += ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
              "/Applications/Chromium.app/Contents/MacOS/Chromium"]
    return next((f for f in found if f and Path(f).exists()), None)


def build_html(main, out_pdf):
    browser = find_browser()
    if not browser:
        return None, "no Chrome/Edge/Chromium found", {"errors": ["install a Chromium-based browser or use LaTeX"]}
    out_pdf = out_pdf.resolve()
    with tempfile.TemporaryDirectory() as profile:
        cmd = [browser, "--headless=new", "--disable-gpu", f"--user-data-dir={profile}",
               "--no-pdf-header-footer", "--print-to-pdf-no-header", "--virtual-time-budget=20000",
               f"--print-to-pdf={out_pdf}", main.resolve().as_uri()]
        if platform.system() == "Linux":
            cmd.insert(1, "--no-sandbox")
        rc, out = run(cmd, main.parent, timeout=180)
    ok = out_pdf.exists()
    return (out_pdf if ok else None), Path(browser).name, {"errors": [] if ok else [out.strip()[-800:]]}


def build_md(main, out_pdf):
    if not shutil.which("pandoc"):
        return None, "pandoc not found", {"errors": ["no pandoc: write the manuscript as .tex or .html instead"]}
    cmd = ["pandoc", main.name, "-s", "-o", str(out_pdf.resolve())]
    for eng in ("xelatex", "lualatex", "pdflatex", "tectonic", "weasyprint"):
        if shutil.which(eng):
            cmd.append(f"--pdf-engine={eng}")
            break
    rc, out = run(cmd, main.parent)
    ok = rc == 0 and out_pdf.exists()
    return (out_pdf.resolve() if ok else None), "pandoc", {"errors": [] if ok else [out.strip()[-800:]]}


# ---------------------------------------------------------------- main

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("main")
    p.add_argument("--out", help="copy the finished PDF here (e.g. WS/rounds/r02/paper.pdf)")
    p.add_argument("--engine", default="auto")
    p.add_argument("--no-latexmk", action="store_true")
    a = p.parse_args()

    main_file = Path(a.main).resolve()
    if not main_file.exists():
        sys.exit(f"not found: {main_file}")
    suffix = main_file.suffix.lower()
    if suffix == ".tex":
        pdf, how, info = build_tex(main_file, a.engine, not a.no_latexmk)
    elif suffix in (".html", ".htm"):
        pdf, how, info = build_html(main_file, Path(a.out) if a.out else main_file.with_suffix(".pdf"))
    elif suffix == ".md":
        pdf, how, info = build_md(main_file, Path(a.out) if a.out else main_file.with_suffix(".pdf"))
    else:
        sys.exit("main file must be .tex, .html or .md")

    if pdf is None:
        print(f"BUILD FAILED ({how})")
        for e in info.get("errors", []):
            print("  " + e)
        for f in info.get("missing", []):
            print(f"  missing file: {f}")
        sys.exit(1)

    if a.out and Path(a.out).resolve() != Path(pdf).resolve():
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pdf, a.out)
    final = Path(a.out) if a.out else Path(pdf)

    pages, todos = "?", "?"
    try:
        from pdf_tools import page_texts
        texts = page_texts(str(final))
        pages, todos = len(texts), "\n".join(texts).count("AUTHOR TODO")
    except SystemExit:
        pass

    print(f"BUILD OK  [{how}]  pages={pages}  -> {final}")
    if suffix == ".tex":
        print(f"undefined refs: {len(info['undef_refs'])}  undefined citations: {len(info['undef_cites'])}  "
              f"missing files: {len(info['missing'])}  overfull hboxes: {info['overfull']}  AUTHOR TODO: {todos}")
        for k, label in (("undef_refs", "undefined refs"), ("undef_cites", "undefined citations"), ("missing", "missing files")):
            if info[k]:
                print(f"  {label}: {', '.join(info[k][:12])}")
    else:
        print(f"AUTHOR TODO: {todos}")


if __name__ == "__main__":
    main()
