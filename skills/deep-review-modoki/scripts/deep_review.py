#!/usr/bin/env python3
"""Workspace helper for deep-review-modoki (segment -> parallel review -> merge -> verify -> synthesize).

  deep_review.py init    INPUT [--ws DIR] [--depth quick|standard|deep] [--focus TEXT] [--venue TEXT]
                         [--lang ja|en] [--dpi 150] [--no-render] [--force]
        INPUT is a .pdf (or .md / .txt / .tex). Creates the workspace and writes paper.txt (per-page text
        with "=== Page N ===" markers), pages/page_NNN.png and pages.json (outline + density per page).
  deep_review.py plan    WS   validate segments.json and write plan.json (which agent reviews what)
  deep_review.py merge   WS   candidates/*.json -> schema check, grounding, clustering -> merged.json
  deep_review.py collate WS   merged.json + verdicts/*.json -> collated.json (input for synthesis)
  deep_review.py render  WS [--check]   findings.json -> report.md + report.html

Grounding = does a finding's verbatim `quote` really occur in paper.txt (whitespace, hyphenation and
punctuation are ignored, so PDF extraction noise does not matter) and on which page.
"""
import argparse
import datetime as dt
import difflib
import html
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pdf_tools import fitz, page_texts  # noqa: E402

DEPTHS = ("quick", "standard", "deep")
TRACKS = ("light", "medium", "high", "none")
FAMILY = {
    "intro": "narrative", "related_work": "narrative", "discussion": "narrative",
    "references": "narrative", "other": "narrative",
    "method": "method", "algorithm": "method", "system": "method",
    "theory": "proof", "appendix_proofs": "proof",
    "experiments": "empirical", "analysis": "empirical", "appendix_experiments": "empirical",
}
ANGLES = {
    "proof": {"A": "逐行検証", "B": "反例・境界・仮定", "C": "依存関係・定数の監査"},
    "method": {"A": "アルゴリズムの正しさ", "B": "前提・失敗条件・隠れコスト", "C": "記述と評価の整合"},
    "empirical": {"A": "数値の再計算", "B": "実験設計・交絡・リーク", "C": "主張・図表・本文の整合"},
    "narrative": {"A": "主張の棚卸しと整合", "B": "前提・定義の精査", "C": "他節との整合"},
}
TRACES = {
    "quick": {"light": 1, "medium": 1, "high": 1},
    "standard": {"light": 1, "medium": 1, "high": 2},
    "deep": {"light": 1, "medium": 2, "high": 3},
}
LIGHT_BUNDLE = {"quick": 3, "standard": 2, "deep": 1}
EFFORT = {"quick": {}, "standard": {"high": "high"}, "deep": {"high": "xhigh", "medium": "high"}}
LENSES = {"quick": ["L0"], "standard": ["L1", "L2", "L3"], "deep": ["L1", "L2", "L3"]}
LENS_NAMES = {
    "L0": "統合レンズ（ストーリー＋新規性＋整合性）",
    "L1": "ストーリーと主張–証拠",
    "L2": "新規性・重要性（文献確認）",
    "L3": "整合性・図表・引用",
}
TYPES = ("major", "minor", "suggestion")
TYPE_RANK = {t: i for i, t in enumerate(TYPES)}
ID_PREFIX = {"major": "MJ", "minor": "MN", "suggestion": "SG"}
CATEGORIES = ("proof", "math", "claim_evidence", "experiment", "statistics", "data_consistency",
              "novelty", "related_work", "citation", "notation", "clarity", "presentation",
              "reproducibility", "other")
ASPECT = {
    "proof": "validity", "math": "validity", "claim_evidence": "validity", "experiment": "validity",
    "statistics": "validity", "data_consistency": "validity",
    "novelty": "novelty", "related_work": "novelty",
    "citation": "clarity", "notation": "clarity", "clarity": "clarity", "presentation": "clarity",
    "reproducibility": "reproducibility", "other": "other",
}
VERIFY_MINOR_CATS = {"proof", "math", "statistics", "data_consistency", "experiment"}
VERDICTS = ("confirmed", "plausible", "refuted", "cannot_locate")
CONFIDENCE = ("high", "medium", "low")
VERIFICATION = ("confirmed", "plausible", "unverified")

GRAM = 6            # char n-gram size for fuzzy grounding
FUZZY_OK = 0.7      # share of the quote's n-grams that must occur on one page
MIN_QUOTE_KEY = 12  # shorter quotes are too ambiguous to ground

MATH_CHARS = set("=<>+±×÷·∑∏∫∮√∞∂∇≤≥≈≠≡∝∈∉⊂⊃⊆⊇∪∩∧∨¬∀∃→←↔⇒⇔↦|^_{}")
EQNUM_RE = re.compile(r"\(\d{1,3}[a-z]?\)\s*$")
THM_RE = re.compile(r"\b(Theorem|Lemma|Proposition|Corollary|Claim)\s+[A-Z]?\d|定理|補題|命題")
PROOF_RE = re.compile(r"\bProof\b|証明")
DEF_RE = re.compile(r"\b(Definition|Assumption)\s+[A-Z]?\d|定義|仮定")
CAPTION_RE = re.compile(r"^\s*((?:(?:Figure|Fig\.|Table)\s*[A-Z]?\d+\s*[:.]|(?:図|表)\s*\d+)[^\n]{0,70})", re.I)
HEAD_NUM_RE = re.compile(r"^\s*((?:\d{1,2}(?:\.\d{1,2}){0,3}|[A-H](?:\.\d{1,2}){1,3})\.?\s+[A-Z぀-ヿ一-鿿].*)$")
HEAD_KW_RE = re.compile(
    r"^\s*((?:Abstract|Introduction|Related Work|Background|Preliminaries|Problem Setup|Methods?|Methodology|"
    r"Experiments?|Results|Evaluation|Discussion|Conclusions?|Limitations|References|Bibliography|"
    r"Acknowledge?ments?|Appendix(?:\s+[A-Z])?[^\n]{0,60}|概要|要旨|はじめに|序論|関連研究|手法|提案手法|実験|"
    r"結果|考察|結論|おわりに|参考文献|謝辞|付録[^\n]{0,30}))\s*$", re.I)

