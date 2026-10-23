#!/usr/bin/env python3
"""Helpers for the academic-writing-loop skill (English proofreading of paper PDFs).

  awl.py init     WS --pdf PDF --mode once|loop [--max-rounds 5] [--journal TEXT] [--force]
  awl.py extract  PDF -o OUT.txt            page/line-numbered text (+ OUT.lines.json with positions)
  awl.py scan     TXT -o OUT.md             mechanical candidates for the proofreader (+ OUT.json)
  awl.py validate CORR.json [--text TXT]    schema check; every `original` must occur in the text
  awl.py merge    OUT.json PART.json ...    combine split proofreading parts and renumber IDs
  awl.py report   CORR.json [-o OUT.md]     readable report in Japanese (validates first)
  awl.py annotate PDF CORR.json -o OUT.pdf  highlight + comment for every item (the marked-up PDF)
  awl.py verify   WS --round N              did round N's applied corrections reach r(N+1)'s PDF?
  awl.py compare  A.txt B.txt               word-level diff of two extracted texts (reconstruction fidelity)
  awl.py status   WS                        progress table and NEXT: ... (the loop's stop rule)
  awl.py finalize WS                        changelog.md, progress.md and deliverable copies

Text positions and annotation use PyMuPDF (pip install pymupdf). Without it, `extract`
falls back to pypdf / pdftotext (no positions) and `annotate` is unavailable.
"""
import argparse
import bisect
import datetime as dt
import json
import re
import shutil
import statistics
import sys
import unicodedata
from collections import Counter, OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

SKILL_DIR = Path(__file__).resolve().parent.parent
SEVERITIES = ("error", "clarity", "style", "query")
SEV_JA = {"error": "誤り", "clarity": "明確さ", "style": "文体", "query": "著者確認"}
COUNTED = ("error", "clarity")  # what the loop's stop rule counts
COLORS = {"error": (1.0, 0.45, 0.45), "clarity": (1.0, 0.8, 0.2),
          "style": (0.55, 0.85, 0.55), "query": (0.45, 0.7, 1.0)}
PREV_STATUS = ("resolved", "remaining", "changed", "not_applicable")
ACTIONS = ("applied", "skipped", "query")

CATEGORY = {
    "G1": "投稿規定", "G2": "表記の一貫性", "G3": "自動書式・参照",
    "S1": "見出しの階層", "S2": "節番号・相互参照", "S3": "見出しの略語", "S4": "段落の構成",
    "S5": "段落のつなぎ", "S6": "リスト",
    "V1": "US/UK綴り", "V2": "綴りの揺れ",
    "A1": "単位の略号", "A2": "ラテン語略語", "A3": "et al. 等", "A4": "略語の定義",
    "A5": "略語の運用", "A6": "タイトル・要旨・見出しの略語",
    "P1": "連続コンマ", "P2": "導入句のコンマ", "P3": "コロン・セミコロン", "P4": "ハイフン",
    "P5": "アポストロフィ・所有格", "P6": "引用・注と句読点", "P7": "ダッシュ・範囲", "P8": "空白・記号",
    "W1": "形式性", "W2": "正確さ・比較", "W3": "用語の一貫性", "W4": "専門用語・名詞の連続",
    "W5": "語の変化・反復", "W6": "数の書き方", "W7": "人の呼び方",
    "T1": "先行研究の時制", "T2": "本研究の時制", "T3": "受動態", "T4": "分割不定詞",
    "R1": "代名詞の先行詞", "R2": "数の一致", "R3": "I / we", "R4": "包括的な we・you",
    "R5": "性別に中立な表現",
    "F1": "図表の独立性", "F2": "図表と本文の一致", "F3": "図表の番号・言及", "F4": "図表ラベルの書式",
    "F5": "図表内の語",
    "C1": "引用の位置", "C2": "引用の書式（著者年）", "C3": "引用の書式（番号）",
    "C4": "引用と文献リストの一致", "C5": "文献リストの書式", "C6": "直接引用", "C7": "脚注",
    "K1": "タイトル", "K2": "要旨", "K3": "キーワード",
    "L1": "主張の強さ", "L2": "結果の文", "L3": "方法の説明",
    "E1": "冠詞", "E2": "主語と動詞の一致", "E3": "可算・不可算", "E4": "前置詞", "E5": "品詞・語形",
    "E6": "文の構造", "E7": "語順", "E8": "誤字・脱字", "E9": "直訳調",
}


def out_utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass


def read_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def write_json(p, obj):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def now():
    return dt.datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------- normalisation

TRANS = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'", "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-",
    "\u00a0": " ", "\u2009": " ", "\u202f": " ", "\u2002": " ", "\u2003": " ", "\u200b": "", "\u00ad": "",
})


def norm(s):
    """Compare-friendly text: ligatures expanded, quotes/dashes/spaces unified."""
    s = unicodedata.normalize("NFKC", s or "").translate(TRANS)
    return re.sub(r"\s+", " ", s).strip()


def nospace(s):
    return re.sub(r"\s+", "", norm(s))


# ---------------------------------------------------------------- extract

def _line_dir_ok(ln):
    d = ln.get("dir", (1, 0))
    return abs(d[0]) > 0.9  # skip rotated text such as the arXiv stamp


def _visual_lines(block):
    """Merge PyMuPDF dict lines that share a baseline (superscripts, split spans)."""
    vis = []
    for ln in block["lines"]:
        if not _line_dir_ok(ln):
            continue
        spans = [s for s in ln["spans"] if s["text"].strip()]
        if not spans:
            continue
        x0, y0, x1, y1 = ln["bbox"]
        piece = {"x0": x0, "x1": x1, "text": "".join(s["text"] for s in ln["spans"]).strip(),
                 "size": max(s["size"] for s in spans),
                 "bold": any((s["flags"] & 16) or "bold" in s["font"].lower() for s in spans)}
        h = max(y1 - y0, 1)
        target = None
        for v in vis:
            ov = min(v["y1"], y1) - max(v["y0"], y0)
            if ov > 0.5 * min(h, v["y1"] - v["y0"]):
                target = v
                break
        if target is None:
            vis.append({"y0": y0, "y1": y1, "pieces": [piece]})
        else:
            target["y0"], target["y1"] = min(target["y0"], y0), max(target["y1"], y1)
            target["pieces"].append(piece)
    out = []
    for v in sorted(vis, key=lambda v: v["y0"]):
        ps = sorted(v["pieces"], key=lambda p: p["x0"])
        text = ps[0]["text"]
        for a, b in zip(ps, ps[1:]):
            text += ("" if b["x0"] - a["x1"] < 0.15 * b["size"] else " ") + b["text"]
        main = max(ps, key=lambda p: len(p["text"]))
        out.append({"bbox": [min(p["x0"] for p in ps), v["y0"], max(p["x1"] for p in ps), v["y1"]],
                    "text": text, "size": round(main["size"], 1), "bold": main["bold"]})
    return out


def _order_blocks(blocks, width):
    """Reading order: two-column pages read left column then right, between full-width blocks."""
    mid, tol = width / 2, width * 0.03
    left, right, full = [], [], []
    for b in blocks:
        x0, _, x1, _ = b["bbox"]
        (left if x1 <= mid + tol else right if x0 >= mid - tol else full).append(b)
    words = lambda bs: sum(len(l["text"].split()) for b in bs for l in b["lines"])
    if len(left) < 2 or len(right) < 2 or words(left) < 40 or words(right) < 40:
        return sorted(blocks, key=lambda b: (round(b["bbox"][1]), b["bbox"][0]))
    out, prev = [], float("-inf")
    for f in sorted(full, key=lambda b: b["bbox"][1]) + [None]:
        y = f["bbox"][1] if f else float("inf")
        band = lambda col: sorted((b for b in col if prev <= b["bbox"][1] < y), key=lambda b: b["bbox"][1])
        out += band(left) + band(right)
        if f:
            out.append(f)
            prev = y
    return out


def _paragraphs(lines):
    """Split a block into paragraphs at first-line indents."""
    if len(lines) < 2:
        return [lines]
    left = min(l["bbox"][0] for l in lines)
    right = max(l["bbox"][2] for l in lines)
    paras, cur = [], [lines[0]]
    for prev, ln in zip(lines, lines[1:]):
        indent = ln["bbox"][0] - left
        ends = prev["text"].rstrip().endswith((".", "!", "?", ":", ".”", ".\"", ".)"))
        if 6 < indent < 40 and (ends or prev["bbox"][2] < right - 8):
            paras.append(cur)
            cur = []
        cur.append(ln)
    paras.append(cur)
    return paras


def extract_pages(pdf):
    """[(page_no, width, height, [paragraph -> [line dict]])]"""
    if fitz is None:
        from pdf_tools import page_texts
        pages = []
        for i, t in enumerate(page_texts(pdf)):
            paras, cur = [], []
            for raw in t.splitlines():
                if raw.strip():
                    cur.append({"bbox": None, "text": raw.strip(), "size": None, "bold": False})
                elif cur:
                    paras.append(cur)
                    cur = []
            if cur:
                paras.append(cur)
            pages.append((i + 1, None, None, paras))
        return pages
    pages = []
    with fitz.open(pdf) as doc:
        for pno, page in enumerate(doc):
            d = page.get_text("dict", flags=fitz.TEXT_MEDIABOX_CLIP)
            blocks = []
            for b in d["blocks"]:
                if b.get("type", 0) != 0:
                    continue
                lines = _visual_lines(b)
                if lines:
                    blocks.append({"bbox": b["bbox"], "lines": lines})
            paras = [p for b in _order_blocks(blocks, page.rect.width) for p in _paragraphs(b["lines"])]
            pages.append((pno + 1, page.rect.width, page.rect.height, paras))
    return pages


def cmd_extract(a):
    pages = extract_pages(a.pdf)
    txt, mp, nwords = [], {"pdf": str(Path(a.pdf).resolve()), "positions": fitz is not None, "pages": []}, 0
    for pno, w, h, paras in pages:
        txt.append(f"=== Page {pno} ===")
        entry = {"page": pno, "width": w, "height": h, "lines": []}
        n = 0
        for bi, para in enumerate(paras):
            if bi:
                txt.append("")
            for ln in para:
                n += 1
                txt.append(f"{n:4d}| {ln['text']}")
                nwords += len(ln["text"].split())
                entry["lines"].append({"n": n, "block": bi, "bbox": [round(v, 1) for v in ln["bbox"]] if ln["bbox"] else None,
                                       "size": ln["size"], "bold": ln["bold"], "text": ln["text"]})
        txt.append("")
        mp["pages"].append(entry)
    out = Path(a.o)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(txt) + "\n", encoding="utf-8")
    write_json(out.with_suffix(".lines.json"), mp)
    per_page = nwords / max(len(pages), 1)
    print(f"wrote {out} ({len(pages)} pages, {nwords} words)" + ("" if fitz else "  [no PyMuPDF: no positions]"))
    if per_page < 60:
        print("WARNING: very little text per page. Scanned PDF? OCR is needed before proofreading.")


# ---------------------------------------------------------------- text model

PAGE_RE = re.compile(r"^=== Page (\d+) ===\s*$")
LINE_RE = re.compile(r"^\s*(\d+)\| ?(.*)$")


def parse_txt(path):
    """[(page, [(line_no, text, block_id)])] from extract's output."""
    pages, cur, block, gap = [], None, 0, False
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        m = PAGE_RE.match(raw)
        if m:
            cur = (int(m.group(1)), [])
            pages.append(cur)
            block += 1
            gap = False
            continue
        if cur is None:
            continue
        m = LINE_RE.match(raw)
        if m:
            if gap:
                block += 1
                gap = False
            cur[1].append((int(m.group(1)), m.group(2), block))
        elif not raw.strip():
            gap = True
    return pages


class Doc:
    """Paragraph blocks of the extracted text, with offsets mapped back to page/line."""

    def __init__(self, txt_path):
        self.path = Path(txt_path)
        self.pages = parse_txt(txt_path)
        vocab, hyph, lower = Counter(), set(), set()
        for _, lines in self.pages:
            for _, t, _ in lines:
                for w in re.findall(r"[A-Za-z]+(?:-[A-Za-z]+)*", t):
                    vocab[w.lower()] += 1
                    if "-" in w:
                        hyph.add(w.lower())
                    if w.islower():
                        lower.add(w)
        self.vocab, self.hyph, self.lower_vocab = vocab, hyph, lower
        self.blocks = []
        for pno, lines in self.pages:
            groups = OrderedDict()
            for ln, t, b in lines:
                groups.setdefault(b, []).append((ln, t))
            for ls in groups.values():
                text, starts = "", []
                for ln, t in ls:
                    t = t.strip()
                    if text:
                        m_head, m_tail = re.search(r"([A-Za-z]{2,})-$", text), re.match(r"[a-z]+", t)
                        if m_head and m_tail:
                            joined = (m_head.group(1) + m_tail.group(0)).lower()
                            if joined in vocab and f"{m_head.group(1)}-{m_tail.group(0)}".lower() not in hyph:
                                text = text[:-1]  # typesetting hyphen
                        elif not text.endswith("-"):
                            text += " "
                    starts.append((len(text), pno, ln))
                    text += t
                self.blocks.append({"page": pno, "line": ls[0][0], "text": text, "starts": starts,
                                    "nlines": len(ls), "lines": [ln for ln, _ in ls]})
        self.meta = {}
        mp = self.path.with_suffix(".lines.json")
        if mp.exists():
            for pg in read_json(mp).get("pages", []):
                for ln in pg["lines"]:
                    self.meta[(pg["page"], ln["n"])] = ln

    def loc(self, bi, off=0):
        st = self.blocks[bi]["starts"]
        i = max(bisect.bisect_right([s[0] for s in st], off) - 1, 0)
        return st[i][1], st[i][2]

    def variants(self):
        """Whole text joined three ways (heuristic / drop all line-end hyphens / keep them)."""
        heur = "\n".join(b["text"] for b in self.blocks)
        drop, keep = [], []
        for _, lines in self.pages:
            for _, t, _ in lines:
                drop.append(t.strip())
                keep.append(t.strip())
        d = re.sub(r"(?<=[A-Za-z])-\n(?=[a-z])", "", "\n".join(drop))
        k = re.sub(r"(?<=[A-Za-z]-)\n(?=[a-z])", "", "\n".join(keep))
        return [heur, d, k]


