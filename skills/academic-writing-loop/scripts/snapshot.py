#!/usr/bin/env python3
"""Freeze the manuscript source for a round and record what changed since the last one.

  snapshot.py SRC_DIR ROUND_DIR [--prev PREV_ROUND_DIR]

Copies the text sources (.tex .bib .sty .cls .bst .md .html .css .txt) of SRC_DIR into
ROUND_DIR/src/ and, with --prev, writes ROUND_DIR/changes.diff (unified diff against
PREV_ROUND_DIR/src/) and prints per-file +/- line counts. Figures and build artefacts
are not copied; they rarely change and would bloat every round.
"""
import argparse
import difflib
import shutil
import sys
from pathlib import Path

TEXT_EXT = {".tex", ".bib", ".sty", ".cls", ".bst", ".md", ".html", ".htm", ".css", ".txt"}


def text_files(root):
    return {p.relative_to(root).as_posix(): p for p in root.rglob("*")
            if p.is_file() and p.suffix.lower() in TEXT_EXT}


def read(p):
    return p.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True) if p else []


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("round_dir")
    ap.add_argument("--prev")
    a = ap.parse_args()

    src, dst = Path(a.src), Path(a.round_dir) / "src"
    if dst.exists():
        shutil.rmtree(dst)
    files = text_files(src)
    for rel, p in files.items():
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst / rel)
    print(f"snapshot: {len(files)} file(s) -> {dst}")

    if not a.prev:
        return
    prev_root = Path(a.prev) / "src"
    old = text_files(prev_root) if prev_root.exists() else {}
    new = text_files(dst)
    chunks, stats = [], []
    for rel in sorted(set(old) | set(new)):
        diff = list(difflib.unified_diff(read(old.get(rel)), read(new.get(rel)),
                                         fromfile=f"prev/{rel}", tofile=f"this/{rel}", n=2))
        if diff:
            chunks.extend(diff)
            plus = sum(1 for d in diff if d.startswith("+") and not d.startswith("+++"))
            minus = sum(1 for d in diff if d.startswith("-") and not d.startswith("---"))
            stats.append(f"  {rel}: +{plus} -{minus}")
    out = Path(a.round_dir) / "changes.diff"
    out.write_text("".join(chunks), encoding="utf-8")
    print(f"diff vs {a.prev}: {len(stats)} file(s) changed -> {out}")
    print("\n".join(stats) if stats else "  (no changes)")


if __name__ == "__main__":
    main()