LABELS = {
    "ja": {
        "title": "Deep Review レポート", "generated": "生成日", "depth": "深さ", "focus": "焦点",
        "venue": "投稿先", "none": "なし",
        "disclaimer": "このレポートは AI が生成した助言で、誤りを含む可能性があります。指摘はご自身で確認してから原稿に反映してください。スコアは付けていません。",
        "overall": "Overall Feedback", "summary": "貢献の要約", "strengths": "強み", "concerns": "主な懸念",
        "bottom_line": "総括", "previous": "前回レビューの指摘の対応状況",
        "detailed": "Detailed Feedback", "major": "Major concerns", "minor": "Minor corrections",
        "suggestion": "Suggestions", "all": "すべて", "view_report": "レポート順", "view_page": "ページ順",
        "problem": "問題", "evidence": "根拠・検証", "impact": "影響", "fix": "提案",
        "confidence": "確信度", "verification": "検証", "support": "独立検出",
        "appendix": "付録", "method": "レビューの方法", "profile": "観点の分布", "limitations": "このレビューの限界",
        "conf": {"high": "高", "medium": "中", "low": "低"},
        "verif": {"confirmed": "反証検証で確認", "plausible": "妥当（未確定）", "unverified": "未検証"},
        "status": {"resolved": "解決", "partially_resolved": "一部解決", "open": "未解決"},
        "cat": {"proof": "証明", "math": "数式・計算", "claim_evidence": "主張と証拠", "experiment": "実験設計",
                "statistics": "統計", "data_consistency": "数値の整合", "novelty": "新規性",
                "related_work": "関連研究", "citation": "引用・文献", "notation": "記法", "clarity": "明確さ",
                "presentation": "図表・体裁", "reproducibility": "再現性", "other": "その他"},
        "aspect": {"validity": "妥当性", "novelty": "新規性・位置づけ", "clarity": "明確さ・体裁",
                   "reproducibility": "再現性", "other": "その他"},
        "m_segments": "セグメント", "m_tasks": "検証エージェント", "m_lenses": "レンズ", "m_cands": "候補",
        "m_clusters": "重複排除後", "m_verified": "反証検証", "m_dropped": "除外（反証・所在不明）",
        "m_final": "最終的な指摘",
    },
    "en": {
        "title": "Deep Review report", "generated": "Generated", "depth": "Depth", "focus": "Focus",
        "venue": "Venue", "none": "none",
        "disclaimer": "This report is AI-generated advice and may contain mistakes. Check each point before changing the manuscript. No scores are given.",
        "overall": "Overall Feedback", "summary": "Summary of contributions", "strengths": "Strengths",
        "concerns": "Main concerns", "bottom_line": "Bottom line", "previous": "Status of the previous review's findings",
        "detailed": "Detailed Feedback", "major": "Major concerns", "minor": "Minor corrections",
        "suggestion": "Suggestions", "all": "All", "view_report": "Report order", "view_page": "Page order",
        "problem": "Issue", "evidence": "Evidence / check", "impact": "Impact", "fix": "Suggestion",
        "confidence": "Confidence", "verification": "Verification", "support": "Found by",
        "appendix": "Appendix", "method": "How this review was made", "profile": "Focus profile",
        "limitations": "Limitations of this review",
        "conf": {"high": "high", "medium": "medium", "low": "low"},
        "verif": {"confirmed": "confirmed by refutation check", "plausible": "plausible", "unverified": "unverified"},
        "status": {"resolved": "resolved", "partially_resolved": "partially resolved", "open": "open"},
        "cat": {c: c.replace("_", " ") for c in CATEGORIES},
        "aspect": {"validity": "validity", "novelty": "novelty / positioning", "clarity": "clarity / presentation",
                   "reproducibility": "reproducibility", "other": "other"},
        "m_segments": "Segments", "m_tasks": "Review agents", "m_lenses": "Lenses", "m_cands": "Candidates",
        "m_clusters": "After de-duplication", "m_verified": "Refutation-checked", "m_dropped": "Dropped (refuted / not found)",
        "m_final": "Final findings",
    },
}


# ---------------------------------------------------------------- helpers