def light(s):
    """Ligatures and spaces normalised, but case, dashes and quotes kept."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", s or "").replace("­", "")).strip()


def fine_only(a, b):
    """True if a and b differ only in case, spacing, dashes or quotes (fixes `find` cannot see)."""
    return a != b and nospace(a).lower() == nospace(b).lower()


class TextIndex:
    def __init__(self, doc):
        vs = doc.variants()
        self.n = [norm(v) for v in vs]
        self.ns = [nospace(v) for v in vs]
        self.nl = [v.lower() for v in self.n]
        self.strict = [light(v) for v in vs]

    def has_exact(self, s):
        """Case-, dash- and quote-sensitive search (for case/spacing/punctuation-only fixes)."""
        return bool(s) and any(light(s) in v for v in self.strict)

    def find(self, s):
        """'exact' | 'nospace' | 'case' | None"""
        if not s:
            return None
        t = norm(s)
        if any(t in v for v in self.n):
            return "exact"
        if any(nospace(s) in v for v in self.ns):
            return "nospace"
        if any(t.lower() in v for v in self.nl):
            return "case"
        return None

    def count(self, s):
        t = norm(s)
        return self.n[0].count(t) if t else 0


def page_line_texts(doc):
    return {(p, ln): t for p, lines in doc.pages for ln, t, _ in lines}


# ---------------------------------------------------------------- scan (mechanical candidates)

UK_US = [
    # (family, UK form, US form) -- matched as whole words with common suffixes
    ("-our/-or", "colour", "color"), ("-our/-or", "behaviour", "behavior"), ("-our/-or", "favour", "favor"),
    ("-our/-or", "labour", "labor"), ("-our/-or", "neighbour", "neighbor"), ("-our/-or", "honour", "honor"),
    ("-our/-or", "humour", "humor"), ("-our/-or", "vapour", "vapor"), ("-our/-or", "flavour", "flavor"),
    ("-our/-or", "rumour", "rumor"), ("-our/-or", "tumour", "tumor"), ("-our/-or", "odour", "odor"),
    ("-our/-or", "endeavour", "endeavor"), ("-our/-or", "vigour", "vigor"), ("-our/-or", "harbour", "harbor"),
    ("-re/-er", "centre", "center"), ("-re/-er", "fibre", "fiber"), ("-re/-er", "litre", "liter"),
    ("-re/-er", "theatre", "theater"), ("-re/-er", "calibre", "caliber"), ("-re/-er", "centimetre", "centimeter"),
    ("-re/-er", "millimetre", "millimeter"), ("-re/-er", "kilometre", "kilometer"), ("-re/-er", "micrometre", "micrometer"),
    ("-re/-er", "nanometre", "nanometer"), ("-re/-er", "lustre", "luster"), ("-re/-er", "sombre", "somber"),
    ("-ll-/-l-", "modelling", "modeling"), ("-ll-/-l-", "modelled", "modeled"), ("-ll-/-l-", "modeller", "modeler"),
    ("-ll-/-l-", "labelling", "labeling"), ("-ll-/-l-", "labelled", "labeled"), ("-ll-/-l-", "travelling", "traveling"),
    ("-ll-/-l-", "travelled", "traveled"), ("-ll-/-l-", "cancelled", "canceled"), ("-ll-/-l-", "cancelling", "canceling"),
    ("-ll-/-l-", "signalling", "signaling"), ("-ll-/-l-", "signalled", "signaled"), ("-ll-/-l-", "fuelled", "fueled"),
    ("-ll-/-l-", "levelled", "leveled"), ("-ll-/-l-", "channelling", "channeling"), ("-ll-/-l-", "channelled", "channeled"),
    ("-ll-/-l-", "tunnelling", "tunneling"), ("-ll-/-l-", "counselling", "counseling"), ("-ll-/-l-", "totalling", "totaling"),
    ("-ll-/-l-", "totalled", "totaled"), ("-ll-/-l-", "fulfil", "fulfill"), ("-ll-/-l-", "enrolment", "enrollment"),
    ("-ll-/-l-", "skilful", "skillful"),
    ("-ss-/-s-", "focussed", None), ("-ss-/-s-", "focussing", None), ("-ss-/-s-", "focusses", None),  # "focused" is also British
    ("-ogue/-og", "catalogue", "catalog"), ("-ogue/-og", "analogue", "analog"), ("-ogue/-og", "dialogue", "dialog"),
    ("-ence/-ense", "defence", "defense"), ("-ence/-ense", "offence", "offense"), ("-ence/-ense", "pretence", "pretense"),
    ("ae・oe/e", "oestrogen", "estrogen"), ("ae・oe/e", "haemoglobin", "hemoglobin"), ("ae・oe/e", "anaemia", "anemia"),
    ("ae・oe/e", "paediatric", "pediatric"), ("ae・oe/e", "orthopaedic", "orthopedic"), ("ae・oe/e", "foetus", "fetus"),
    ("ae・oe/e", "foetal", "fetal"), ("ae・oe/e", "oesophagus", "esophagus"), ("ae・oe/e", "aetiology", "etiology"),
    ("ae・oe/e", "haematology", "hematology"), ("ae・oe/e", "leukaemia", "leukemia"), ("ae・oe/e", "anaesthesia", "anesthesia"),
    ("ae・oe/e", "manoeuvre", "maneuver"), ("ae・oe/e", "encyclopaedia", "encyclopedia"), ("ae・oe/e", "haemorrhage", "hemorrhage"),
    ("その他", "grey", "gray"), ("その他", "aluminium", "aluminum"), ("その他", "sulphur", "sulfur"),
    ("その他", "judgement", "judgment"), ("その他", "ageing", "aging"), ("その他", "artefact", "artifact"),
    ("その他", "sceptical", "skeptical"), ("その他", "mould", "mold"), ("その他", "plough", "plow"),
    ("その他", "whilst", None), ("その他", "amongst", None), ("その他", "learnt", None), ("その他", "programme", None),
]
SUFFIX = r"(?:s|es|ed|ing|al|ally|ly|ful|less|ist|ists|er|ers)?"
IZE_STEMS = ("organi", "recogni", "reali", "characteri", "minimi", "maximi", "normali", "optimi", "generali", "utili",
             "summari", "emphasi", "categori", "visuali", "standardi", "initiali", "randomi", "parameteri", "regulari",
             "speciali", "stabili", "prioriti", "customi", "finali", "locali", "quanti", "tokeni", "vectori", "discreti",
             "synchroni", "hypothesi", "synthesi", "critici", "authori", "capitali", "centrali", "civili", "digiti",
             "familiari", "globali", "memori", "moderni", "neutrali", "personali", "polari", "symboli", "theori",
             "industriali", "lineari", "marginali", "mobili", "operationali", "conceptuali", "contextuali", "formali",
             "harmoni", "ideali", "itemi", "legitimi", "monetari", "naturali", "penali", "rationali", "sanitize")
IZE_RE = re.compile(r"\b(" + "|".join(s for s in IZE_STEMS if s.endswith("i")) + r")([sz])(e|es|ed|ing|ation|ations|er|ers)\b", re.I)
YSE_RE = re.compile(r"\b(analy|paraly|cataly|dialy|electroly|hydroly)([sz])(e|es|ed|ing|er|ers)\b", re.I)

COMMON_ACRONYMS = set("""US USA UK EU UN DNA RNA mRNA AIDS HIV IQ PDF URL URLs HTTP HTTPS HTML XML JSON ID IDs CPU CPUs GPU GPUs
TPU RAM ROM USB TV PC PCs OK AM PM BC AD CEO NASA UNESCO ISBN DOI ISSN IEEE ACM ISO ANSI ASCII UTF API APIs SQL CSV
GB MB KB TB GHz MHz kHz CD DVD LED LCD NA OR II III IV VI VII VIII IX XI XII XIII XIV XV LaTeX UTC GPS SI MRI CT
PhD MSc BSc MD MA BA COVID COVID-19 SARS SARS-CoV-2 WHO OECD GDP NGO NGOs""".split())
LATIN_ABBR = r"(?:e\.g|i\.e|et al|Fig|Figs|Eq|Eqs|Sec|Secs|Ref|Refs|cf|vs|etc|approx|resp|No|Nos|Dr|Mr|Mrs|Ms|Prof|Inc|Ltd|Co|Jr|Sr|St|pp|p|vol|Vol|ed|eds|Ch|Tab|al|viz|ca|Corp|Univ|Dept|Eqn|Thm|Lem|Def|Prop|Alg|Appx)"
NON_ADVERB_LY = set("""family apply supply reply rely fly july italy assembly anomaly monopoly poly holy jelly belly ally
rally comply multiply imply emily kelly daily weekly monthly yearly early likely friendly lonely costly lovely ugly silly
butterfly bully curly elderly orderly scholarly timely deadly lively hourly quarterly underlie""".split())
INFORMAL = r"\b(a lot of|lots of|kind of|sort of|pretty much|okay|stuff|really|huge|basically|totally|anyway|nowadays|and so on|gotten|got)\b"
SENT_START_INFORMAL = r"(?:^|[.!?]\s+)(And|But|So|Also|Plus),?\s"
JE_UNCOUNTABLE = r"\b(informations|researches|evidences|softwares|equipments|feedbacks|knowledges|advices|datas|hardwares|staffs|furnitures|machineries)\b"
JE_ABOUT = r"\b(discuss|discussed|discusses|discussing|consider|considered|considers|considering|mention|mentioned|mentions|explain|explained|explains|describe|described|describes)\s+about\b"
CONNECTIVES = ("However", "Moreover", "Furthermore", "In addition", "Therefore", "Thus", "Additionally", "In this paper",
               "In recent years", "On the other hand", "Consequently", "Hence")
UNITS_ATTACHED = r"\b\d+(?:\.\d+)?(ms|ns|μs|µs|min|Hz|kHz|MHz|GHz|kg|mg|mm|cm|km|nm|μm|µm|mL|mol|mM|mV|kV|mA|kW|MW|kJ|kPa|MPa|dB|GB|MB|KB|TB|px)\b"
PRONOUN_START = re.compile(r"^(It|They|Its|Their|Them)\b|^(This|These|That|Those)\s+(is|was|are|were|has|have|had|can|could|may|might|will|would|should|shows?|suggests?|means?|indicates?|implies|allows?|leads?|makes?|demonstrates?|results?|provides?|enables?|gives?|reveals?|confirms?)\b")
CAPTION_RE = re.compile(r"^\s*(Figure|Fig\.|FIGURE|FIG\.|Table|TABLE|Tab\.)\s*([IVXLC]+|\d+)\s*(?:[.:|—–]|$|(?=[A-Z(]))")
MENTION_RE = re.compile(r"\b(Figures?|Figs?\.|FIGURES?|FIGS?\.|Tables?|TABLES?|Tab\.)\s*~?\s*((?:\d+|[IVX]+)(?:\s*\(?[a-z]\)?)?(?:\s*(?:,|and|&|–|-|to)\s*(?:\d+|[IVX]+)(?:\s*\(?[a-z]\)?)?)*)")
HEADING_NUM_RE = re.compile(r"^\s*((?:\d+\.)*\d+\.?|[IVX]+\.|[A-Z]\.)\s+(\S.*)$")
MINOR_WORDS = set("a an the and or but nor for of in on at to by with from as via vs into onto upon per than over under".split())


def roman_to_int(s):
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    total, prev = 0, 0
    for ch in reversed(s.upper()):
        v = vals.get(ch, 0)
        total += -v if v < prev else v
        prev = max(prev, v)
    return total


def num_of(s):
    s = s.strip()
    return int(s) if s.isdigit() else roman_to_int(s)


def split_sentences(text):
    protected = re.sub(r"\b" + LATIN_ABBR + r"\.", lambda m: m.group(0).replace(".", "\u2024"), text)
    protected = re.sub(r"\b([A-Z])\.(?=\s+[A-Z])", "\\1\u2024", protected)  # initials
    out, pos = [], 0
    # Abbreviations were protected above, so a remaining period after an ordinary word ends a
    # sentence even when the next one starts with a digit or (wrongly) a lowercase letter.
    for m in re.finditer(r"(?<=[.!?])[\"”’)]*\s+(?=[A-Z0-9(\[“\"‘])|(?<=[a-z]{3}[.!?])\s+(?=[a-z])", protected):
        out.append((pos, protected[pos:m.start()].replace("\u2024", ".")))
        pos = m.end()
    out.append((pos, protected[pos:].replace("\u2024", ".")))
    return [(o, s) for o, s in out if s.strip()]


def inside_parens(text, off):
    depth = 0
    for ch in text[:off]:
        if ch == "(":
            depth += 1
        elif ch == ")" and depth:
            depth -= 1
    return depth > 0


def case_style(text):
    words = re.findall(r"[A-Za-z][A-Za-z'’\-]*", text)
    if not words:
        return "-"
    letters = "".join(words)
    if letters.isupper() and len(letters) > 3:
        return "ALL CAPS"
    content = [w for w in words[1:] if w.lower() not in MINOR_WORDS and not w.isupper()]
    if not content:
        return "Title/Sentence"
    caps = sum(w[0].isupper() for w in content) / len(content)
    if caps >= 0.8:
        return "Title Case"
    if caps <= 0.2:
        return "Sentence case"
    return "混在"


class Scanner:
    def __init__(self, doc):
        self.doc = doc
        self.cands = []
        self.stats = OrderedDict()
        self.extra_md = []
        self._zones()

    # -- zones -------------------------------------------------------
    def _zones(self):
        B = self.doc.blocks
        self.abs_i = self.kw_i = self.intro_i = None
        self.ref_i = len(B)
        heading = r"^\s*(?:(?:\d+|[IVX]+)\.?\s+)?(References|REFERENCES|Bibliography|BIBLIOGRAPHY|Works Cited|WORKS CITED|Literature Cited|Reference List)\b"
        for i, b in enumerate(B):
            t = b["text"]
            if self.abs_i is None and re.match(r"^\s*(Abstract|ABSTRACT|Summary|SUMMARY)\b", t):
                self.abs_i = i
            if self.kw_i is None and re.match(r"^\s*(Key ?words|KEY ?WORDS|Index Terms|INDEX TERMS)\b", t, re.I):
                self.kw_i = i
            if self.intro_i is None and re.match(r"^\s*(?:(?:\d+|[IVX]+)\.?\s+)?(Introduction|INTRODUCTION)\b", t):
                self.intro_i = i
            m = re.match(heading, t)
            if m and (len(t.split()) <= 3 or re.match(heading + r"\s*(\[\d+\]|\d+\.|[A-Z])", t)) and i > (self.intro_i or 0):
                self.ref_i = i
        self.captions = {i for i, b in enumerate(B) if CAPTION_RE.match(b["text"])}
        self.headings = self._find_headings()
        start = self.intro_i if self.intro_i is not None else ((self.kw_i or self.abs_i or -1) + 1)
        self.body = [i for i in range(start, self.ref_i) if i not in self.captions and i not in self.headings]
        self.refs = list(range(self.ref_i, len(B)))
        if self.abs_i is not None:
            end = self.kw_i if self.kw_i is not None and self.kw_i > self.abs_i else (self.intro_i or self.abs_i + 1)
            self.abstract = list(range(self.abs_i, max(end, self.abs_i + 1)))
        else:
            self.abstract = []
        self.prose = [i for i in range(0, self.ref_i) if i not in self.captions and i not in self.headings]

    def _find_headings(self):
        B, meta = self.doc.blocks, self.doc.meta
        sizes = Counter()
        for (p, n), m in meta.items():
            if m.get("size"):
                sizes[m["size"]] += len(m.get("text", ""))
        body = sizes.most_common(1)[0][0] if sizes else None
        out = {}
        for i, b in enumerate(B):
            t = b["text"].strip()
            words = t.split()
            if b["nlines"] > 2 or not words or len(words) > 14 or i in self.captions or t.count(",") >= 2 \
                    or re.match(r"^\s*(Key ?words|Index Terms)\b", t, re.I):
                continue
            m0 = meta.get((b["page"], b["line"]), {})
            numbered = HEADING_NUM_RE.match(t)
            big = body and m0.get("size") and m0["size"] >= body + 0.8
            bold = m0.get("bold")
            caps = t.isupper() and len(t) > 4
            ends_period = t.endswith(".") and not re.fullmatch(r"(?:\d+\.)+", t)
            if ends_period or re.search(r"[,;]$", t) or t[0].islower():
                continue
            if re.match(r"^\[?\d+\]?\s*$", t) or re.match(r"^\s*(\d+|[ivx]+)\s*$", t):
                continue  # page numbers
            if numbered and (bold or big or caps or len(words) <= 8):
                out[i] = {"num": numbered.group(1).rstrip("."), "title": numbered.group(2), "size": m0.get("size"), "bold": bold}
            elif (bold or big or caps) and len(words) <= 10 and not re.search(r"\d{4}", t):
                out[i] = {"num": "", "title": t, "size": m0.get("size"), "bold": bold}
        return out

    # -- helpers -------------------------------------------------------
    def add(self, cat, bi, off, note, snippet=None, span=60):
        b = self.doc.blocks[bi]
        p, ln = self.doc.loc(bi, off)
        if snippet is None:
            s = max(0, off - span // 2)
            snippet = ("…" if s else "") + b["text"][s:off + span].strip() + ("…" if off + span < len(b["text"]) else "")
        self.cands.append({"category": cat, "page": p, "line": ln, "snippet": snippet, "note": note})

    def regex(self, cat, pattern, note, blocks=None, flags=0, limit=40, group=0):
        hits = 0
        for bi in (self.prose if blocks is None else blocks):
            for m in re.finditer(pattern, self.doc.blocks[bi]["text"], flags):
                hits += 1
                if hits <= limit:
                    self.add(cat, bi, m.start(group), note.format(m=m.group(group)))
        if hits > limit:
            self.cands.append({"category": cat, "page": None, "line": None, "snippet": "", "note": f"（ほか {hits - limit} 件。同種の箇所を全文検索すること）"})
        return hits

    def text_of(self, blocks):
        return "\n".join(self.doc.blocks[i]["text"] for i in blocks)

    # -- checks -------------------------------------------------------
    def overview(self):
        d = self.doc
        words = sum(len(b["text"].split()) for b in d.blocks)
        self.stats["pages"] = len(d.pages)
        self.stats["words"] = words
        zone = lambda i: f"p{d.blocks[i]['page']} L{d.blocks[i]['line']}" if i is not None and i < len(d.blocks) else "未検出"
        self.stats["zones"] = {"abstract": zone(self.abs_i), "keywords": zone(self.kw_i),
                               "introduction": zone(self.intro_i), "references": zone(self.ref_i if self.ref_i < len(d.blocks) else None)}

    def variety(self):
        text_blocks = self.prose
        fam = OrderedDict()
        occ = {"UK": [], "US": []}
        for family, uk, us in UK_US:
            for var, word in (("UK", uk), ("US", us)):
                if not word:
                    continue
                pat = re.compile(r"\b" + word + SUFFIX + r"\b", re.I)
                for bi in text_blocks:
                    for m in pat.finditer(self.doc.blocks[bi]["text"]):
                        fam.setdefault(family, Counter())[var] += 1
                        occ[var].append((bi, m.start(), m.group(0), family))
        for regex, family in ((IZE_RE, "-ise/-ize"), (YSE_RE, "-yse/-yze")):
            for bi in text_blocks:
                for m in regex.finditer(self.doc.blocks[bi]["text"]):
                    var = "UK" if m.group(2).lower() == "s" else "US"
                    fam.setdefault(family, Counter())[var] += 1
                    occ[var].append((bi, m.start(), m.group(0), family))
        uk = sum(c["UK"] for f, c in fam.items() if f != "-ise/-ize")
        us = sum(c["US"] for f, c in fam.items() if f != "-ise/-ize")
        guess = "US" if us > uk else "UK" if uk > us else "判定不能"
        self.stats["variety"] = {"guess": guess, "UK": uk, "US": us,
                                 "families": {f: dict(c) for f, c in fam.items()}}
        rows = ["| 系統 | UK | US |", "|---|---|---|"]
        rows += [f"| {f} | {c['UK']} | {c['US']} |" for f, c in fam.items()]
        ise = fam.get("-ise/-ize", Counter())
        note = ""
        if guess == "UK" and ise["US"] and not ise["UK"]:
            note = "UK綴りで -ize のみ → Oxford spelling の可能性（混在でなければ誤りではない）。"
        self.extra_md.append("## V1 US/UK 綴りの集計（参考文献リストを除く）\n\n" + "\n".join(rows) +
                             f"\n\n推定: **{guess}**（-ise/-ize を除く UK {uk} / US {us}）。{note}\n")
        minority = []
        if guess in ("US", "UK"):
            other = "UK" if guess == "US" else "US"
            minority = [o for o in occ[other] if not (guess == "UK" and o[3] == "-ise/-ize" and not ise["UK"])]
        if ise["UK"] and ise["US"]:
            minor = "UK" if ise["UK"] < ise["US"] else "US"
            minority += [o for o in occ[minor] if o[3] == "-ise/-ize" and o not in minority]
        for bi, off, word, family in minority[:60]:
            self.add("V1", bi, off, f"少数派の綴り '{word}'（{family}）")

    def contractions(self):
        self.regex("W1", r"\b(?:[A-Za-z]+n['’]t|[A-Za-z]+['’](?:re|ve|ll|d|m)|(?:it|that|there|here|what|who|let|he|she|where)['’]s)\b",
                   "短縮形 '{m}' → 書き下す", flags=re.I)

    def repeated(self):
        self.regex("E8", r"\b([A-Za-z]+)\s+\1\b", "語の重複 '{m}'", flags=re.I)

    def spacing(self):
        self.regex("P8", r"[A-Za-z][ ]+[,;](?!\d)", "句読点の前の空白", limit=25)
        self.regex("P8", r"[a-z][,;][A-Za-z]", "コンマ/セミコロンの後に空白がない", limit=25)
        self.regex("P8", r"\b(?:Fig|Figs|Eq|Eqs|Sec|Ref|Tab)\.(?=\d)", "略語の後に空白がない（Fig. 2）", limit=25)
        self.regex("P8", r"[，．（）：；！？　、。「」０-９Ａ-Ｚａ-ｚ]", "全角記号・全角文字 '{m}'", limit=25)
        self.regex("F5", r"[\u3040-\u30ff\u4e00-\u9fff]+", "日本語の文字 '{m}'（図表・本文に残っていないか）",
                   blocks=list(range(len(self.doc.blocks))), limit=25)
        self.regex("P8", r"\.\.(?!\.)", "ピリオドの重複", limit=15)
        self.regex("P6", r"(?:^|[\s(\[])[”’](?=[A-Za-z])", "開き引用符が閉じ引用符になっている（LaTeX で \" を使った可能性 → ``…''）", limit=15)
        self.regex("G3", r"\?\?|\[\?\]", "未定義の参照（LaTeX の ??）", blocks=list(range(len(self.doc.blocks))), limit=20)

    def latin(self):
        self.regex("A2", r"\b(?:eg\.|ie\.|e\.g(?!\.)|i\.e(?!\.)|e\. g\.|i\. e\.)", "ラテン語略語の綴り '{m}' → e.g. / i.e.")
        self.regex("A2", r"such as[^.;:]{0,100}\betc\b", "such as と etc. の重複")
        self.regex("A3", r"\bet\.\s?al\.?|\bet al(?![.\w])", "et al. の句読点 '{m}'")
        with_c = without_c = 0
        for bi in self.prose:
            t = self.doc.blocks[bi]["text"]
            for m in re.finditer(r"\b(e\.g|i\.e)\.(,?)", t):
                if m.group(2):
                    with_c += 1
                else:
                    without_c += 1
                if not inside_parens(t, m.start()):
                    self.add("A2", bi, m.start(), f"本文中（カッコの外）の '{m.group(1)}.' → for example / that is と書き下すか、カッコ内へ")
        self.stats["eg_ie_comma"] = {"with_comma": with_c, "without_comma": without_c}

    def numbers(self):
        for bi in self.prose:
            t = self.doc.blocks[bi]["text"]
            for o, s in split_sentences(t):
                m = re.match(r"\s*(\d+(?:[,.]\d+)*)\s+[A-Za-z]", s)  # "1. Item" (a list) does not match
                if m and not re.match(r"\s*\d+(\.\d+)*\s+[A-Z][a-z]+(\s+[A-Z][a-z]+)*$", s.strip()):
                    self.add("W6", bi, o, f"文頭の数字 '{m.group(1)}' → 語で書くか語順を変える")
        self.regex("W6", r"\b\d{1,3}(?:\.\d{3})+,\d+\b|\b0,\d+\b", "小数点・桁区切りが英語の慣習と逆 '{m}'")
        attached = self.regex("A1", UNITS_ATTACHED, "数値と単位の間に空白がない '{m}'", limit=20)
        spaced_re = UNITS_ATTACHED.replace(r"(?:\.\d+)?(", r"(?:\.\d+)?\s(")
        spaced = sum(len(re.findall(spaced_re, self.doc.blocks[bi]["text"])) for bi in self.prose)
        pct_sp = sum(len(re.findall(r"\d\s%", self.doc.blocks[bi]["text"])) for bi in self.prose)
        pct = sum(len(re.findall(r"\d%", self.doc.blocks[bi]["text"])) for bi in self.prose)
        self.stats["units"] = {"attached": attached, "spaced": spaced, "percent_spaced": pct_sp, "percent_attached": pct}
        words = len(re.findall(r"\b(?:one|two|three|four|five|six|seven|eight|nine)\s+[a-z]+s\b", self.text_of(self.body), re.I))
        labels = {"fig", "fig.", "figs.", "figure", "figures", "table", "tables", "eq.", "eqs.", "equation", "section",
                  "sec.", "step", "phase", "type", "algorithm", "chapter", "appendix", "round", "experiment", "case",
                  "stage", "level", "version", "model", "setting", "scenario", "condition", "group", "study"}
        digits = sum(1 for m in re.finditer(r"(\S+)\s+([1-9])\s+(?!%|ms|s\b|cm|mm|kg|Hz)[a-z]+s\b", self.text_of(self.body))
                     if m.group(1).lower().strip("(~") not in labels and not re.search(r"[\d.,]$", m.group(1)))
        self.stats["small_numbers"] = {"as_words": words, "as_digits": digits}
        hy = sum(len(re.findall(r"\d-\d", self.doc.blocks[bi]["text"])) for bi in self.prose + self.refs)
        en = sum(len(re.findall(r"\d–\d", self.doc.blocks[bi]["text"])) for bi in self.prose + self.refs)
        sp = self.regex("P7", r"\d\s+[–-]\s+\d", "範囲のダッシュの前後に空白 '{m}'", blocks=self.prose + self.refs, limit=15)
        self.stats["ranges"] = {"hyphen": hy, "en_dash": en, "spaced": sp}
        if hy and en:
            self.regex("P7", r"\d+-\d+" if hy < en else r"\d+–\d+",
                       "範囲の記号が混在（少数派）'{m}'", blocks=self.prose + self.refs, limit=15)

    def punctuation_stats(self):
        t = self.text_of(self.prose)
        serial = len(re.findall(r"\w+, \w+(?: \w+)?, (?:and|or) \w+", t))
        no_serial = len(re.findall(r"\w+, \w+(?: \w+)? (?:and|or) \w+", t))
        self.stats["serial_comma"] = {"with": serial, "without(候補)": no_serial}
        self.stats["quotes"] = {"double_curly": t.count("“"), "single_curly_open": t.count("‘"), "straight_double": t.count('"')}

    def person(self):
        t = self.text_of(self.prose)
        we = len(re.findall(r"\b(?:we|We|our|Our|us)\b", t))
        i_ = len(re.findall(r"(?:^|[.!?]\s+|,\s+|\band\s+)I\s+(?:am|have|had|was|will|would|propose|argue|use|used|found|find|believe|think|conducted|collected|interviewed|observed|show|showed|discuss|focus|examine|analy[sz]e)\b", t))
        you = len(re.findall(r"\b(?:you|your|yours|yourself)\b", t, re.I))
        self.stats["person"] = {"we/our": we, "I": i_, "you": you}
        self.regex("R4", r"\b[Ww]e (?:can|could) (?:see|observe|notice|find|say|conclude)\b|\b[Aa]s we (?:all )?know\b|\b[Ww]e (?:all|humans?)\b|\b[Ww]e now know\b|\b[Ll]et us\b", "包括的な we '{m}' → 結果を主語にして述べる")
        self.regex("R4", r"\b(?:you|your)\b", "二人称 '{m}'", flags=re.I, limit=15)
        if we and i_:
            self.cands.append({"category": "R3", "page": None, "line": None, "snippet": "", "note": f"we/our {we} 件と I {i_} 件が混在"})

    def style_words(self):
        self.regex("W1", INFORMAL, "口語的な表現 '{m}'", flags=re.I, limit=30)
        self.regex("W1", SENT_START_INFORMAL, "文頭の '{m}'", group=1, limit=20)
        self.regex("E3", JE_UNCOUNTABLE, "不可算名詞の複数形 '{m}'", flags=re.I)
        self.regex("E4", JE_ABOUT, "不要な about '{m}'", flags=re.I)
        self.regex("E9", r"\b(?:can be considered that|it is considered that|It is considered that)\b", "直訳調 '{m}'")
        self.regex("E2", r"\b[Tt]he number of [a-z]+ (?:are|were|have)\b|\b[Ee]ach of the [a-z]+ (?:are|have|were)\b|\b[Ee]very [a-z]+ (?:are|have|were)\b", "主語と動詞の一致 '{m}'")
        self.regex("E4", r"\bbased of\b|\bdifferent with\b|\bcomprised of\b", "前置詞 '{m}'")
        self.regex("E5", r"\bmore (?:faster|better|larger|smaller|higher|lower|easier|simpler|worse)\b", "比較級の重複 '{m}'", flags=re.I)
        self.regex("T3", r"\b[Ii]t (?:was|is|can be|could be) (?:found|shown|seen|observed|noted|concluded|confirmed) that\b", "受動態の非人称構文 '{m}'（行為者を明示できるか）", limit=20)
        hits = 0
        for bi in self.prose:
            for m in re.finditer(r"\bto ([a-z]+ly) ([a-z]+)\b", self.doc.blocks[bi]["text"]):
                if m.group(1) in NON_ADVERB_LY or m.group(2) in ("the", "a", "an", "and", "or", "of", "to", "in"):
                    continue
                hits += 1
                if hits <= 20:
                    self.add("T4", bi, m.start(), f"分割不定詞 '{m.group(0)}'（style 扱い）")
        self.regex("E1", r"\b(?:propose|proposes|present|presents|introduce|introduces|develop|develops|design|designs)\s+(?:novel|new|simple|efficient|effective|robust|general|unified)\s+(?:method|approach|framework|model|algorithm|technique|scheme|system|strategy)\b",
                   "冠詞の欠落の可能性 '{m}'")
        self.regex("P4", r"\b(?:a|an|the|this|our|its|their)\s+(?:well known|well established|well defined|real world|large scale|long term|short term|high quality|low cost|fine grained|time consuming|data driven|end to end|state of the art|two stage|multi stage|so called|first order|second order|high dimensional|low dimensional)\s+[a-z]+",
                   "名詞の前の複合形容詞にハイフンがない '{m}'", flags=re.I)
        self.regex("P4", r"\b(?:is|are|was|were|be|been|remains?)\s+(?:well-known|well-established|well-defined|state-of-the-art)\b(?!\s+[a-z]+(?:s|ion|ers?|ods?|ms?)\b)",
                   "述語の位置の複合語にハイフン '{m}'（名詞の前でなければ不要）")
        self.regex("E6", r",\s+(?:this|it|they|these|we|there)\s+(?:is|are|was|were|shows?|suggests?|indicates?|means?|has|have|can|will)\b",
                   "コンマで2つの文をつないでいる可能性（comma splice）'{m}'")
        self.regex("E6", r"(?:^|[.!?]\s+)(?:Using|By using|Based on|Having|Considering|After applying|Applying)\b[^,.]{0,70},\s+(?:the|this|these|it|there)\b",
                   "ぶら下がり修飾の可能性（分詞の意味上の主語が主節の主語と違う）")
        self.regex("L1", r"\b(?:clearly|obviously|undoubtedly|certainly|prove|proves|proved|proven|always|never|perfectly|dramatically)\b",
                   "強い断定 '{m}'（証拠に見合うか。言い換えは意味を変えうるので著者確認）", flags=re.I, limit=20)
        self.regex("P6", r'"[^"]{1,60}"', "直線の二重引用符 {m}（LaTeX なら ``…''、引用符の種類を統一）", limit=15)
        t_all = self.text_of(self.prose)
        sing = re.findall(r"\bdata (?:is|was|has)\b", t_all)
        plur = re.findall(r"\bdata (?:are|were|have)\b", t_all)
        self.stats["data_is_are"] = {"singular": len(sing), "plural": len(plur)}
        if sing and plur:
            minority = r"\bdata (?:is|was|has)\b" if len(sing) <= len(plur) else r"\bdata (?:are|were|have)\b"
            self.regex("E2", minority, "data の単複が混在（style sheet で統一）'{m}'")
        for bi in self.prose:
            for o, s_ in split_sentences(self.doc.blocks[bi]["text"]):
                m = re.match(r"\s*(Although|Because|While|Whereas|If|When|Since|Unless|Though|Even though|Once|As long as)\b", s_)
                if not m:
                    continue
                words = s_.split()
                head = s_.split(",")[0].split()
                if len(words) > 10 and (len(head) > 12 or "," not in s_):
                    self.add("P2", bi, o, f"文頭の従属節（{m.group(1)} …）の後にコンマがない可能性")
        starts = Counter()
        where = {}
        for bi in self.prose:
            for o, s in split_sentences(self.doc.blocks[bi]["text"]):
                for c in CONNECTIVES:
                    if s.lstrip().startswith(c):
                        starts[c] += 1
                        where.setdefault(c, (bi, o))
        self.stats["sentence_initial_connectives"] = dict(starts.most_common())
        for c, n in starts.items():
            if n >= 5:
                bi, o = where[c]
                self.add("W5", bi, o, f"文頭の '{c}' が {n} 回（変化をつける）")

    def long_sentences(self):
        found = []
        for bi in self.prose:
            for o, s in split_sentences(self.doc.blocks[bi]["text"]):
                n = len(s.split())
                if n > 40:
                    found.append((n, bi, o, s))
        for n, bi, o, s in sorted(found, reverse=True)[:15]:
            self.add("L2", bi, o, f"{n} 語の文（分割を検討）", snippet=s[:120] + ("…" if len(s) > 120 else ""))

    def paragraphs(self):
        pron = single = 0
        for bi in self.body:
            t = self.doc.blocks[bi]["text"].strip()
            if not t or t[0] in "•-–(" or len(re.findall(r"[A-Za-z]", t)) < 0.5 * len(t):
                continue
            m = PRONOUN_START.match(t)
            if m and pron < 25:
                pron += 1
                self.add("S5", bi, 0, f"段落が代名詞 '{m.group(0)}' で始まる → 名詞句で主題を示す")
            sents = split_sentences(t)
            if len(sents) == 1 and len(t.split()) >= 6 and t.endswith(".") and single < 20:
                single += 1
                self.add("S4", bi, 0, "1文だけの段落（前後と統合できるか。ページ・段の境目の分割による誤検出に注意）")

    def check_headings(self):
        if not self.headings:
            return
        rows = ["| 位置 | 番号 | 見出し | 文字サイズ | 太字 | 大文字化 |", "|---|---|---|---|---|---|"]
        prev = None
        for bi, h in sorted(self.headings.items()):
            b = self.doc.blocks[bi]
            style = case_style(h["title"])
            rows.append(f"| p{b['page']} L{b['line']} | {h['num'] or '-'} | {md(h['title'][:60])} | {h['size'] or '-'} | {'○' if h['bold'] else ''} | {style} |")
            for m in re.finditer(r"\b[A-Z][A-Z0-9]*[A-Z][A-Z0-9]*s?\b", h["title"]):
                if m.group(0) not in COMMON_ACRONYMS and not h["title"].isupper():
                    self.add("S3", bi, 0, f"見出しに略語 '{m.group(0)}'")
            num = h["num"]
            if re.fullmatch(r"\d+(?:\.\d+)*", num):
                parts = [int(x) for x in num.split(".")]
                if prev is not None:
                    ok = (len(parts) == len(prev) and parts[:-1] == prev[:-1] and parts[-1] == prev[-1] + 1) or \
                         (len(parts) == len(prev) + 1 and parts[:-1] == prev and parts[-1] == 1) or \
                         (len(parts) < len(prev) and parts[:-1] == prev[:len(parts) - 1] and parts[-1] == prev[len(parts) - 1] + 1)
                    if not ok:
                        self.add("S2", bi, 0, f"節番号の飛び・重複: {'.'.join(map(str, prev))} の次が {num}")
                prev = parts
        by_level = {}
        for bi, h in self.headings.items():
            if re.fullmatch(r"\d+(?:\.\d+)*", h["num"]):
                by_level.setdefault(h["num"].count("."), []).append((case_style(h["title"]), bi))
        for level, hs in by_level.items():
            styles = Counter(st_ for st_, _ in hs if st_ in ("Title Case", "Sentence case"))
            if len(styles) == 2:
                split = f"Title Case {styles['Title Case']} / Sentence case {styles['Sentence case']}"
                if styles["Title Case"] == styles["Sentence case"]:
                    bi = next(bi for st_, bi in hs if st_ in styles)
                    self.add("S1", bi, 0, f"同じ階層の見出しで大文字化が混在（{split}、同数なので規定・既刊論文で決める）")
                    continue
                minority = min(styles, key=styles.get)
                for st_, bi in hs:
                    if st_ == minority:
                        self.add("S1", bi, 0, f"同じ階層の見出しで大文字化が混在（{split}。少数派の {minority}）")
        self.extra_md.append("## S1/S2 見出しの一覧（自動検出。同じ階層の書式が揃っているかを見る）\n\n" + "\n".join(rows) + "\n")

    def acronyms(self):
        d = self.doc
        token = re.compile(r"(?<![A-Za-z0-9])([A-Z][A-Za-z0-9]*[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*)(s)?(?![\w])")
        uses = OrderedDict()
        defs = {}
        order = sorted(set(self.prose) | set(self.headings))
        for bi in order:
            t = d.blocks[bi]["text"]
            if t.isupper():
                continue
            for m in token.finditer(t):
                a = m.group(1)
                if re.fullmatch(r"[IVXLC]+", a) or a in COMMON_ACRONYMS:
                    continue
                if len(a) >= 4 and a.isalpha() and a.lower() in d.lower_vocab and a.isupper():
                    continue  # an ordinary word typed in capitals
                if sum(ch.islower() for ch in a) > sum(ch.isupper() for ch in a):
                    continue  # CamelCase names such as ResNet
                uses.setdefault(a, []).append((bi, m.start()))
                before = t[:m.start()].rstrip()
                after = t[m.end():m.end() + 2]
                if before.endswith("(") and (after.startswith(")") or after.startswith(";") or after.startswith(",")):
                    words = re.findall(r"[A-Za-z][A-Za-z\-]*", before[:-1])[-8:]
                    defs.setdefault(a, []).append((bi, m.start(), " ".join(words)))
                else:
                    fm = re.match(r"\s*\(([A-Za-z][^()]{3,80})\)", t[m.end():])
                    if fm:
                        initials = "".join(w[0] for w in re.findall(r"[A-Za-z]+", fm.group(1)) if w.lower() not in MINOR_WORDS).upper()
                        if a.replace("-", "")[:2].upper() in initials:
                            defs.setdefault(a, []).append((bi, m.start(), fm.group(1)))
        abstract = set(self.abstract)
        rows = ["| 略語 | 回数 | 初出 | 定義（本文） | 注意 |", "|---|---|---|---|---|"]
        body_start = min(self.body) if self.body else 0
        for a, us in sorted(uses.items(), key=lambda kv: (kv[1][0][0], kv[1][0][1])):
            ds = defs.get(a, [])
            body_defs = [x for x in ds if x[0] not in abstract]
            body_uses = [u for u in us if u[0] not in abstract and u[0] >= body_start]
            notes = []
            if not ds:
                notes.append("定義が見つからない")
            elif body_uses and not body_defs:
                notes.append("要旨でのみ定義（本文でも初出で定義）")
            elif body_defs and body_uses and (body_uses[0][0], body_uses[0][1]) < (body_defs[0][0], body_defs[0][1]):
                notes.append("定義より前に使用")
            if len(body_defs) > 1:
                notes.append(f"本文で {len(body_defs)} 回定義")
            after = [u for u in body_uses if body_defs and (u[0], u[1]) > (body_defs[0][0], body_defs[0][1])]
            def_spots = {(x[0], x[1]) for x in ds}
            if ds and all((u[0], u[1]) in def_spots for u in us):
                notes.append("定義だけで、どこでも使われていない（定義を削るか書き下す）")
            elif body_defs and len(after) == 0:
                notes.append("定義後に使われていない")
            elif body_defs and len(after) == 1:
                notes.append("定義後1回だけ（書き下しを検討）")
            if body_defs and body_defs[0][2]:
                full = " ".join(body_defs[0][2].split()[-max(2, min(len(a), 6)):])
                later = self.text_of([i for i in self.body if i > body_defs[0][0]])
                if len(full) > 6 and re.search(re.escape(full), later, re.I):
                    notes.append(f"定義後も正式名称 '{full}' を使用")
            p, ln = d.loc(*us[0])
            dp = f"p{d.loc(*body_defs[0][:2])[0]}" if body_defs else ("要旨" if ds else "-")
            rows.append(f"| {a} | {len(us)} | p{p} L{ln} | {dp} | {'; '.join(notes)} |")
            if notes:
                serious = any(n.startswith(("定義が見つからない", "要旨でのみ", "定義より前")) for n in notes)
                self.add("A4" if serious else "A5", us[0][0], us[0][1], f"略語 {a}: {'; '.join(notes)}")
        self.stats["acronyms"] = len(uses)
        self.extra_md.append("## A4/A5 略語の一覧（自動検出。一般に通用する略語は除外済み）\n\n" + "\n".join(rows) + "\n")
        for bi in self.abstract:
            for m in token.finditer(d.blocks[bi]["text"]):
                a = m.group(1)
                if a in uses and not any(x[0] in abstract for x in defs.get(a, [])):
                    self.add("A6", bi, m.start(), f"要旨の略語 {a} が要旨内で定義されていない")
                    break

    def figures(self):
        d = self.doc
        caps = {"fig": {}, "tab": {}}
        for bi in sorted(self.captions):
            m = CAPTION_RE.match(d.blocks[bi]["text"])
            kind = "tab" if m.group(1).lower().startswith("tab") else "fig"
            caps[kind].setdefault(num_of(m.group(2)), bi)
        first, forms = {"fig": OrderedDict(), "tab": OrderedDict()}, Counter()
        for bi in self.prose:
            if bi in self.captions:
                continue
            t = d.blocks[bi]["text"]
            for m in MENTION_RE.finditer(t):
                kind = "tab" if m.group(1).lower().startswith("tab") else "fig"
                forms[m.group(1).rstrip(".").rstrip("s")] += 1
                nums = []
                for a_, b_ in re.findall(r"(\d+|[IVX]+)\s*(?:[–-]|to)\s*(\d+|[IVX]+)", m.group(2)):
                    nums += list(range(num_of(a_), num_of(b_) + 1))
                nums += [num_of(x) for x in re.findall(r"\d+|\b[IVX]+\b", m.group(2))]
                for n in nums:
                    first[kind].setdefault(n, (bi, m.start()))
                prev = t[:m.start()].rstrip()
                if m.group(1).startswith("Fig.") and (not prev or prev.endswith((".", "!", "?"))):
                    self.add("F4", bi, m.start(), "文頭の 'Fig.'（APA などは 'Figure'、IEEE は文頭でも 'Fig.'。規定と style sheet で判断）")
        label = {"fig": "図", "tab": "表"}
        for kind in ("fig", "tab"):
            seq = list(first[kind].keys())
            for i, n in enumerate(seq):
                if any(m > n for m in seq[:i]):
                    bi, off = first[kind][n]
                    self.add("F3", bi, off, f"{label[kind]} {n} の初出が、より大きい番号の後")
            for n, bi in caps[kind].items():
                if n not in first[kind]:
                    self.add("F3", bi, 0, f"{label[kind]} {n} が本文で言及されていない")
            nums = sorted(caps[kind])
            if nums and nums != list(range(1, nums[-1] + 1)):
                self.cands.append({"category": "F3", "page": None, "line": None, "snippet": "",
                                   "note": f"{label[kind]}のキャプション番号が連続していない: {nums}（キャプション検出漏れの可能性もある）"})
        self.stats["figure_label_forms"] = dict(forms)
        self.stats["captions"] = {"figures": sorted(caps["fig"]), "tables": sorted(caps["tab"])}

    def citations(self):
        d = self.doc
        body_text_blocks = [i for i in self.prose if i not in self.refs]
        numeric, first = 0, OrderedDict()
        for bi in body_text_blocks:
            for m in re.finditer(r"\[(\s*\d+(?:\s*[-–,]\s*\d+)*\s*)\]", d.blocks[bi]["text"]):
                if "0" in re.findall(r"\d+", m.group(1)) or re.search(r"\d\.\d", m.group(1)):
                    continue  # an interval such as [0, 1], not a citation
                numeric += 1
                for part in m.group(1).split(","):
                    r = re.split(r"\s*[-–]\s*", part.strip())
                    nums = range(int(r[0]), int(r[-1]) + 1) if len(r) == 2 and r[0].isdigit() and r[1].isdigit() else [int(x) for x in r if x.isdigit()]
                    for n in nums:
                        first.setdefault(n, (bi, m.start()))
        ref_text = self.text_of(self.refs)
        entries = set()
        for bi in self.refs:
            for ln_text in [d.blocks[bi]["text"]] + re.split(r"(?=\[\d+\])", d.blocks[bi]["text"]):
                m = re.match(r"^\s*(?:References\s*)?\[(\d+)\]|^\s*(\d+)\.\s+[A-Z]", ln_text)
                if m:
                    entries.add(int(m.group(1) or m.group(2)))
        ay_paren = ay_narr = 0
        ay_cites = []
        skip = set("In The A An Figure Fig Table Section Eq Equation Appendix Since From After Before Between During Until By Of On At For And Or See Also cf".split())
        for bi in body_text_blocks:
            t = d.blocks[bi]["text"]
            for m in re.finditer(r"\(([^()]*?\b(?:19|20)\d{2}[a-z]?[^()]*)\)", t):
                for part in m.group(1).split(";"):
                    nm = re.search(r"([A-Z][A-Za-z'’\-]+)(?:\s+et al\.?|\s+(?:and|&)\s+[A-Z][A-Za-z'’\-]+)?,?\s+((?:19|20)\d{2}[a-z]?)", part)
                    if nm and nm.group(1) not in skip:
                        ay_paren += 1
                        ay_cites.append((nm.group(1), nm.group(2), bi, m.start()))
            for m in re.finditer(r"\b([A-Z][A-Za-z'’\-]+)(?:\s+et al\.?|\s+(?:and|&)\s+[A-Z][A-Za-z'’\-]+)?\s*\(((?:19|20)\d{2}[a-z]?)[),]", t):
                if m.group(1) not in skip:
                    ay_narr += 1
                    ay_cites.append((m.group(1), m.group(2), bi, m.start()))
        titles = []
        for bi in self.refs:
            for m in re.finditer(r"[“\"]([^”\"]{12,220}?)[,.]?[”\"]", d.blocks[bi]["text"]):
                titles.append((case_style(m.group(1)), bi, m.start(), m.group(1)))
        styles = Counter(t[0] for t in titles if t[0] in ("Title Case", "Sentence case"))
        self.stats["reference_title_case"] = dict(styles)
        if len(styles) == 2:
            minority = min(styles, key=styles.get)
            for st_, bi, off, title in titles:
                if st_ == minority:
                    self.add("C5", bi, off, f"文献タイトルの大文字化が他と違う（{minority}; 多数派は {max(styles, key=styles.get)}）")
        style = "numeric" if numeric >= max(3, ay_paren + ay_narr) else "author-year" if ay_paren + ay_narr >= 3 else "不明"
        self.stats["citations"] = {"style_guess": style, "numeric_brackets": numeric, "author_year": ay_paren + ay_narr,
                                   "reference_entries_numbered": len(entries)}
        if style == "numeric":
            seq = list(first.keys())
            out_of_order = [n for i, n in enumerate(seq) if any(m > n for m in seq[:i])]
            if out_of_order:
                bi, off = first[out_of_order[0]]
                self.add("C3", bi, off, f"番号が初出順でない（例: [{out_of_order[0]}]）。文献リストがアルファベット順の番号方式なら問題なし。該当: {out_of_order[:10]}")
            if entries:
                missing = sorted(set(first) - entries)
                uncited = sorted(entries - set(first))
                if missing:
                    bi, off = first[missing[0]]
                    self.add("C4", bi, off, f"文献リストにない番号を引用: {missing[:15]}")
                if uncited:
                    self.cands.append({"category": "C4", "page": None, "line": None, "snippet": "",
                                       "note": f"本文で引用されていない文献番号: {uncited[:20]}（上付き番号の引用は検出できないので注意）"})
        elif style == "author-year":
            seen = set()
            for name, year, bi, off in ay_cites:
                if (name, year) in seen:
                    continue
                seen.add((name, year))
                ok = any(re.search(re.escape(year[:4]), ref_text[m.start():m.start() + 400])
                         for m in re.finditer(r"\b" + re.escape(name) + r"\b", ref_text))
                if not ok:
                    self.add("C4", bi, off, f"文献リストに '{name} … {year}' が見つからない")
            t = self.text_of(body_text_blocks)
            self.stats["citations"]["paren_with_comma"] = len(re.findall(r"\([A-Z][A-Za-z'\-]+(?: et al\.)?, (?:19|20)\d{2}", t))
            self.stats["citations"]["paren_without_comma"] = len(re.findall(r"\([A-Z][A-Za-z'\-]+(?: et al\.)? (?:19|20)\d{2}", t))
            self.stats["citations"]["ampersand_in_parens"] = len(re.findall(r"\([^()]*&[^()]*\d{4}", t))
            self.stats["citations"]["and_in_parens"] = len(re.findall(r"\([^()]* and [^()]*\d{4}", t))

    def title_abstract(self):
        d = self.doc
        p1 = [(n, m) for (p, n), m in d.meta.items() if p == 1 and m.get("size")]
        if p1:
            mx = max(m["size"] for _, m in p1)
            title = " ".join(m["text"] for n, m in sorted(p1) if m["size"] >= mx - 0.3)
            words = len(title.split())
            self.stats["title"] = {"text": title[:200], "words": words}
            if re.search(r"\b(A Study (of|on)|An Investigation (of|into)|Research on|Results of|A Novel|Novel)\b", title, re.I):
                self.cands.append({"category": "K1", "page": 1, "line": None, "snippet": title[:120], "note": "タイトルの不要語（A Study of / Novel など）"})
        if self.abstract:
            t = self.text_of(self.abstract)
            words = len(re.sub(r"^\s*(Abstract|ABSTRACT|Summary)\s*[—:.\-–]?", "", t).split())
            self.stats["abstract_words"] = words
            for bi in self.abstract:
                for m in re.finditer(r"\[\d+(?:[,–-]\s*\d+)*\]|\([A-Z][A-Za-z\-]+(?: et al\.)?,? (?:19|20)\d{2}\)", d.blocks[bi]["text"]):
                    self.add("K2", bi, m.start(), f"要旨に引用 '{m.group(0)}'")
        if self.kw_i is not None:
            t = re.sub(r"^\s*(Key ?words|Index Terms)\s*[—:.\-–]*\s*", "", d.blocks[self.kw_i]["text"], flags=re.I)
            items = [x.strip() for x in re.split(r"[;,·•]", t) if x.strip()]
            self.stats["keywords"] = {"count": len(items), "items": items[:12]}
            for x in items:
                if re.search(r"\b(and|or|between|of the)\b", x):
                    self.add("K3", self.kw_i, 0, f"キーワードにつなぎ語: '{x}'")

    def run(self):
        for f in (self.overview, self.variety, self.contractions, self.repeated, self.spacing, self.latin,
                  self.numbers, self.punctuation_stats, self.person, self.style_words, self.long_sentences,
                  self.paragraphs, self.check_headings, self.acronyms, self.figures, self.citations, self.title_abstract):
            try:
                f()
            except Exception as e:  # one broken heuristic must not hide the others
                self.cands.append({"category": "-", "page": None, "line": None, "snippet": "", "note": f"scan:{f.__name__} failed: {e}"})
        return self


def md(s):
    return str(s).replace("|", "\\|").replace("\n", "<br>")


def cmd_scan(a):
    doc = Doc(a.txt)
    sc = Scanner(doc).run()
    out = Path(a.o)
    st = sc.stats
    lines = ["# scan：機械的チェックの候補", "",
             "正規表現などで拾った**候補**の一覧で、誤検出を含む。各候補は本文を読んで判定し、本当に問題なものだけを corrections.json に入れる。"
             "ここに無い誤り（冠詞、時制、語法、論理のつながりなど）の方が多いので、これは精読の代わりにはならない。", "",
             "## 概要", ""]
    v = st.get("variety", {})
    c = st.get("citations", {})
    lines += [f"- ページ {st.get('pages')} / 語数 約 {st.get('words')}",
              f"- 範囲の推定: {st.get('zones')}",
              f"- タイトル: {st.get('title', {}).get('text', '未検出')}（{st.get('title', {}).get('words', '-')} 語）",
              f"- 要旨: {st.get('abstract_words', '未検出')} 語 / キーワード: {st.get('keywords', {}).get('count', '未検出')} 個 {st.get('keywords', {}).get('items', '')}",
              f"- 綴り: 推定 {v.get('guess')}（UK {v.get('UK')} / US {v.get('US')}）",
              f"- 引用方式: 推定 {c.get('style_guess')}（[n] {c.get('numeric_brackets')} / 著者年 {c.get('author_year')} / 番号付き文献 {c.get('reference_entries_numbered')}）",
              f"- 連続コンマ: {st.get('serial_comma')}",
              f"- e.g./i.e. の後のコンマ: {st.get('eg_ie_comma')}",
              f"- 引用符: {st.get('quotes')}",
              f"- 範囲の記号: {st.get('ranges')}",
              f"- 単位: {st.get('units')}",
              f"- 1〜9 の数: {st.get('small_numbers')}",
              f"- 人称: {st.get('person')}",
              f"- 文頭の接続語: {st.get('sentence_initial_connectives')}",
              f"- 図表ラベルの書き方: {st.get('figure_label_forms')} / キャプション: {st.get('captions')}", ""]
    lines += sc.extra_md
    lines += ["## 個別の候補（チェックリストの区分順）", ""]
    by = OrderedDict()
    for cand in sorted(sc.cands, key=lambda c: (c["category"], c["page"] or 0, c["line"] or 0)):
        by.setdefault(cand["category"], []).append(cand)
    for cat, cs in by.items():
        lines.append(f"### {cat} {CATEGORY.get(cat, '')}（{len(cs)}）")
        for cand in cs:
            loc = f"p{cand['page']} L{cand['line']}" if cand["page"] and cand["line"] else (f"p{cand['page']}" if cand["page"] else "全体")
            snip = f" — `{cand['snippet'].replace('`', '')}`" if cand["snippet"] else ""
            lines.append(f"- {loc}: {cand['note']}{snip}")
        lines.append("")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(out.with_suffix(".json"), {"stats": st, "candidates": sc.cands})
    print(f"wrote {out}: {len(sc.cands)} candidate(s); spelling {v.get('guess')}, citations {c.get('style_guess')}")


# ---------------------------------------------------------------- corrections

def round_of(path):
    m = re.search(r"r(\d+)", Path(path).parent.name)
    return int(m.group(1)) if m else None


def default_text_for(corr_path):
    return Path(corr_path).parent / "paper.txt"


def validate(corr_path, text_path=None, fix_ids=False):
    data = read_json(corr_path)
    problems, warnings = [], []
    items = data.get("items")
    if not isinstance(items, list):
        return data, ["`items` (list) がない"], warnings
    rnd = data.get("round") or round_of(corr_path) or 1
    text_path = Path(text_path) if text_path else default_text_for(corr_path)
    index = TextIndex(Doc(text_path)) if text_path.exists() else None
    if index is None:
        warnings.append(f"text not found: {text_path} (original の照合を省略)")
    ids = Counter()
    changed = False
    for i, it in enumerate(items):
        if fix_ids and not it.get("id"):
            it["id"] = f"R{rnd}-{i + 1:03d}"
            changed = True
        iid = it.get("id", f"#{i + 1}")
        ids[iid] += 1
        sev = it.get("severity")
        if sev not in SEVERITIES:
            problems.append(f"{iid}: severity '{sev}' は {SEVERITIES} のどれか")
        if it.get("category") not in CATEGORY:
            warnings.append(f"{iid}: category '{it.get('category')}' はチェックリストにない")
        if not isinstance(it.get("page"), int):
            problems.append(f"{iid}: page（整数）がない")
        if not it.get("reason"):
            problems.append(f"{iid}: reason がない")
        glob = it.get("scope") == "global"
        rep = it.get("replace")
        if rep is not None and not (isinstance(rep, list) and all(isinstance(p, list) and len(p) == 2 and all(isinstance(x, str) for x in p) for p in rep)):
            problems.append(f"{iid}: replace は [[\"置き換え前\", \"置き換え後\"], …] の形にする")
        for extra in it.get("also") or []:
            if extra not in CATEGORY:
                warnings.append(f"{iid}: also の '{extra}' はチェックリストにない")
        orig, sug = it.get("original", ""), it.get("suggestion", "")
        if not orig and not glob:
            problems.append(f"{iid}: original がない")
        if sev not in ("query",) and not glob and sug == "" and not it.get("delete"):
            problems.append(f"{iid}: suggestion がない（削除なら \"delete\": true）")
        if orig and sug and " ".join(orig.split()) == " ".join(sug.split()):
            problems.append(f"{iid}: original と suggestion が同じ")  # dash/quote-only fixes differ here, so they pass
        if orig and index is not None:
            hit = index.find(orig)
            if hit is None:
                problems.append(f"{iid}: original がPDFのテキストに見つからない → 正確に写す: \"{orig[:70]}\"")
            elif hit == "case":
                warnings.append(f"{iid}: original の大文字・小文字がPDFと違う")
            elif index.count(orig) > 1 and not glob:
                warnings.append(f"{iid}: original がPDF内に {index.count(orig)} 回ある（page/line で区別はされるが、一意になるまで前後の語を足すと確実）")
    for iid, n in ids.items():
        if n > 1:
            problems.append(f"ID の重複: {iid} ×{n}")
    for pc in data.get("previous_check", []) or []:
        if pc.get("status") not in PREV_STATUS:
            problems.append(f"previous_check {pc.get('id')}: status は {PREV_STATUS} のどれか")
    if changed:
        write_json(corr_path, data)
    return data, problems, warnings


def cmd_validate(a):
    _, problems, warnings = validate(a.corr, a.text, fix_ids=True)
    for w in warnings:
        print("WARN  " + w)
    for p in problems:
        print("ERROR " + p)
    print("VALID" if not problems else f"{len(problems)} problem(s)")
    sys.exit(1 if problems else 0)


def counted(it):
    """A global item records a rule whose occurrences are listed as their own items, so it is
    not counted again -- unless it stands in for occurrences that are not listed separately."""
    return it.get("scope") != "global" or bool(it.get("occurrences"))


def counts(items):
    c = Counter(it.get("severity") for it in items if counted(it))
    return {s: c.get(s, 0) for s in SEVERITIES}


def cmd_report(a):
    data, problems, warnings = validate(a.corr, a.text, fix_ids=True)
    for p in problems:
        print("ERROR " + p)
    for w in warnings:
        print("WARN  " + w)
    items = data.get("items", [])
    rnd = data.get("round") or round_of(a.corr) or 1
    cnt = counts(items)
    n_rules = sum(1 for it in items if not counted(it))
    s = data.get("settings", {}) or {}
    target = data.get("pdf", "")
    state_p = Path(a.corr).resolve().parent.parent.parent / "state.json"  # <ws>/rounds/rNN/corrections.json
    if state_p.exists():
        st = read_json(state_p)
        target = f"{Path(st['pdf']).name}" + ("（元の PDF）" if rnd == 1 else f"（修正版 r{rnd:02d}）")
    L = [f"# 英文校正レポート — Round {rnd}", "",
         f"- 対象: {target}",
         f"- 設定: 英語 {s.get('variety', '-')} / 引用 {s.get('citation_style', '-')} / 投稿先 {s.get('journal', '指定なし')}",
         f"- 指摘: 誤り {cnt['error']} / 明確さ {cnt['clarity']} / 文体 {cnt['style']} / 著者確認 {cnt['query']}（計 {sum(cnt.values())}）"
         + (f"。ほかに論文全体に適用する規則 {n_rules} 件（🌐。各箇所は個別の指摘として数えている）" if n_rules else ""),
         "- 重大度: **誤り** = 規則違反・不統一・規定違反 / **明確さ** = 誤読・曖昧さ / **文体** = 任意の磨き上げ / **著者確認** = 校正者だけでは決められない点", ""]
    if s.get("notes"):
        L += [f"- メモ: {s['notes']}", ""]
    if data.get("summary"):
        L += ["## 全体所見", "", data["summary"], ""]
    cat = Counter(it.get("category") for it in items if it.get("severity") in COUNTED and counted(it))
    if cat:
        L += ["## 区分別の件数（誤り＋明確さ）", "", "| 区分 | 件数 |", "|---|---|"]
        L += [f"| {k} {CATEGORY.get(k, '')} | {v} |" for k, v in cat.most_common()]
        L.append("")
    prev = data.get("previous_check") or []
    if prev:
        pc = Counter(p.get("status") for p in prev)
        L += ["## 前回の指摘の反映状況", "",
              f"解決 {pc.get('resolved', 0)} / 残存 {pc.get('remaining', 0)} / 書き換えで別の形 {pc.get('changed', 0)} / 該当箇所なし {pc.get('not_applicable', 0)}", ""]
        rem = [p for p in prev if p.get("status") in ("remaining", "changed")]
        if rem:
            L += ["| 前回ID | 状態 | メモ |", "|---|---|---|"] + [f"| {p.get('id')} | {p.get('status')} | {md(p.get('note', ''))} |" for p in rem]
            L.append("")
    intro = [it for it in items if it.get("introduced")]
    if intro:
        L += [f"改訂で新たに入った誤り: {len(intro)} 件（ID に ★）", ""]
    L += ["## 指摘一覧", ""]
    for sev in SEVERITIES:
        group = sorted((it for it in items if it.get("severity") == sev), key=lambda it: (it.get("page") or 0, it.get("line") or 0))
        if not group:
            continue
        L += [f"### {SEV_JA[sev]}（{sev}）— {len(group)} 件", ""]
        if sev == "query":
            L += ["| ID | 位置 | 区分 | 該当箇所 | 質問・提案 |", "|---|---|---|---|---|"]
        else:
            L += ["| ID | 位置 | 区分 | 原文 | 修正案 | 理由 |", "|---|---|---|---|---|---|"]
        for it in group:
            loc = f"p.{it.get('page')}" + (f" L{it['line']}" if it.get("line") else "") + (f"<br>{md(it['section'])}" if it.get("section") else "")
            iid = it.get("id", "") + (" ★" if it.get("introduced") else "") + (" 🌐" if it.get("scope") == "global" else "")
            c = f"{it.get('category', '')} {CATEGORY.get(it.get('category'), '')}" + (f"（＋{', '.join(it['also'])}）" if it.get("also") else "")
            orig = it.get("original") or it.get("pattern", "")
            if sev == "query":
                q = md(it.get("reason", "")) + (f"<br>案: {md(it['suggestion'])}" if it.get("suggestion") else "")
                L.append(f"| {iid} | {loc} | {c} | {md(orig)} | {q} |")
            else:
                sug = "（削除）" if it.get("delete") and not it.get("suggestion") else it.get("suggestion", "")
                L.append(f"| {iid} | {loc} | {c} | {md(orig)} | {md(sug)} | {md(it.get('reason', ''))} |")
        L.append("")
    if any(it.get("scope") == "global" for it in items):
        L += ["🌐 = 論文全体に適用する指摘（同じ規則を全箇所に）", ""]
    out = Path(a.o) if a.o else Path(a.corr).with_name("report.md")
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {out}: error {cnt['error']} / clarity {cnt['clarity']} / style {cnt['style']} / query {cnt['query']}"
          + (f"  — fix the {len(problems)} problem(s) above and rerun" if problems else ""))


def cmd_merge(a):
    parts = [read_json(p) for p in a.parts]
    rnd = a.round or next((p.get("round") for p in parts if p.get("round")), None) or round_of(a.out) or 1
    items, seen = [], set()
    for p in parts:
        for it in p.get("items", []):
            key = (it.get("page"), norm(it.get("original", "")), norm(it.get("suggestion", "")))
            if key in seen and it.get("original"):
                continue
            seen.add(key)
            items.append(it)
    items.sort(key=lambda it: (it.get("page") or 0, it.get("line") or 0))
    for i, it in enumerate(items):
        it["id"] = f"R{rnd}-{i + 1:03d}"
    prev = OrderedDict()
    for p in parts:
        for pc in p.get("previous_check", []) or []:
            prev[pc.get("id")] = pc
    merged = {"round": rnd,
              "pdf": next((p.get("pdf") for p in parts if p.get("pdf")), ""),
              "settings": next((p.get("settings") for p in parts if p.get("settings")), {}),
              "summary": "\n\n".join(p.get("summary", "") for p in parts if p.get("summary")),
              "items": items, "previous_check": list(prev.values())}
    write_json(a.out, merged)
    print(f"merged {len(a.parts)} part(s) -> {a.out}: {len(items)} item(s), IDs renumbered R{rnd}-001…")


# ---------------------------------------------------------------- annotate

def _load_lines(path):
    if not path or not Path(path).exists():
        return {}
    return {(pg["page"], ln["n"]): ln for pg in read_json(path).get("pages", []) for ln in pg["lines"]}


def _search(page, needle):
    flags = fitz.TEXT_DEHYPHENATE | fitz.TEXT_PRESERVE_WHITESPACE | fitz.TEXT_MEDIABOX_CLIP
    try:
        return page.search_for(needle, quads=True, flags=flags)
    except TypeError:  # older PyMuPDF
        return page.search_for(needle, quads=True)


def _hits(quads, needle):
    """Group search quads into hits: a hit may consist of several spans on one line and may
    wrap onto following lines."""
    if not quads:
        return []
    max_lines = len(needle) // 40 + 2
    hits = [[quads[0]]]
    for q in quads[1:]:
        prev = hits[-1][-1].rect
        h = max(prev.height, 1)
        same_line = abs(q.rect.y0 - prev.y0) < 0.4 * h and 0 <= q.rect.x0 - prev.x1 < 3 * h  # split spans
        next_line = prev.y0 + 0.5 * h < q.rect.y0 < prev.y1 + 1.0 * h  # the hit wraps onto the next line
        lines = len({round(x.rect.y0) for x in hits[-1]})
        unfinished = sum(x.rect.width for x in hits[-1]) < 0.85 * len(needle) * 0.42 * h  # ~0.42 em per character
        if same_line or (next_line and unfinished and lines < max_lines):
            hits[-1].append(q)
        else:
            hits.append([q])
    return hits


def _pick(quads, target, needle):
    """The hit nearest the reported line (or the first hit)."""
    hits = _hits(quads, needle)
    if not hits or not target:
        return hits[0] if hits else []
    return min(hits, key=lambda hit: min(abs(q.rect.y0 - target[1]) for q in hit))


def _locate(doc, pno, original, target, page_lines):
    """(page index, quads) for `original`. Long passages that the search cannot match whole
    (a reflowed paragraph, an extraction quirk) are covered from the hit of their first words
    to the hit of their last words, including the lines in between."""
    pages = [pno] + [p for p in (pno - 1, pno + 1) if 0 <= p < len(doc)]
    t = re.sub(r"\s+", " ", original).strip()
    for p in pages:
        for needle in dict.fromkeys([t, t.translate(TRANS)]):
            qs = _search(doc[p], needle)
            if qs:
                return p, _pick(qs, target if p == pno else None, needle)
    w = t.split()
    if len(w) >= 6:
        k = min(6, len(w) // 2)
        head, tail = " ".join(w[:k]), " ".join(w[-k:])
        for p in pages:
            hq, tq = _search(doc[p], head), _search(doc[p], tail)
            if not (hq and tq):
                continue
            first = _pick(hq, target if p == pno else None, head)
            later = [h for h in _hits(tq, tail) if h[0].rect.y0 >= first[0].rect.y0 - 1]
            if not later:
                continue
            last = min(later, key=lambda h: h[0].rect.y0)
            x0 = min(q.rect.x0 for q in first + last) - 40
            x1 = max(q.rect.x1 for q in first + last) + 40
            middle = [fitz.Rect(ln["bbox"]).quad for ln in page_lines.get(p + 1, [])
                      if ln.get("bbox") and first[-1].rect.y1 - 1 < (ln["bbox"][1] + ln["bbox"][3]) / 2 < last[0].rect.y0
                      and ln["bbox"][0] >= x0 and ln["bbox"][2] <= x1]
            return p, first + middle + last
    for p in pages:
        for needle in ([" ".join(w[:6]), " ".join(w[-6:])] if len(w) > 6 else []) + ([" ".join(w[:3])] if len(w) > 3 else []):
            qs = _search(doc[p], needle)
            if qs:
                return p, _pick(qs, target if p == pno else None, needle)
    return None, []


def cmd_annotate(a):
    if fitz is None:
        sys.exit("annotate needs PyMuPDF: pip install pymupdf")
    data = read_json(a.corr)
    lines = _load_lines(a.lines or Path(a.corr).with_name("paper.lines.json"))
    page_lines = {}
    for (p, _), ln in sorted(lines.items()):
        page_lines.setdefault(p, []).append(ln)
    only = set(a.only.split(",")) if a.only else set(SEVERITIES)
    doc = fitz.open(a.pdf)
    stats = Counter()
    for it in data.get("items", []):
        sev = it.get("severity", "error")
        if sev not in only:
            continue
        pno = (it.get("page") or 1) - 1
        if not 0 <= pno < len(doc):
            pno = 0
        meta = lines.get((pno + 1, it.get("line")))
        target = meta["bbox"] if meta and meta.get("bbox") else None
        content = []
        if it.get("suggestion"):
            content.append(f"修正案: {it['suggestion']}")
        elif it.get("delete"):
            content.append("修正案: （削除）")
        if it.get("pattern"):
            content.append(f"規則: {it['pattern']}")
        content.append(f"理由: {it.get('reason', '')}")
        title = f"{it.get('id', '')} {SEV_JA.get(sev, sev)} {it.get('category', '')} {CATEGORY.get(it.get('category'), '')}".strip() \
            + (f" ＋{','.join(it['also'])}" if it.get("also") else "")
        quads, where = [], None
        if it.get("original"):
            where, quads = _locate(doc, pno, it["original"], target, page_lines)
        page = doc[where if quads else pno]  # keep the page alive while the annotation is edited
        if quads:
            annot = page.add_highlight_annot(quads)
            stats["highlight"] += 1
        elif target:
            # cover as many lines of the paragraph as the quoted text is long
            same = [ln for ln in page_lines.get(pno + 1, []) if ln.get("block") == meta.get("block") and ln["n"] >= meta["n"] and ln.get("bbox")]
            k = max(1, round(len(it.get("original", "")) / max(len(meta.get("text", "")), 30)))
            annot = page.add_highlight_annot([fitz.Rect(ln["bbox"]).quad for ln in same[:k]] or fitz.Rect(target))
            stats["line"] += 1
        else:
            y = 30 + 14 * (stats["note"] % 40)
            annot = page.add_text_annot(fitz.Point(12, y), "", icon="Comment")
            stats["note"] += 1
        annot.set_colors(stroke=COLORS.get(sev, COLORS["error"]))
        annot.set_info(title=title, content="\n".join(content), subject=f"{SEV_JA.get(sev, sev)} / {it.get('original', '')[:60]}")
        annot.update()
    out = Path(a.o)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out), garbage=3, deflate=True)
    doc.close()
    print(f"wrote {out}: {stats['highlight']} highlighted, {stats['line']} by line position, {stats['note']} as margin notes")
    if stats["note"]:
        print("margin notes = text not found and no line given; check `original`/`line` of those items")


# ---------------------------------------------------------------- compare (reconstruction fidelity)

def cmd_compare(a):
    import difflib
    da, db = Doc(a.a), Doc(a.b)

    def words(doc):
        out = []
        for bi, b in enumerate(doc.blocks):
            for m in re.finditer(r"\S+", b["text"]):
                out.append((re.sub(r"[^\w%-]", "", norm(m.group(0))).lower(), bi, m.start()))
        return [w for w in out if w[0]]

    wa, wb = words(da), words(db)
    sm = difflib.SequenceMatcher(None, [w[0] for w in wa], [w[0] for w in wb], autojunk=False)
    diffs = [op for op in sm.get_opcodes() if op[0] != "equal"]
    print(f"word similarity {sm.ratio():.3f}  ({len(wa)} vs {len(wb)} words, {len(diffs)} differing spans)")
    shown = 0
    for tag, i1, i2, j1, j2 in diffs:
        if shown >= a.max:
            print(f"… {len(diffs) - shown} more")
            break
        _, bi, off = wa[min(i1, len(wa) - 1)] if wa else ("", 0, 0)
        p, ln = da.loc(bi, off)
        left = " ".join(w[0] for w in wa[i1:i2])[:80]
        right = " ".join(w[0] for w in wb[j1:j2])[:80]
        print(f"  {tag:7s} near p{p} L{ln}: [{left}] -> [{right}]")
        shown += 1


# ---------------------------------------------------------------- workspace / loop

def rdir(ws, n):
    return Path(ws) / "rounds" / f"r{n:02d}"


def rounds_of(ws):
    out = []
    for p in sorted((Path(ws) / "rounds").glob("r[0-9][0-9]")):
        out.append(int(p.name[1:]))
    return out


def load_state(ws):
    p = Path(ws) / "state.json"
    if not p.exists():
        sys.exit(f"no workspace at {ws} (run init first)")
    return read_json(p)


def cmd_init(a):
    ws = Path(a.ws)
    pdf = Path(a.pdf).resolve()
    if not pdf.exists():
        sys.exit(f"not found: {pdf}")
    state_p = ws / "state.json"
    if state_p.exists() and not a.force:
        st = read_json(state_p)
        print(f"workspace exists (mode={st['mode']}, rounds={rounds_of(ws)}); resuming. Use --force to start over.")
        return
    for sub in ("original", "rounds/r01", "work"):
        (ws / sub).mkdir(parents=True, exist_ok=True)
    shutil.copy2(pdf, ws / "original" / pdf.name)
    shutil.copy2(pdf, rdir(ws, 1) / "paper.pdf")
    tmpl = SKILL_DIR / "assets" / "style_sheet_template.md"
    if tmpl.exists() and (a.force or not (ws / "style_sheet.md").exists()):
        shutil.copy2(tmpl, ws / "style_sheet.md")
    if a.mode == "loop":
        (ws / "src").mkdir(exist_ok=True)
        aq = ws / "author_queries.md"
        if a.force or not aq.exists():
            aq.write_text("# 著者への確認事項\n\n校正者だけでは決められない点。本文は変更していない。\n\n"
                          "| ID | 位置 | 質問 | 校正者の案 |\n|---|---|---|---|\n", encoding="utf-8")
    state = {"version": 1, "mode": a.mode, "max_rounds": 1 if a.mode == "once" else a.max_rounds,
             "pdf": str(pdf), "stem": pdf.stem, "journal": a.journal or "", "created": now(),
             "finished": None, "finish_reason": None}
    write_json(state_p, state)
    print(f"workspace: {ws.resolve()}  mode={a.mode}  max_rounds={state['max_rounds']}")
    cands = []
    for pat in ("*.tex", "*.zip", "*.tar.gz", "*.tgz", "*.tar", "*.docx", "*.bib"):
        cands += sorted(pdf.parent.glob(pat))
    cands += [d for d in sorted(pdf.parent.iterdir()) if d.is_dir() and d.resolve() != ws.resolve() and any(d.glob("*.tex"))]
    if cands:
        print("source candidates next to the PDF:")
        for c in cands[:20]:
            print(f"  {c}")
    elif a.mode == "loop":
        print("no LaTeX source found next to the PDF (ask the user, or reconstruct from the PDF)")


def round_summary(ws, n):
    d = rdir(ws, n)
    row = {"round": n, "pdf": (d / "paper.pdf").exists(), "proofread": False}
    cp = d / "corrections.json"
    if cp.exists():
        data = read_json(cp)
        items = data.get("items", [])
        row.update(proofread=True, **counts(items))
        row["must"] = sum(row[s] for s in COUNTED)
        row["introduced"] = sum(1 for it in items if it.get("introduced"))
        pc = Counter(p.get("status") for p in data.get("previous_check", []) or [])
        row["prev"] = dict(pc)
    lp = d / "revision_log.json"
    if lp.exists():
        log = read_json(lp).get("items", {})
        row["actions"] = dict(Counter(v.get("action") for v in log.values()))
    return row


def progress_table(ws):
    rows = [round_summary(ws, n) for n in rounds_of(ws)]
    L = ["| ラウンド | 誤り | 明確さ | 文体 | 著者確認 | 判定対象（誤り+明確さ） | 前回の解決/残存 | 改訂で混入 | 反映（適用/見送り/確認） |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if not r["proofread"]:
            L.append(f"| r{r['round']:02d} | – | – | – | – | （未校正） | | | |")
            continue
        prev = r.get("prev") or {}
        pv = f"{prev.get('resolved', 0)}/{prev.get('remaining', 0) + prev.get('changed', 0)}" if prev else "–"
        act = r.get("actions")
        av = f"{act.get('applied', 0)}/{act.get('skipped', 0)}/{act.get('query', 0)}" if act else "–"
        L.append(f"| r{r['round']:02d} | {r['error']} | {r['clarity']} | {r['style']} | {r['query']} | **{r['must']}** | {pv} | {r['introduced']} | {av} |")
    return rows, "\n".join(L)


def decide(ws, state, rows):
    if not rows:
        return "PROOFREAD r01", None
    with_pdf = [r for r in rows if r["pdf"]]
    last = with_pdf[-1]
    n = last["round"]
    if not last["proofread"]:
        return f"PROOFREAD r{n:02d}", None
    if state["mode"] == "once":
        return "STOP", "1回校正モード"
    if last["must"] == 0:
        return "STOP", f"収束（r{n:02d} で誤り・明確さの指摘が 0）"
    if n >= state["max_rounds"]:
        return "STOP", f"上限ラウンド数 {state['max_rounds']} に到達"
    prev = [r for r in with_pdf if r["round"] < n and r["proofread"]]
    if prev and last["must"] >= prev[-1]["must"]:
        return "STOP", f"改善なし（判定対象 {prev[-1]['must']} → {last['must']}）。これ以上回しても書き換えが往復するだけになりやすい"
    return f"REVISE r{n:02d} -> r{n + 1:02d}", None


def cmd_status(a):
    state = load_state(a.ws)
    rows, table = progress_table(a.ws)
    (Path(a.ws) / "progress.md").write_text("# 校正の推移\n\n" + table + "\n", encoding="utf-8")
    print(f"mode: {state['mode']}  max_rounds: {state['max_rounds']}  journal: {state['journal'] or '-'}")
    print(table)
    nxt, reason = decide(a.ws, state, rows)
    if state.get("finished"):
        print(f"finished: {state['finished']} ({state.get('finish_reason')})")
    print(f"NEXT: {nxt}" + (f" — {reason}" if reason else ""))


def cmd_verify(a):
    n = a.round
    corr = read_json(rdir(a.ws, n) / "corrections.json")
    log_p = rdir(a.ws, n) / "revision_log.json"
    if not log_p.exists():
        sys.exit(f"missing {log_p}")
    log = read_json(log_p).get("items", {})
    new_txt = rdir(a.ws, n + 1) / "paper.txt"
    old_txt = rdir(a.ws, n) / "paper.txt"
    if not new_txt.exists():
        sys.exit(f"missing {new_txt} (extract the rebuilt PDF first)")
    new_doc = Doc(new_txt)
    new = TextIndex(new_doc)
    old = TextIndex(Doc(old_txt)) if old_txt.exists() else None
    prose = Scanner(new_doc).prose  # the reference list keeps its original spellings
    missing_log, not_found, still, ok, unchecked, manual = [], [], [], 0, [], 0
    for it in corr.get("items", []):
        iid = it.get("id")
        entry = log.get(iid)
        if entry is None:
            missing_log.append(iid)
            continue
        if entry.get("action") != "applied":
            continue
        if entry.get("verified_manually"):
            manual += 1
            continue
        if it.get("scope") == "global":
            pairs = [p for p in it.get("replace") or [] if len(p) == 2 and p[0] and p[0] not in p[1]]
            if not pairs:
                unchecked.append(iid)
                continue
            bad = []
            for old_form, _ in pairs:
                pat = re.compile(r"(?<![A-Za-z])" + re.escape(old_form))
                hits = [new_doc.loc(bi, m.start()) for bi in prose for m in pat.finditer(new_doc.blocks[bi]["text"])]
                if hits:
                    bad.append(f"'{old_form}' at " + ", ".join(f"p{p} L{l}" for p, l in hits[:8]))
            if bad:
                still.append(f"{iid}（全体）: 置き換え前の形が残っている: " + "; ".join(bad))
            else:
                ok += 1
            continue
        sug, orig = it.get("suggestion", ""), it.get("original", "")
        exact = fine_only(orig, sug)  # case/spacing/dash/quote-only fixes need exact comparison
        present = new.has_exact if exact else (lambda s: new.find(s) is not None)
        if sug and not present(sug):
            not_found.append(f"{iid}: 修正後の文字列が新しいPDFに無い: \"{sug[:70]}\"")
            continue
        contained = light(orig) in light(sug) if exact else norm(orig) in norm(sug)
        if orig and not contained and present(orig) and (old is None or old.count(orig) <= 1):
            still.append(f"{iid}: 修正前の文字列がまだある: \"{orig[:70]}\"")
            continue
        ok += 1
    print(f"verify r{n:02d} -> r{n + 1:02d}: OK {ok}, not found {len(not_found)}, original still present {len(still)}, "
          f"verified manually {manual}, missing in revision_log {len(missing_log)}")
    for s in not_found + still:
        print("  " + s)
    if unchecked:
        print(f"  global items without `replace` (check by hand): {', '.join(unchecked)}")
    if missing_log:
        print("  revision_log に記録がない ID: " + ", ".join(missing_log[:30]))
    print("If a flagged item is in fact correct in the PDF (an extraction quirk), confirm it on the page image and set "
          "\"verified_manually\": true on its revision_log entry.")
    sys.exit(1 if (not_found or still or missing_log) else 0)


def cmd_finalize(a):
    ws = Path(a.ws)
    state = load_state(ws)
    rows, table = progress_table(ws)
    nxt, reason = decide(ws, state, rows)
    if state.get("finished"):
        print(f"note: finalize already ran at {state['finished']}; refreshing the deliverables")
    if state["mode"] == "loop":
        (ws / "progress.md").write_text("# 校正の推移\n\n" + table + "\n", encoding="utf-8")
    stem = state["stem"]
    done = [r for r in rows if r["proofread"]]
    if not done:
        sys.exit("nothing proofread yet")
    last = done[-1]["round"]
    copies = []

    def cp(src, dst):
        if Path(src).exists():
            shutil.copy2(src, dst)
            copies.append(Path(dst))

    cp(rdir(ws, 1) / "annotated.pdf", ws / (f"{stem}_proofread.pdf" if state["mode"] == "once" else f"{stem}_proofread_r01.pdf"))
    cp(rdir(ws, 1) / "report.md", ws / ("report.md" if state["mode"] == "once" else "report_r01.md"))
    if state["mode"] == "loop" and last >= 2:
        cp(rdir(ws, last) / "paper.pdf", ws / f"{stem}_corrected.pdf")
        cp(rdir(ws, last) / "report.md", ws / "report_final.md")
        if done[-1]["must"] + done[-1]["style"] + done[-1]["query"] > 0:
            cp(rdir(ws, last) / "annotated.pdf", ws / f"{stem}_corrected_remaining.pdf")
    # changelog: every correction that was applied, round by round
    L = ["# 変更履歴（適用した修正）", ""]
    total = 0
    for n in rounds_of(ws):
        lp, cpth = rdir(ws, n) / "revision_log.json", rdir(ws, n) / "corrections.json"
        if not (lp.exists() and cpth.exists()):
            continue
        log = read_json(lp).get("items", {})
        items = {it.get("id"): it for it in read_json(cpth).get("items", [])}
        applied = [(iid, items[iid]) for iid, v in log.items() if v.get("action") == "applied" and iid in items]
        skipped = [(iid, v, items.get(iid, {})) for iid, v in log.items() if v.get("action") == "skipped"]
        total += len(applied)
        L += [f"## r{n:02d} → r{n + 1:02d}（適用 {len(applied)} / 見送り {len(skipped)}）", "",
              "| ID | 位置 | 区分 | 修正前 | 修正後 |", "|---|---|---|---|---|"]
        for iid, it in sorted(applied, key=lambda x: (x[1].get("page") or 0, x[1].get("line") or 0)):
            glob = it.get("scope") == "global"
            where = f"p.{it.get('page')}" + (f" L{it['line']}" if it.get("line") else "") + (" 🌐" if glob else "")
            after = it.get("suggestion", "")
            if glob and not after:
                after = "（全体に適用）" + "、".join(f"{o} → {n_}" for o, n_ in it.get("replace") or [])
            L.append(f"| {iid} | {where} | {it.get('category', '')} | {md(it.get('original') or it.get('pattern', ''))} | {md(after)} |")
        if skipped:
            L += ["", "見送り:", ""] + [f"- {iid}（{it.get('category', '')}）: {v.get('reason', '')}" for iid, v, it in skipped]
        L.append("")
    if total:
        (ws / "changelog.md").write_text("\n".join(L) + "\n", encoding="utf-8")
        copies.append(ws / "changelog.md")
    # the final round has no reviser, so its queries would otherwise never reach author_queries.md
    aq = ws / "author_queries.md"
    if state["mode"] == "loop" and aq.exists() and (rdir(ws, last) / "corrections.json").exists():
        text = aq.read_text(encoding="utf-8")
        added = 0
        for it in read_json(rdir(ws, last) / "corrections.json").get("items", []):
            if it.get("severity") == "query" and it.get("id") and it["id"] not in text:
                where = f"p.{it.get('page')}" + (f" L{it['line']}" if it.get("line") else "") + f"（r{last:02d}）"
                text += f"| {it['id']} | {where} | {md(it.get('reason', ''))} | {md(it.get('suggestion', ''))} |\n"
                added += 1
        if added:
            aq.write_text(text, encoding="utf-8")
            print(f"author_queries.md: added {added} query(ies) from the final round r{last:02d}")
    state["finished"] = now()
    state["finish_reason"] = a.reason or (reason if nxt == "STOP" else f"途中で終了（次の工程: {nxt}）")
    write_json(ws / "state.json", state)
    print(table)
    print(f"finished: {state['finish_reason']}")
    for c in copies:
        print(f"  {c}")


# ---------------------------------------------------------------- main

def main():
    out_utf8()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init"); s.add_argument("ws"); s.add_argument("--pdf", required=True)
    s.add_argument("--mode", choices=("once", "loop"), required=True); s.add_argument("--max-rounds", type=int, default=5)
    s.add_argument("--journal"); s.add_argument("--force", action="store_true"); s.set_defaults(fn=cmd_init)
    s = sub.add_parser("extract"); s.add_argument("pdf"); s.add_argument("-o", required=True); s.set_defaults(fn=cmd_extract)
    s = sub.add_parser("scan"); s.add_argument("txt"); s.add_argument("-o", required=True); s.set_defaults(fn=cmd_scan)
    s = sub.add_parser("validate"); s.add_argument("corr"); s.add_argument("--text"); s.set_defaults(fn=cmd_validate)
    s = sub.add_parser("merge"); s.add_argument("out"); s.add_argument("parts", nargs="+"); s.add_argument("--round", type=int)
    s.set_defaults(fn=cmd_merge)
    s = sub.add_parser("report"); s.add_argument("corr"); s.add_argument("-o"); s.add_argument("--text"); s.set_defaults(fn=cmd_report)
    s = sub.add_parser("annotate"); s.add_argument("pdf"); s.add_argument("corr"); s.add_argument("-o", required=True)
    s.add_argument("--lines"); s.add_argument("--only", help="comma-separated severities"); s.set_defaults(fn=cmd_annotate)
    s = sub.add_parser("verify"); s.add_argument("ws"); s.add_argument("--round", type=int, required=True); s.set_defaults(fn=cmd_verify)
    s = sub.add_parser("compare"); s.add_argument("a"); s.add_argument("b"); s.add_argument("--max", type=int, default=40)
    s.set_defaults(fn=cmd_compare)
    s = sub.add_parser("status"); s.add_argument("ws"); s.set_defaults(fn=cmd_status)
    s = sub.add_parser("finalize"); s.add_argument("ws"); s.add_argument("--reason", help="why the loop ended, if not by the stop rule")
    s.set_defaults(fn=cmd_finalize)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