def load_json(path, default=None):
    path = Path(path)
    if not path.exists():
        if default is not None:
            return default
        sys.exit(f"not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"invalid JSON in {path}: {e}")


def save_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def key(s):
    """Comparison key: NFKC, lower case, letters and digits only (drops spaces, hyphens, math symbols)."""
    s = unicodedata.normalize("NFKC", s or "").lower()
    return "".join(ch for ch in s if ch.isalnum())


def grams(k):
    return {k[i:i + GRAM] for i in range(max(0, len(k) - GRAM + 1))}


def parse_pages(v, n=None):
    """int | "4-6,13" | [4, "5-6"] -> sorted page list (1-based)."""
    out = set()
    items = v if isinstance(v, list) else [v]
    for it in items:
        if it is None or it == "":
            continue
        if isinstance(it, int):
            out.add(it)
            continue
        for part in str(it).replace("–", "-").split(","):
            part = re.sub(r"[^\d-]", "", part)
            if not part:
                continue
            if "-" in part:
                a, b = part.split("-", 1)
                if a and b:
                    out.update(range(int(a), int(b) + 1))
            else:
                out.add(int(part))
    return sorted(p for p in out if p >= 1 and (n is None or p <= n))


def read_pages(ws):
    """paper.txt -> list of page strings."""
    txt = (Path(ws) / "paper.txt").read_text(encoding="utf-8")
    parts = re.split(r"\n=== Page \d+ ===\n", "\n" + txt.lstrip("\n"))
    return parts[1:] if parts and not parts[0].strip() else parts


class Grounder:
    def __init__(self, pages):
        self.keys = [key(p) for p in pages]
        self.grams = [grams(k) for k in self.keys]
        self.doc = "".join(self.keys)

    def check(self, quote, pages_hint=()):
        """-> (status, matched_pages). status: exact | fuzzy | not_found | too_short | absent"""
        q = key(quote)
        if not q:
            return "absent", []
        if len(q) < MIN_QUOTE_KEY:
            hits = [i + 1 for i, k in enumerate(self.keys) if q in k]
            return "too_short", hits
        hits = [i + 1 for i, k in enumerate(self.keys) if q in k]
        if hits:
            return "exact", hits
        if q in self.doc:  # quote spans a page break
            pos = self.doc.find(q)
            acc = 0
            for i, k in enumerate(self.keys):
                if acc + len(k) > pos:
                    return "exact", [i + 1, i + 2]
                acc += len(k)
        qg = grams(q)
        best, best_p = 0.0, None
        for i, g in enumerate(self.grams):
            share = len(qg & g) / len(qg)
            if share > best or (share == best and (i + 1) in pages_hint):
                best, best_p = share, i + 1
        if best >= FUZZY_OK:
            return "fuzzy", [best_p]
        return "not_found", []


def loc_pages(loc):
    if isinstance(loc, dict):
        return parse_pages(loc.get("page", loc.get("pages")))
    return parse_pages(loc)


def loc_str(loc):
    if not isinstance(loc, dict):
        return str(loc or "")
    pages = loc_pages(loc)
    parts = []
    if pages:
        parts.append(f"p.{pages[0]}" if len(pages) == 1 else f"pp.{pages[0]}–{pages[-1]}")
    for k in ("section", "anchor"):
        if loc.get(k):
            parts.append(str(loc[k]))
    return " ｜ ".join(parts)


def lang_of(ws):
    lang = load_json(Path(ws) / "config.json").get("lang", "ja")
    return lang if lang in LABELS else "en"


# ---------------------------------------------------------------- init

def pseudo_pages(text, size=3500):
    pages, cur = [], ""
    for para in re.split(r"\n\s*\n", text):
        if cur and len(cur) + len(para) > size:
            pages.append(cur)
            cur = ""
        cur += para + "\n\n"
    if cur.strip():
        pages.append(cur)
    return pages or [""]


def math_density(t):
    chars = [c for c in t if not c.isspace()]
    if not chars:
        return 0.0
    m = sum(1 for c in chars if c in MATH_CHARS or "Ͱ" <= c <= "Ͽ"
            or "←" <= c <= "⋿" or "\U0001d400" <= c <= "\U0001d7ff")
    return round(m / len(chars), 3)


def page_profile(i, t):
    lines = t.splitlines()
    heads, caps, skip_head = [], [], False
    for j, ln in enumerate(lines):
        s = ln.strip()
        m = CAPTION_RE.match(s)
        if m:
            caps.append(m.group(1))
        if skip_head:  # already used as the title of a bare section number
            skip_head = False
            continue
        # LaTeX PDFs often put the section number on its own line: "2" / "Problem Setup"
        if re.fullmatch(r"\d{1,2}(?:\.\d{1,2}){0,3}\.?", s) and j + 1 < len(lines):
            nxt = lines[j + 1].strip()
            if (len(nxt) <= 60 and re.match(r"[A-Z][a-z]|[぀-ヿ一-鿿]", nxt)
                    and not nxt.endswith(".") and not set(nxt) & set("()[]=∈≤≥<>")):
                s, skip_head = f"{s} {nxt}", True
        if not s or len(s) > 70:
            continue
        if HEAD_KW_RE.match(s) or (HEAD_NUM_RE.match(s) and not s.endswith(".") and len(s.split()) <= 10
                                    and sum(c.isdigit() for c in s) < len(s) / 3):
            heads.append(s)
    return {
        "page": i + 1,
        "words": len(t.split()),
        "chars": len(t),
        "math_density": math_density(t),
        "eq_numbers": sum(1 for ln in lines if EQNUM_RE.search(ln)),
        "thm": len(THM_RE.findall(t)),
        "proof": len(PROOF_RE.findall(t)),
        "defs": len(DEF_RE.findall(t)),
        "headings": heads[:12],
        "captions": caps[:8],
    }


def render_pages(pdf, out, dpi):
    if fitz is not None:
        with fitz.open(pdf) as doc:
            for pno, page in enumerate(doc):
                page.get_pixmap(dpi=dpi).save(out / f"page_{pno + 1:03d}.png")
        return True
    if shutil.which("pdftoppm"):
        subprocess.run(["pdftoppm", "-png", "-r", str(dpi), str(pdf), str(out / "tmp")], check=True)
        for f in out.glob("tmp-*.png"):
            n = int(re.search(r"(\d+)\.png$", f.name).group(1))
            f.replace(out / f"page_{n:03d}.png")
        return True
    return False


GENERATED = ("segments.json", "plan.json", "merged.json", "collated.json", "findings.json",
             "report.md", "report.html", "critique.md")


def cmd_init(a):
    src = Path(a.input).resolve()
    if not src.exists():
        sys.exit(f"not found: {src}")
    ws = Path(a.ws).resolve() if a.ws else src.parent / f"{src.stem}_deep_review"
    if (ws / "config.json").exists() and not a.force:
        sys.exit(f"workspace already exists: {ws}\n  resume from it, or pass --force to start over")
    try:
        ws.mkdir(parents=True, exist_ok=True)
    except OSError:
        if a.ws:
            raise
        ws = Path.cwd() / f"{src.stem}_deep_review"
        ws.mkdir(parents=True, exist_ok=True)
    if a.force:  # drop results of the previous run so they cannot mix with the new one
        for d in ("candidates", "verdicts", "pages"):
            shutil.rmtree(ws / d, ignore_errors=True)
        for f in GENERATED:
            (ws / f).unlink(missing_ok=True)
    for d in ("input", "pages", "candidates", "verdicts", "work"):
        (ws / d).mkdir(exist_ok=True)
    if src.parent != ws / "input":
        shutil.copy2(src, ws / "input" / src.name)

    is_pdf = src.suffix.lower() == ".pdf"
    texts = page_texts(src) if is_pdf else pseudo_pages(src.read_text(encoding="utf-8", errors="replace"))
    (ws / "paper.txt").write_text(
        "".join(f"\n=== Page {i + 1} ===\n{t.rstrip()}\n" for i, t in enumerate(texts)), encoding="utf-8")

    pages = [page_profile(i, t) for i, t in enumerate(texts)]
    warnings = []
    for p in pages:
        if p["chars"] < 200:
            warnings.append(f"p{p['page']}: almost no text (figure-only or scanned?) -> read pages/page_{p['page']:03d}.png")
    total_words = sum(p["words"] for p in pages)
    if is_pdf and total_words < 150 * len(pages):
        warnings.append("text extraction is sparse: the PDF may be scanned. Rely on the page images.")
    bad = sum(t.count("�") for t in texts)
    if bad:
        warnings.append(f"{bad} undecodable characters (U+FFFD) in the extracted text: check math/symbols on the page images.")

    rendered = False
    if is_pdf and not a.no_render:
        rendered = render_pages(src, ws / "pages", a.dpi)
        if not rendered:
            warnings.append("could not render page images (install pymupdf or poppler). Agents will only have text.")

    config = {
        "skill": "deep-review-modoki", "input": str(src), "input_copy": f"input/{src.name}",
        "is_pdf": is_pdf, "pseudo_pages": not is_pdf, "n_pages": len(texts), "words": total_words,
        "page_images": rendered, "depth": a.depth, "focus": a.focus or "", "venue": a.venue or "",
        "lang": a.lang, "created": dt.datetime.now().isoformat(timespec="seconds"),
    }
    save_json(ws / "config.json", config)
    save_json(ws / "pages.json", {"n_pages": len(texts), "pages": pages, "warnings": warnings})

    print(f"workspace : {ws}")
    print(f"pages     : {len(texts)}{' (pseudo pages)' if not is_pdf else ''}   words: {total_words}   "
          f"images: {'pages/page_NNN.png' if rendered else 'none'}")
    print(f"depth     : {a.depth}   focus: {a.focus or '-'}   venue: {a.venue or '-'}")
    print("\noutline (math = share of math symbols, eq = numbered equations, thm/prf = theorem-like / proof markers)")
    print(" page  words  math  eq  thm/prf  headings  |  captions")
    for p in pages:
        caps = ("  |  " + "; ".join(c[:28] for c in p["captions"][:3])) if p["captions"] else ""
        print(f" {p['page']:>4}  {p['words']:>5}  {p['math_density']:.2f}  {p['eq_numbers']:>2}  "
              f"{p['thm']:>3}/{p['proof']:<3}  {'; '.join(h[:40] for h in p['headings'][:4])}{caps}")
    for w in warnings:
        print("WARN:", w)
    print(f"\nnext: write {ws / 'segments.json'} then run: deep_review.py plan \"{ws}\"")


# ---------------------------------------------------------------- plan

def cmd_plan(a):
    ws = Path(a.ws)
    cfg = load_json(ws / "config.json")
    n, depth = cfg["n_pages"], cfg["depth"]
    segs = load_json(ws / "segments.json")
    segs = segs.get("segments", segs) if isinstance(segs, dict) else segs
    errors, warns, covered, ids = [], [], set(), set()
    for s in segs:
        sid = s.get("id")
        if not sid or sid in ids:
            errors.append(f"segment id missing or duplicated: {sid!r}")
        ids.add(sid)
        if s.get("theme") not in FAMILY:
            errors.append(f"{sid}: theme must be one of {sorted(FAMILY)}")
        if s.get("track") not in TRACKS:
            errors.append(f"{sid}: track must be one of {TRACKS}")
        if s.get("track") == "none" and not s.get("reason"):
            errors.append(f"{sid}: track 'none' needs a reason (e.g. references are checked by lens L3)")
        raw = s.get("pages")
        pages = parse_pages(raw)
        if not pages:
            errors.append(f"{sid}: no pages")
        out_of_range = [p for p in pages if p > n]
        if out_of_range:
            errors.append(f"{sid}: pages beyond the document ({n} pages): {out_of_range}")
        s["_pages"] = [p for p in pages if p <= n]
        covered.update(s["_pages"])
        if s.get("track") == "high" and len(s["_pages"]) > 10:
            warns.append(f"{sid}: {len(s['_pages'])} pages on the high track - consider splitting it")
    missing = sorted(set(range(1, n + 1)) - covered)
    if missing:
        errors.append(f"pages not covered by any segment: {missing}")
    if errors:
        print("segments.json is invalid:")
        for e in errors:
            print("  -", e)
        sys.exit(1)

    tasks = []

    def add(**kw):
        kw["id"] = f"T{len(tasks) + 1:02d}"
        tag = kw.get("lens") or "+".join(kw["segments"]) + "_" + kw["trace"]
        kw["output"] = f"candidates/{kw['id']}_{tag}.json"
        tasks.append(kw)

    def info(s):
        return {"id": s["id"], "title": s.get("title", ""), "theme": s["theme"], "family": FAMILY[s["theme"]],
                "pages": s["_pages"], "notes": s.get("notes", "")}

    for s in segs:
        if s["track"] in ("none", "light"):
            continue
        fam = FAMILY[s["theme"]]
        for t in "ABC"[:TRACES[depth][s["track"]]]:
            add(kind="segment", segments=[s["id"]], segment_info=[info(s)], track=s["track"], trace=t,
                angle=ANGLES[fam][t], pages=s["_pages"], effort=EFFORT[depth].get(s["track"]))
    light = [s for s in segs if s["track"] == "light"]
    b = LIGHT_BUNDLE[depth]
    for i in range(0, len(light), b):
        grp = light[i:i + b]
        add(kind="segment", segments=[s["id"] for s in grp], segment_info=[info(s) for s in grp], track="light",
            trace="A", angle=" / ".join(sorted({ANGLES[FAMILY[s["theme"]]]["A"] for s in grp})),
            pages=sorted({p for s in grp for p in s["_pages"]}), effort=None)
    for lens in LENSES[depth]:
        add(kind="lens", lens=lens, angle=LENS_NAMES[lens], pages="all", effort=None)

    for s in segs:
        s.pop("_pages", None)
    plan = {"depth": depth, "n_pages": n, "focus": cfg.get("focus", ""), "venue": cfg.get("venue", ""),
            "tasks": tasks, "created": dt.datetime.now().isoformat(timespec="seconds")}
    save_json(ws / "plan.json", plan)

    print(f"plan: {len(tasks)} agents (depth={depth}) -> {ws / 'plan.json'}")
    for t in tasks:
        done = "  [done]" if (ws / t["output"]).exists() else ""
        what = f"lens {t['lens']}" if t["kind"] == "lens" else f"{'+'.join(t['segments'])} [{t['track']}] trace {t['trace']}"
        pages = "all" if t["pages"] == "all" else ",".join(map(str, t["pages"]))
        eff = f"  effort={t['effort']}" if t.get("effort") else ""
        print(f"  {t['id']}  {what:<28} {t['angle']:<22} pages {pages:<14} -> {t['output']}{eff}{done}")
    for w in warns:
        print("WARN:", w)


# ---------------------------------------------------------------- merge

REQUIRED = ("id", "type", "category", "title", "location", "explanation")


def cmd_merge(a):
    ws = Path(a.ws)
    cfg = load_json(ws / "config.json")
    depth = cfg["depth"]
    plan = load_json(ws / "plan.json", default={"tasks": []})
    by_output = {t["output"]: t for t in plan["tasks"]}
    grounder = Grounder(read_pages(ws))

    cands, invalid, lens_notes, files = [], [], {}, []
    for f in sorted((ws / "candidates").glob("*.json")):
        rel = f"candidates/{f.name}"
        d = load_json(f)
        items = d.get("candidates", []) if isinstance(d, dict) else d
        task = by_output.get(rel, {})
        tid = (d.get("task_id") if isinstance(d, dict) else None) or task.get("id") or f.stem.split("_")[0]
        if task.get("lens"):
            tag = task["lens"]
        elif task.get("segments"):
            tag = "+".join(task["segments"]) + "-" + task.get("trace", "")
        else:
            tag = f.stem
        files.append(rel)
        if isinstance(d, dict) and d.get("overall_notes"):
            lens_notes[task.get("lens") or tid] = d["overall_notes"]
        for c in items:
            miss = [k for k in REQUIRED if not c.get(k)]
            if miss or c.get("type") not in TYPES:
                invalid.append({"file": rel, "id": c.get("id"), "problem": f"missing {miss}" if miss else f"type={c.get('type')!r}"})
                continue
            if c["category"] not in CATEGORIES:
                c["category"] = "other"
            c["task_id"], c["source"] = tid, f"{tid}/{tag}"
            c["_pages"] = loc_pages(c["location"])
            status, hits = grounder.check(c.get("quote", ""), c["_pages"])
            note = ""
            if status in ("exact", "fuzzy") and c["_pages"] and not any(abs(h - p) <= 1 for h in hits for p in c["_pages"]):
                note = f"quote found on p.{hits} but location says p.{c['_pages']}"
            c["ground"] = {"status": status, "pages": hits, "note": note}
            c["_qk"], c["_tk"] = key(c.get("quote", "")), key(c["title"])
            cands.append(c)
    missing = [o for o in by_output if not (ws / o).exists()]

    # cluster near-duplicates (advisory: the synthesis agent makes the final call)
    parent = list(range(len(cands)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    qgrams = [grams(c["_qk"]) if len(c["_qk"]) >= MIN_QUOTE_KEY else set() for c in cands]
    for i in range(len(cands)):
        for j in range(i + 1, len(cands)):
            x, y = cands[i], cands[j]
            tsim = difflib.SequenceMatcher(None, x["_tk"], y["_tk"]).ratio()
            same = False
            if qgrams[i] and qgrams[j]:
                overlap = len(qgrams[i] & qgrams[j]) / min(len(qgrams[i]), len(qgrams[j]))
                same = overlap >= 0.6 and (x["category"] == y["category"] or tsim >= 0.35)
            if not same and set(x["_pages"]) & set(y["_pages"]) and x["category"] == y["category"]:
                same = tsim >= 0.55
            if same:
                parent[find(i)] = find(j)
    groups = {}
    for i in range(len(cands)):
        groups.setdefault(find(i), []).append(cands[i])

    order = {"exact": 0, "fuzzy": 1, "too_short": 2, "absent": 3, "not_found": 4}
    clusters = []
    for members in groups.values():
        members.sort(key=lambda c: (TYPE_RANK[c["type"]], order[c["ground"]["status"]]))
        top = members[0]
        ctype = top["type"]
        statuses = {m["ground"]["status"] for m in members}
        cats = sorted({m["category"] for m in members})
        ungrounded = statuses <= {"not_found"}
        need = (ctype == "major"
                or (depth == "deep" and ctype == "minor" and VERIFY_MINOR_CATS & set(cats))
                or (ungrounded and ctype != "suggestion"))
        clusters.append({
            "type": ctype, "title": top["title"], "categories": cats,
            "pages": sorted({p for m in members for p in m["_pages"]}),
            "support": len({m["task_id"] for m in members}), "sources": sorted({m["source"] for m in members}),
            "ground": min(statuses, key=order.get), "needs_verification": bool(need),
            "members": [{k: v for k, v in m.items() if not k.startswith("_")} for m in members],
        })
    clusters.sort(key=lambda c: (TYPE_RANK[c["type"]], -c["support"], c["pages"][:1] or [9999]))
    for i, c in enumerate(clusters):
        c["id"] = f"K{i + 1:02d}"

    # verification batches, grouped by where the issue was found
    size = 3 if depth == "deep" else 4
    buckets = {}
    for c in clusters:
        if c["needs_verification"]:
            src = c["members"][0]["source"].split("/", 1)[-1].split("-")[0]
            buckets.setdefault(src, []).append(c)
    chunks = [cs[i:i + size] for cs in buckets.values() for i in range(0, len(cs), size)]
    full, partial = [c for c in chunks if len(c) == size], sorted((c for c in chunks if len(c) < size), key=len, reverse=True)
    for c in partial:  # pack leftovers so that no verifier gets a single cluster when others could share
        for f in full:
            if len(f) + len(c) <= size:
                f.extend(c)
                break
        else:
            full.append(c)
    verify = []
    for chunk in full:
        verify.append({"id": f"V{len(verify) + 1:02d}", "clusters": [c["id"] for c in chunk],
                       "pages": sorted({p for c in chunk for p in c["pages"]}),
                       "output": f"verdicts/V{len(verify) + 1:02d}.json"})

    profile = {}
    for c in clusters:
        asp = ASPECT[c["categories"][0]]
        profile[asp] = profile.get(asp, 0) + 1
    merged = {"depth": depth, "n_candidates": len(cands), "files": files, "missing_outputs": missing,
              "invalid": invalid, "lens_notes": lens_notes, "focus_profile": profile,
              "clusters": clusters, "verify_tasks": verify}
    save_json(ws / "merged.json", merged)

    by_type = {t: sum(c["type"] == t for c in clusters) for t in TYPES}
    print(f"merged {len(cands)} candidates from {len(files)} files -> {len(clusters)} clusters "
          f"(major {by_type['major']}, minor {by_type['minor']}, suggestion {by_type['suggestion']})")
    print(f"support>=2: {sum(c['support'] >= 2 for c in clusters)}   "
          f"ungrounded (quote not in paper): {sum(c['ground'] == 'not_found' for c in clusters)}")
    print("focus profile:", ", ".join(f"{k}={v}" for k, v in sorted(profile.items())) or "-")
    if "novelty" not in profile:
        print("NOTE: no novelty/positioning findings - make sure the lens notes on novelty reach the overall feedback")
    if missing:
        print("WARN: missing agent outputs:", ", ".join(missing))
    for x in invalid:
        print(f"WARN: invalid candidate {x['file']} {x['id']}: {x['problem']}")
    print(f"\nverification: {len(verify)} agents for {sum(len(v['clusters']) for v in verify)} clusters")
    for v in verify:
        print(f"  {v['id']}  {', '.join(v['clusters'])}  pages {','.join(map(str, v['pages']))} -> {v['output']}")


# ---------------------------------------------------------------- collate

def cmd_collate(a):
    ws = Path(a.ws)
    merged = load_json(ws / "merged.json")
    verdicts = {}
    for f in sorted((ws / "verdicts").glob("*.json")):
        d = load_json(f)
        for v in (d.get("verdicts", []) if isinstance(d, dict) else d):
            if v.get("verdict") not in VERDICTS:
                print(f"WARN: {f.name}: {v.get('cluster')} has verdict {v.get('verdict')!r}")
                continue
            verdicts.setdefault(v.get("cluster"), []).append(v)
    missing, counts = [], {}
    for c in merged["clusters"]:
        vs = verdicts.get(c["id"], [])
        kinds = {v["verdict"] for v in vs}
        if not vs:
            status = "unverified"
            if c["needs_verification"]:
                missing.append(c["id"])
        elif "confirmed" in kinds and "refuted" in kinds:
            status = "conflict"
        else:
            status = vs[0]["verdict"]
        c["verification"] = {"status": status, "verdicts": vs}
        c["drop_recommended"] = status in ("refuted", "cannot_locate")
        counts[status] = counts.get(status, 0) + 1
    kept = [c for c in merged["clusters"] if not c["drop_recommended"]]
    merged["stats"] = {"clusters": len(merged["clusters"]), "kept": len(kept), "verification": counts,
                       "kept_by_type": {t: sum(c["type"] == t for c in kept) for t in TYPES}}
    save_json(ws / "collated.json", merged)
    print(f"collated -> {ws / 'collated.json'}")
    print("verification:", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print("kept by type:", merged["stats"]["kept_by_type"], f"(dropped {len(merged['clusters']) - len(kept)})")
    if missing:
        print("WARN: clusters that needed verification but have no verdict:", ", ".join(missing))


# ---------------------------------------------------------------- render

def validate_findings(F, grounder, n_pages):
    errors, warns = [], []
    if not isinstance(F.get("title"), str) or not F["title"].strip():
        errors.append("title is missing")
    ov = F.get("overall") or {}
    for k in ("summary", "bottom_line"):
        if not isinstance(ov.get(k), str) or not ov[k].strip():
            errors.append(f"overall.{k} is missing")
    for k in ("strengths", "concerns"):
        if not isinstance(ov.get(k), list) or not ov[k]:
            errors.append(f"overall.{k} must be a non-empty list")
    seen = set()
    for f in F.get("findings", []):
        fid = f.get("id", "?")
        if fid in seen:
            errors.append(f"{fid}: duplicated id")
        seen.add(fid)
        if f.get("type") not in TYPES:
            errors.append(f"{fid}: type must be one of {TYPES}")
            continue
        if not re.fullmatch(ID_PREFIX[f["type"]] + r"\d+", fid):
            errors.append(f"{fid}: id of a {f['type']} must look like {ID_PREFIX[f['type']]}1")
        for k in ("title", "explanation"):
            if not f.get(k):
                errors.append(f"{fid}: {k} is missing")
        if f["type"] != "suggestion" and not f.get("suggestion"):
            errors.append(f"{fid}: suggestion (how to fix) is missing")
        if f.get("category") not in CATEGORIES:
            warns.append(f"{fid}: unknown category {f.get('category')!r} (shown as 'other')")
        if f.get("confidence", "medium") not in CONFIDENCE:
            errors.append(f"{fid}: confidence must be one of {CONFIDENCE}")
        if f.get("verification", "unverified") not in VERIFICATION:
            errors.append(f"{fid}: verification must be one of {VERIFICATION}")
        pages = loc_pages(f.get("location"))
        if any(p > n_pages for p in pages):
            errors.append(f"{fid}: page beyond the document ({n_pages} pages)")
        if f["type"] == "major" and f.get("verification") == "unverified":
            warns.append(f"{fid}: a major concern that was never refutation-checked")
        if f.get("quote"):
            status, hits = grounder.check(f["quote"], pages)
            if status == "not_found":
                errors.append(f"{fid}: quote not found in the paper - copy it verbatim from paper.txt or drop it")
            elif status in ("exact", "fuzzy") and pages and not any(abs(h - p) <= 1 for h in hits for p in pages):
                warns.append(f"{fid}: quote is on p.{hits}, location says p.{pages}")
    if not F.get("findings"):
        warns.append("no findings at all")
    return errors, warns


def method_stats(ws, F):
    segs = load_json(ws / "segments.json", default={"segments": []})
    segs = segs.get("segments", segs) if isinstance(segs, dict) else segs
    plan = load_json(ws / "plan.json", default={"tasks": []})
    col = load_json(ws / "collated.json", default={})
    st = col.get("stats", {})
    ver = st.get("verification", {})
    return {
        "segments": len(segs),
        "tasks": sum(t["kind"] == "segment" for t in plan["tasks"]),
        "lenses": sum(t["kind"] == "lens" for t in plan["tasks"]),
        "candidates": col.get("n_candidates", 0),
        "clusters": st.get("clusters", 0),
        "verified": sum(v for k, v in ver.items() if k != "unverified"),
        "dropped": ver.get("refuted", 0) + ver.get("cannot_locate", 0),
        "final": {t: sum(f.get("type") == t for f in F.get("findings", [])) for t in TYPES},
    }


def badge_line(f, L):
    bits = [f"{L['confidence']}: {L['conf'].get(f.get('confidence', 'medium'), '-')}",
            f"{L['verification']}: {L['verif'].get(f.get('verification', 'unverified'), '-')}"]
    if f.get("support", 0) >= 2:
        bits.append(f"{L['support']}: {f['support']}")
    return " ｜ ".join(bits)


def md_quote(q):
    return "\n".join("> " + ln for ln in q.strip().splitlines())


def render_md(F, cfg, stats, L):
    out = [f"# {L['title']}: {F['title']}", ""]
    meta = (f"{L['generated']}: {dt.date.today().isoformat()} ｜ {L['depth']}: {cfg.get('depth')} ｜ "
            f"{L['focus']}: {cfg.get('focus') or L['none']} ｜ {L['venue']}: {cfg.get('venue') or L['none']}")
    out += [f"> {meta}", ">", f"> {L['disclaimer']}", ""]
    fin = stats["final"]
    out += [f"**{L['major']}: {fin['major']} ｜ {L['minor']}: {fin['minor']} ｜ {L['suggestion']}: {fin['suggestion']}**", ""]
    ov = F["overall"]
    out += [f"## {L['overall']}", "", f"### {L['summary']}", "", ov["summary"].strip(), "",
            f"### {L['strengths']}", ""] + [f"- {s}" for s in ov["strengths"]] + \
           ["", f"### {L['concerns']}", ""] + [f"- {s}" for s in ov["concerns"]] + \
           ["", f"### {L['bottom_line']}", "", ov["bottom_line"].strip(), ""]
    if F.get("previous"):
        out += [f"### {L['previous']}", "", "| ID | | |", "|---|---|---|"]
        for p in F["previous"]:
            out.append(f"| {p.get('id', '')} {p.get('title', '')} | {L['status'].get(p.get('status'), p.get('status', ''))} | {p.get('note', '')} |")
        out.append("")
    out += [f"## {L['detailed']}", ""]
    groups = {t: [f for f in F.get("findings", []) if f.get("type") == t] for t in TYPES}
    # major: full blocks
    out += [f"### {L['major']} ({len(groups['major'])})", ""]
    for f in groups["major"]:
        out += [f"#### {f['id']}［{L['cat'].get(f.get('category'), f.get('category', ''))}］{f['title']}", "",
                f"*{loc_str(f.get('location'))}* ｜ {badge_line(f, L)}", ""]
        if f.get("quote"):
            out += [md_quote(f["quote"]), ""]
        out.append(f"**{L['problem']}**: {f['explanation'].strip()}")
        for k, lab in (("evidence", "evidence"), ("impact", "impact"), ("suggestion", "fix")):
            if f.get(k):
                out.append(f"\n**{L[lab]}**: {f[k].strip()}")
        out.append("")
    # minor: compact list
    out += [f"### {L['minor']} ({len(groups['minor'])})", ""]
    for f in groups["minor"]:
        out.append(f"- **{f['id']}**［{L['cat'].get(f.get('category'), f.get('category', ''))}］**{f['title']}** — {loc_str(f.get('location'))}")
        if f.get("quote"):
            out.append(f"  - 「{' '.join(f['quote'].split())}」")
        out.append(f"  - {f['explanation'].strip()}")
        if f.get("suggestion"):
            out.append(f"  - → {f['suggestion'].strip()}")
    out.append("")
    # suggestions: medium blocks
    out += [f"### {L['suggestion']} ({len(groups['suggestion'])})", ""]
    for f in groups["suggestion"]:
        out += [f"#### {f['id']}［{L['cat'].get(f.get('category'), f.get('category', ''))}］{f['title']}", "",
                f"*{loc_str(f.get('location'))}*", "", f["explanation"].strip()]
        if f.get("suggestion"):
            out += ["", f"**{L['fix']}**: {f['suggestion'].strip()}"]
        out.append("")
    # appendix
    prof = {}
    for f in F.get("findings", []):
        asp = ASPECT.get(f.get("category"), "other")
        prof[asp] = prof.get(asp, 0) + 1
    out += [f"## {L['appendix']}", "", f"### {L['method']}", "",
            f"- {L['m_segments']}: {stats['segments']} ／ {L['m_tasks']}: {stats['tasks']} ／ {L['m_lenses']}: {stats['lenses']}",
            f"- {L['m_cands']}: {stats['candidates']} → {L['m_clusters']}: {stats['clusters']} → "
            f"{L['m_verified']}: {stats['verified']} ／ {L['m_dropped']}: {stats['dropped']}",
            f"- {L['m_final']}: Major {fin['major']} ／ Minor {fin['minor']} ／ Suggestions {fin['suggestion']}", ""]
    if F.get("method_notes"):
        out += [F["method_notes"].strip(), ""]
    out += [f"### {L['profile']}", "", " ／ ".join(f"{L['aspect'][k]}: {v}" for k, v in sorted(prof.items())) or "-", ""]
    if F.get("limitations"):
        out += [f"### {L['limitations']}", ""] + [f"- {x}" for x in F["limitations"]] + [""]
    return "\n".join(out)


CSS = """
:root{--bg:#f7f6f3;--fg:#1c1c1e;--muted:#66666d;--card:#ffffff;--line:#e4e1db;--quote:#f1eee8;--chip:#ece9e3;
--major:#b42318;--minor:#a15c07;--sugg:#1d5bbf;--accent:#3a3a40}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#151517;--fg:#ececf0;--muted:#a2a2aa;
--card:#1e1e22;--line:#303036;--quote:#26262b;--chip:#2b2b31;--major:#f97066;--minor:#fdb022;--sugg:#84adff;--accent:#d0d0d6}}
:root[data-theme="dark"]{--bg:#151517;--fg:#ececf0;--muted:#a2a2aa;--card:#1e1e22;--line:#303036;--quote:#26262b;
--chip:#2b2b31;--major:#f97066;--minor:#fdb022;--sugg:#84adff;--accent:#d0d0d6}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.7 system-ui,-apple-system,"Segoe UI","Hiragino Sans","Yu Gothic UI","Meiryo",sans-serif}
main{max-width:920px;margin:0 auto;padding:28px 16px 72px}
h1{font-size:1.45rem;line-height:1.35;margin:0 0 6px}h2{font-size:1.15rem;margin:36px 0 12px;padding-bottom:6px;border-bottom:1px solid var(--line)}
h3{font-size:1rem;margin:20px 0 6px}
.meta,.note{color:var(--muted);font-size:.86rem;margin:2px 0}
.counts{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 0}
.pill{border-radius:999px;padding:2px 12px;font-size:.84rem;font-weight:600;background:var(--chip)}
.pill.major{color:var(--major)}.pill.minor{color:var(--minor)}.pill.suggestion{color:var(--sugg)}
.bottom{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:8px;padding:10px 14px}
ul{padding-left:1.3em;margin:6px 0}
.toolbar{display:flex;gap:10px;flex-wrap:wrap;justify-content:space-between;margin:8px 0 14px}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden}
.seg button{border:0;background:var(--card);color:var(--fg);padding:6px 12px;font:inherit;font-size:.85rem;cursor:pointer}
.seg button+button{border-left:1px solid var(--line)}.seg button.on{background:var(--accent);color:var(--bg)}
.card{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--line);border-radius:8px;padding:12px 14px;margin:0 0 10px}
.card.major{border-left-color:var(--major)}.card.minor{border-left-color:var(--minor)}.card.suggestion{border-left-color:var(--sugg)}
.card h3{margin:0 0 4px;font-size:.98rem}.card .id{font-variant-numeric:tabular-nums;margin-right:6px}
.tag{display:inline-block;font-size:.75rem;padding:0 8px;border-radius:999px;background:var(--chip);color:var(--muted);margin-right:6px}
.card .t-major{color:var(--major)}.card .t-minor{color:var(--minor)}.card .t-suggestion{color:var(--sugg)}
blockquote{margin:8px 0;padding:6px 12px;background:var(--quote);border-radius:6px;font-size:.88rem;overflow-wrap:anywhere}
.field{margin:6px 0}.field b{font-weight:600}
code{font-family:ui-monospace,Consolas,monospace;font-size:.88em;background:var(--chip);padding:0 4px;border-radius:4px}
table{border-collapse:collapse;width:100%;font-size:.88rem}td,th{border:1px solid var(--line);padding:4px 8px;text-align:left;vertical-align:top}
"""

JS = """
const box=document.getElementById('cards');const cards=[...box.querySelectorAll('.card')];
document.querySelectorAll('[data-filter]').forEach(b=>b.addEventListener('click',()=>{
 document.querySelectorAll('[data-filter]').forEach(x=>x.classList.toggle('on',x===b));
 const f=b.dataset.filter;cards.forEach(c=>{c.hidden=!(f==='all'||c.dataset.type===f)});}));
document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>{
 document.querySelectorAll('[data-view]').forEach(x=>x.classList.toggle('on',x===b));
 const k=b.dataset.view==='page'?'page':'order';
 cards.slice().sort((x,y)=>(+x.dataset[k])-(+y.dataset[k])||(+x.dataset.order)-(+y.dataset.order)).forEach(c=>box.appendChild(c));}));
"""


def fmt(s):
    s = html.escape((s or "").strip())
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return s.replace("\n", "<br>")


def render_html(F, cfg, stats, L):
    e = html.escape
    fin = stats["final"]
    ov = F["overall"]
    lang = "ja" if L is LABELS["ja"] else "en"
    meta = (f"{L['generated']}: {dt.date.today().isoformat()} ｜ {L['depth']}: {cfg.get('depth')} ｜ "
            f"{L['focus']}: {cfg.get('focus') or L['none']} ｜ {L['venue']}: {cfg.get('venue') or L['none']}")
    h = [f"<!doctype html><html lang='{lang}'><head><meta charset='utf-8'>"
         f"<meta name='viewport' content='width=device-width,initial-scale=1'><title>Deep Review: {e(F['title'][:60])}</title>"
         f"<style>{CSS}</style></head><body><main>",
         f"<header><h1>{e(F['title'])}</h1><p class='meta'>{e(L['title'])} ｜ {e(meta)}</p>"
         f"<p class='note'>{e(L['disclaimer'])}</p><div class='counts'>"]
    for t in TYPES:
        h.append(f"<span class='pill {t}'>{e(L[t])}: {fin[t]}</span>")
    h.append("</div></header>")
    h.append(f"<section><h2>{e(L['overall'])}</h2><h3>{e(L['summary'])}</h3><p>{fmt(ov['summary'])}</p>"
             f"<h3>{e(L['strengths'])}</h3><ul>{''.join(f'<li>{fmt(s)}</li>' for s in ov['strengths'])}</ul>"
             f"<h3>{e(L['concerns'])}</h3><ul>{''.join(f'<li>{fmt(s)}</li>' for s in ov['concerns'])}</ul>"
             f"<h3>{e(L['bottom_line'])}</h3><div class='bottom'>{fmt(ov['bottom_line'])}</div>")
    if F.get("previous"):
        h.append(f"<h3>{e(L['previous'])}</h3><table>")
        for p in F["previous"]:
            h.append(f"<tr><td>{e(str(p.get('id', '')))} {fmt(p.get('title', ''))}</td>"
                     f"<td>{e(L['status'].get(p.get('status'), str(p.get('status', ''))))}</td><td>{fmt(p.get('note', ''))}</td></tr>")
        h.append("</table>")
    h.append("</section>")

    total = len(F.get("findings", []))
    h.append(f"<section><h2>{e(L['detailed'])}</h2><div class='toolbar'><div class='seg' role='group'>"
             f"<button data-filter='all' class='on'>{e(L['all'])} ({total})</button>")
    for t in TYPES:
        h.append(f"<button data-filter='{t}'>{e(L[t])} ({fin[t]})</button>")
    h.append(f"</div><div class='seg' role='group'><button data-view='report' class='on'>{e(L['view_report'])}</button>"
             f"<button data-view='page'>{e(L['view_page'])}</button></div></div><div id='cards'>")
    ordered = sorted(F.get("findings", []), key=lambda f: TYPE_RANK.get(f.get("type"), 9))
    for i, f in enumerate(ordered):
        t = f.get("type", "minor")
        pages = loc_pages(f.get("location"))
        cat = L["cat"].get(f.get("category"), f.get("category", ""))
        h.append(f"<article class='card {t}' data-type='{t}' data-order='{i}' data-page='{pages[0] if pages else 9999}'>"
                 f"<h3><span class='id t-{t}'>{e(f.get('id', ''))}</span>{fmt(f.get('title', ''))}</h3>"
                 f"<div><span class='tag'>{e(L[t])}</span><span class='tag'>{e(cat)}</span>"
                 f"<span class='meta'>{e(loc_str(f.get('location')))}</span></div>")
        if t != "suggestion":
            h.append(f"<p class='meta'>{e(badge_line(f, L))}</p>")
        if f.get("quote"):
            h.append(f"<blockquote>{fmt(f['quote'])}</blockquote>")
        h.append(f"<div class='field'><b>{e(L['problem'])}</b>: {fmt(f.get('explanation', ''))}</div>")
        for k, lab in (("evidence", "evidence"), ("impact", "impact"), ("suggestion", "fix")):
            if f.get(k):
                h.append(f"<div class='field'><b>{e(L[lab])}</b>: {fmt(f[k])}</div>")
        h.append("</article>")
    h.append("</div></section>")

    prof = {}
    for f in F.get("findings", []):
        asp = ASPECT.get(f.get("category"), "other")
        prof[asp] = prof.get(asp, 0) + 1
    h.append(f"<section><h2>{e(L['appendix'])}</h2><h3>{e(L['method'])}</h3><ul>"
             f"<li>{e(L['m_segments'])}: {stats['segments']} ／ {e(L['m_tasks'])}: {stats['tasks']} ／ {e(L['m_lenses'])}: {stats['lenses']}</li>"
             f"<li>{e(L['m_cands'])}: {stats['candidates']} → {e(L['m_clusters'])}: {stats['clusters']} → "
             f"{e(L['m_verified'])}: {stats['verified']} ／ {e(L['m_dropped'])}: {stats['dropped']}</li></ul>")
    if F.get("method_notes"):
        h.append(f"<p>{fmt(F['method_notes'])}</p>")
    prof_txt = " ／ ".join(f"{e(L['aspect'][k])}: {v}" for k, v in sorted(prof.items())) or "-"
    h.append(f"<h3>{e(L['profile'])}</h3><p>{prof_txt}</p>")
    if F.get("limitations"):
        h.append(f"<h3>{e(L['limitations'])}</h3><ul>{''.join(f'<li>{fmt(x)}</li>' for x in F['limitations'])}</ul>")
    h.append(f"</section></main><script>{JS}</script></body></html>")
    return "".join(h)


def cmd_render(a):
    ws = Path(a.ws)
    cfg = load_json(ws / "config.json")
    F = load_json(ws / "findings.json")
    errors, warns = validate_findings(F, Grounder(read_pages(ws)), cfg["n_pages"])
    for w in warns:
        print("WARN:", w)
    if errors:
        print("findings.json has errors:")
        for x in errors:
            print("  -", x)
        sys.exit(1)
    if a.check:
        print(f"findings.json OK ({len(F.get('findings', []))} findings)")
        return
    L = LABELS[lang_of(ws)]
    stats = method_stats(ws, F)
    (ws / "report.md").write_text(render_md(F, cfg, stats, L), encoding="utf-8")
    (ws / "report.html").write_text(render_html(F, cfg, stats, L), encoding="utf-8")
    fin = stats["final"]
    print(f"wrote {ws / 'report.md'}\nwrote {ws / 'report.html'}")
    print(f"major {fin['major']} / minor {fin['minor']} / suggestion {fin['suggestion']}")


# ---------------------------------------------------------------- main

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init")
    s.add_argument("input")
    s.add_argument("--ws")
    s.add_argument("--depth", choices=DEPTHS, default="standard")
    s.add_argument("--focus", default="")
    s.add_argument("--venue", default="")
    s.add_argument("--lang", choices=sorted(LABELS), default="ja")
    s.add_argument("--dpi", type=int, default=150)
    s.add_argument("--no-render", action="store_true")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_init)
    for name, fn in (("plan", cmd_plan), ("merge", cmd_merge), ("collate", cmd_collate)):
        s = sub.add_parser(name)
        s.add_argument("ws")
        s.set_defaults(fn=fn)
    s = sub.add_parser("render")
    s.add_argument("ws")
    s.add_argument("--check", action="store_true", help="only validate findings.json")
    s.set_defaults(fn=cmd_render)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
