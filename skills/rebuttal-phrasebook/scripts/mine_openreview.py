"""Mine Opening Statements / General Responses from public OpenReview notes.

Input: the parquet files of the Hugging Face dataset `Jasonpicky/openreview_raw`
(a mirror of `sumukshashidhar-archive/openreview_raw`, ODC-By, OpenReview public notes).
The data is NOT shipped with the skill. Download it only with the user's permission:

    python mine_openreview.py files                    # list the files and their sizes
    python mine_openreview.py download <data_dir>      # ~0.9 GB, 6 parquet files
    python mine_openreview.py analyze <data_dir> -o <out_dir>
    python mine_openreview.py search  <data_dir> "<phrase>" [--section opening|closing|reply] [-n 5]

`analyze` writes:
    stats.json          move / phrase / structure statistics with outcome associations
    stats.md            the same, human readable
    doc_features.pkl    per-document features for re-slicing (e.g. by venue)
    samples.jsonl       short opening / closing excerpts per move (for the skill author, not for shipping)

Outcome signals (associations only, never causal):
    accept   ICLR 2019-2024 decisions (all submissions public, so accepted and rejected are comparable)
    raised   a reviewer of the thread later says they raised / increased / updated their score
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import math
import os
import re
import sys
import urllib.request

HF_DATASET = "Jasonpicky/openreview_raw"
HF_FILES = [f"data/train-0000{i}-of-00006.parquet" for i in range(6)]
COLUMNS = ["forum_id", "note_id", "note_type", "note_created", "note_replyto",
           "note_signatures", "venue", "year", "note_text"]

# ---------------------------------------------------------------- loading

def cmd_files(_args):
    url = f"https://huggingface.co/api/datasets/{HF_DATASET}?blobs=true"
    with urllib.request.urlopen(url, timeout=60) as r:
        info = json.load(r)
    total = 0
    for s in info.get("siblings", []):
        if s["rfilename"] in HF_FILES:
            total += s.get("size") or 0
            print(f"{s['rfilename']}\t{(s.get('size') or 0) / 1e6:.1f} MB")
    print(f"total\t{total / 1e6:.1f} MB\tlicense: {(info.get('cardData') or {}).get('license')}")


def cmd_download(args):
    os.makedirs(args.data_dir, exist_ok=True)
    for f in HF_FILES:
        dst = os.path.join(args.data_dir, os.path.basename(f))
        if os.path.exists(dst) and os.path.getsize(dst) > 0:
            print("skip", dst)
            continue
        url = f"https://huggingface.co/datasets/{HF_DATASET}/resolve/main/{f}"
        print("get", url)
        urllib.request.urlretrieve(url, dst + ".part")
        os.replace(dst + ".part", dst)


def load_notes(data_dir):
    import pandas as pd
    import pyarrow.parquet as pq
    cache = os.path.join(data_dir, "notes.pkl")
    if os.path.exists(cache):
        return pd.read_pickle(cache)
    files = sorted(glob.glob(os.path.join(data_dir, "*.parquet")))
    if not files:
        sys.exit(f"no parquet files in {data_dir}")
    df = pd.concat([pq.read_table(f, columns=COLUMNS).to_pandas() for f in files], ignore_index=True)
    df.to_pickle(cache)
    return df

# ---------------------------------------------------------------- text helpers

KEY_RE = re.compile(r"(?m)^(title|comment|rebuttal|pdf|withdrawal_confirmation|zip_file|answer|edit): ?")
SALUTATION_RE = re.compile(
    r"^(dear|to|hi|hello)\b[^.!?\n]{0,80}(reviewers?|acs?|area chairs?|sacs?|pcs?|chairs?|meta-?reviewers?|all|everyone)\b[^\n]{0,40}$",
    re.I)
SIGNOFF_RE = re.compile(r"^(best|kind|warm(est)?|many thanks|thanks again|sincerely|regards|yours)\b[^\n]{0,40}$|^(the )?authors?\b[^\n]{0,30}$|^paper ?\d+ authors?$", re.I)


def split_fields(text):
    """note_text is 'key: value' lines; return dict key -> value (value may span lines)."""
    text = text or ""
    out, spans = {}, list(KEY_RE.finditer(text))
    for i, m in enumerate(spans):
        end = spans[i + 1].start() if i + 1 < len(spans) else len(text)
        out.setdefault(m.group(1), text[m.end():end].strip())
    if not spans:
        out["comment"] = text.strip()
    return out


def body_of(text):
    f = split_fields(text)
    return f.get("comment") or f.get("rebuttal") or f.get("answer") or ""


def clean_md(s):
    s = re.sub(r"```.*?```", " ", s, flags=re.S)
    s = re.sub(r"\$\$.*?\$\$", " <math> ", s, flags=re.S)
    s = re.sub(r"\$[^$\n]{1,200}\$", " <math> ", s)
    s = re.sub(r"(?m)^\s*\|.*\|\s*$", " ", s)          # tables
    s = re.sub(r"https?://\S+", " <url> ", s)
    s = re.sub(r"[*_#>`~]+", " ", s)
    s = re.sub(r"(?m)^\s*(\d+[.)]|[-•+])\s+", "\n", s)  # list markers -> line break
    return s


def sentences(body):
    """Split into sentence-like units; salutation / sign-off lines are tagged."""
    out = []
    for line in clean_md(body).split("\n"):
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        if SALUTATION_RE.match(line):
            out.append(("salutation", line))
            continue
        if SIGNOFF_RE.match(line):
            out.append(("signoff", line))
            continue
        for s in re.split(r"(?<=[.!?])\s+(?=[A-Z(\"'“])", line):
            s = s.strip()
            if len(s) < 3:
                continue
            out.append(("cite" if CITE_RE.search(s) or not re.search(r"[a-z]{3,}", s) else "text", s))
    return out

CITE_RE = re.compile(r"\barxiv\b|\bet al\.|\bproceedings\b|\badvances in neural\b|\b(international )?conference on\b|\bpp\. ?\d|\bvol\. ?\d|\bdoi\b|\bjournal of\b|^\s*\[\d+\]", re.I)


def normalize(s):
    s = s.lower()
    s = re.sub(r"[“”\"«»].{0,120}?[“”\"«»]", " <q> ", s)
    s = re.sub(r"\breviewers?\s*#?\s*[a-z0-9]{4}\b(?<!\ball)", "reviewer <id>", s)
    s = re.sub(r"\b(reviewer|r)\s*#?\s*\d\b", "reviewer <id>", s)
    s = re.sub(r"\[[\d,\s\-–]+\]", " <cite> ", s)
    s = re.sub(r"\d+(\.\d+)?%?", "<num>", s)
    s = re.sub(r"[^a-z<>'\- ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def tokens(s):
    return normalize(s).split()

# ---------------------------------------------------------------- moves

MOVES = collections.OrderedDict([
    ("gratitude", r"\b(thank|thanks|grateful|gratitude|appreciate|appreciation)\b"),
    ("strengths_ack", r"\b(encouraged|glad|pleased|delighted|happy|heartened)\b.{0,40}\b(see|hear|note|know|that|by)\b"
                      r"|\breviewers?\b.{0,40}\b(recogni[sz]ed|recogni[sz]e|acknowledged|acknowledge|appreciated|praised|commended|highlighted)\b"
                      r"|\breviewers?\b.{0,30}\b(found|noted|agree[ds]?|consider(ed)?|think|thought)\b.{0,60}\b(novel|well[- ]written|clear|interesting|important|significant|strong|solid|extensive|comprehensive|thorough|sound|effective|promising|insightful|original|timely|valuable|rigorous|simple|elegant|easy to follow|convincing|impressive|useful|practical|good)\b"
                      r"|\b(positive|encouraging|favorable|kind) (feedback|comments|remarks|words|assessment)"),
    ("revision_summary", r"\b(revised|updated|new|modified) (version|manuscript|paper|draft|pdf|submission)\b"
                         r"|\b(uploaded|we have revised|we revised|we have updated|we updated)\b"
                         r"|\bhighlighted in\b|\bin (blue|red|green|orange|purple|magenta|teal)\b|\bmarked in\b"),
    ("change_list", r"\b(main|key|major|following|summary of( the)?) (changes|revisions|modifications|updates)\b"
                    r"|\bwe (have )?made the following\b|\bchanges (include|are)\b"),
    ("new_experiments", r"\b(additional|new|more|extra|further|extensive|comprehensive) (experiments?|experimental results?|results?|evaluations?|ablations?|ablation studies|analys[ie]s|baselines?|comparisons?|benchmarks?|datasets?|empirical)\b"
                        r"|\bwe (have )?(conducted|ran|performed|run|carried out)\b"),
    ("pdf_pointer", r"\b(attached|one-page|1-page|rebuttal|uploaded|global) pdf\b|\bthe pdf\b|\bin the pdf\b"),
    ("common_concerns", r"\b(several|multiple|many|some|most|both|two|three|all|other) (of the )?reviewers\b.{0,40}\b(raised|asked|pointed|mentioned|questioned|concern|suggested|noted|requested|expressed|shared)"
                        r"|\b(common|shared|recurring|frequently|repeated)\w* (concerns?|questions?|points?|issues?|comments?|asked|raised)\b|\braised by (several|multiple|many|some|most|both|two|three|all)\b"),
    ("contribution_restate", r"\bwe (would like|want|wish|like) to (re-?)?(emphasi[sz]e|clarify|highlight|reiterate|stress|summari[sz]e|restate|recap|point out)\b"
                             r"|\b(main|key|core|primary|our) contributions?\b|\bthe novelty of\b"),
    ("clarify_misunderstanding", r"\b(misunderstand|misunderstood|misconception|misinterpret|confusion|confusing|unclear)\w*\b|\bclarif(y|ication)\b"),
    ("pointer_individual", r"\b(individual|separate|respective|point-by-point|detailed)\b.{0,20}\b(responses?|replies|rebuttals?|answers?)\b|\bbelow each review\b|\bto each reviewer\b"),
    ("closing_hope", r"\bwe (sincerely |truly |really |do |genuinely )?hope\b|\bhopefully\b"),
    ("further_questions", r"\b(further|additional|any other|remaining|more|follow-up|outstanding) (questions?|concerns?|comments?|feedback|discussions?|clarifications?|suggestions?)\b"
                          r"|\bplease (let us know|feel free|do not hesitate|don't hesitate)\b|\bhappy to (answer|address|discuss|clarify|provide|engage)\b|\blook forward to\b"),
    ("score_request", r"\b(rais\w*|increas\w*|reconsider\w*|re-?evaluat\w*|re-?assess\w*|updat\w*|adjust\w*|revisit\w*)\b.{0,30}"
                      r"\b((your|their|the reviewers?'?s?|the) (score|rating|recommendation)s?|(your|their) (evaluation|assessment)s?)\b"),
    ("reminder", r"\b(gentle|friendly|kind) reminder\b|\breminder\b|\b(discussion|rebuttal|author-reviewer) (period|phase|stage|window)\b.{0,40}\b(end|clos|approach|over|conclud|deadline)"
                 r"|\bdeadline (is )?(approaching|near)\b|\bmay we (kindly )?ask\b|\bhave (we|our responses?) (addressed|resolved)\b"),
])
MOVES_RE = {k: re.compile(v, re.I) for k, v in MOVES.items()}


def moves_of(sent):
    return [k for k, r in MOVES_RE.items() if r.search(sent)]

# ---------------------------------------------------------------- titles / classes

def note_title(text):
    m = re.search(r"(?m)^title: ?(.*)$", text or "")
    return (m.group(1).strip() if m else "").lower()

GR_TITLE = re.compile(r"general|global|common|overall|all reviewers|to (the )?reviewers|reviewers and|response to reviewers|author rebuttal|rebuttal by authors|^rebuttal$|meta[- ]?response|joint response|shared response|^author response", re.I)
REV_TITLE = re.compile(r"revis|change|update|manuscript|new version|paper version|camera", re.I)
REMIND_TITLE = re.compile(r"remind|follow[- ]?up|discussion (period|deadline)|deadline|kind request|request for (feedback|response|discussion)|awaiting|looking forward|gentle", re.I)
AC_TITLE = re.compile(r"\b(ac|acs|area chair|area chairs|meta[- ]?reviewer|sac|pc)s?\b|summary of (the )?(discussion|rebuttal|responses|our responses)|rebuttal summary|discussion summary|final (summary|remarks|comment)", re.I)
THANKS_TITLE = re.compile(r"^thank|^thanks|grateful|appreciation", re.I)


def classify_top(title, body, words):
    if re.search(r"withdraw", title) or re.search(r"\b(decided|decide|choose|chosen) to withdraw\b|\bwithdraw (our|the|this) (paper|submission)\b", body[:600], re.I):
        return "withdrawal"
    if REMIND_TITLE.search(title):
        return "reminder"
    if AC_TITLE.search(title) and not re.search(r"general|global|common", title):
        return "ac_summary"
    if GR_TITLE.search(title):
        return "general"
    if REV_TITLE.search(title):
        return "revision"
    if THANKS_TITLE.search(title):
        return "thanks"
    low = body.lower()[:600]
    if words < 120 and MOVES_RE["reminder"].search(low):
        return "reminder"
    if words < 60 and MOVES_RE["gratitude"].search(low):
        return "thanks"
    if words >= 120:
        return "general"
    return "other"

# ---------------------------------------------------------------- analysis

RAISE_RE = re.compile(r"\b(rais|increas|bump|improv|upgrad|updat|adjust|chang|mov)\w*\s+(up\s+)?(my\s+|the\s+|our\s+)?(overall\s+)?(score|rating|recommendation|assessment)\b"
                      r"|\b(score|rating)\s+(has been|is|was|will be)\s+(raised|increased|updated|bumped|changed)\b"
                      r"|\b(raise|increase|bump)\w*\s+(it|this)\s+(to|from)\b", re.I)
NEG_RE = re.compile(r"\b(not|n't|no|cannot|won't|unable|keep|maintain|retain|stay|remain)\b[^.]{0,30}$", re.I)


def raised(text):
    for m in RAISE_RE.finditer(text or ""):
        pre = text[max(0, m.start() - 40):m.start()]
        if not NEG_RE.search(pre):
            return True
    return False


def ngrams(toks, nmin, nmax):
    out = set()
    for n in range(nmin, nmax + 1):
        for i in range(len(toks) - n + 1):
            g = toks[i:i + n]
            if g[0] in STOP_EDGE or g[-1] in STOP_EDGE:
                continue
            out.add(" ".join(g))
    return out

STOP_EDGE = {"and", "or", "the", "a", "an", "of", "to", "in", "for", "on", "with", "as", "that", "which", "is", "are", "be", "by", "at", "from"}


def rate(xs):
    xs = [x for x in xs if x is not None]
    return (sum(xs) / len(xs), len(xs)) if xs else (None, 0)


def wilson(p, n, z=1.96):
    if not n:
        return (None, None)
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(c - h, 3), round(c + h, 3))


def cmd_analyze(args):
    import pandas as pd
    df = load_notes(args.data_dir)
    df["sig"] = df.note_signatures.apply(lambda s: " ".join(s) if s is not None else "")
    df["role"] = "other"
    df.loc[df.sig.str.contains(r"/Authors\b"), "role"] = "author"
    df.loc[df.sig.str.contains(r"Reviewer_|AnonReviewer"), "role"] = "reviewer"
    df["created"] = pd.to_numeric(df.note_created, errors="coerce")
    df["family"] = df.venue.str.extract(r"^(ICLR|NeurIPS|EMNLP|robot-learning|MIDL|colmweb|ICML|ACM)", expand=False).fillna("other")
    df["vy"] = df.family + " " + df.year.astype(str)

    # forum-level decisions (ICLR 2019-2024 have public decisions for all submissions)
    dec = df[df.note_type == "decision"].copy()
    dec["d"] = dec.note_text.str.extract(r"(?m)^decision:\s*([^\n]+)", expand=False)
    dec = dec.dropna(subset=["d"])
    dec["accept"] = dec.d.str.contains("accept", case=False)
    accept = dict(zip(dec.forum_id, dec.accept))
    iclr_forums = set(df[(df.family == "ICLR") & df.year.astype(str).isin([str(y) for y in range(2019, 2025)])].forum_id)

    # reviewer raise signals per (forum, reviewer signature)
    rv = df[(df.role == "reviewer") & df.note_type.isin(["official_comment", "comment"])]
    raised_by = set()
    for fid, sig, txt in zip(rv.forum_id, rv.sig, rv.note_text):
        if raised(body_of(txt)):
            raised_by.add((fid, sig.split()[0]))
    forum_raised = {fid for fid, _ in raised_by}
    reviews = df[df.note_type.isin(["official_review", "review"]) & (df.role == "reviewer")]
    review_owner = dict(zip(reviews.note_id, zip(reviews.forum_id, reviews.sig.str.split().str[0])))
    forums_with_reviews = set(reviews.forum_id)

    # ---------------- top-level author notes
    au = df[df.role == "author"].copy()
    top = au[au.note_replyto == au.forum_id].copy()
    top["title"] = top.note_text.apply(note_title)
    top["body"] = top.note_text.apply(body_of)
    top["words"] = top.body.str.split().str.len().fillna(0).astype(int)
    top["cls"] = [classify_top(t, b, w) for t, b, w in zip(top.title, top.body, top.words)]

    report = {"source": f"huggingface.co/datasets/{HF_DATASET} (ODC-By; original content: OpenReview)",
              "n_notes": int(len(df)), "n_forums": int(df.forum_id.nunique())}
    report["top_level_classes"] = top.cls.value_counts().to_dict()
    report["top_level_titles"] = top[top.cls == "general"].title.replace("", "(untitled)").value_counts().head(40).to_dict()

    # earliest general response per forum (fallback: revision note)
    gen = top[top.cls.isin(["general", "revision"])].sort_values("created")
    gen["prio"] = (gen.cls != "general").astype(int)
    first = gen.sort_values(["prio", "created"]).groupby("forum_id").head(1)
    # merge multi-part GRs posted together: concatenate same-forum general notes within 1 day of the first
    parts = gen[gen.cls == "general"].groupby("forum_id")
    merged = {}
    for fid, g in parts:
        t0 = g.created.min()
        g = g[g.created <= t0 + 86400_000].sort_values("created")
        merged[fid] = "\n\n".join(g.body)
    first = first.assign(full=[merged.get(f, b) for f, b in zip(first.forum_id, first.body)])

    # coverage: who posts a general response?
    cov = {}
    for vy, g in df[df.forum_id.isin(forums_with_reviews)].groupby("vy"):
        fs = set(g.forum_id)
        if len(fs) < 300:
            continue
        has = fs & set(first.forum_id)
        row = {"forums": len(fs), "with_general_response": len(has), "share": round(len(has) / len(fs), 3)}
        acc_fs = [f for f in fs if f in accept and f in iclr_forums]
        if acc_fs:
            a_with = [accept[f] for f in acc_fs if f in has]
            a_without = [accept[f] for f in acc_fs if f not in has]
            row["accept_rate_with"] = round(rate(a_with)[0], 3) if a_with else None
            row["accept_rate_without"] = round(rate(a_without)[0], 3) if a_without else None
        cov[vy] = row
    report["coverage_by_venue_year"] = cov

    # ---------------- per-document features
    docs = []
    for r in first.itertuples():
        sents = sentences(r.full)
        txt = [s for k, s in sents if k == "text"]
        sal = [s for k, s in sents if k == "salutation"]
        d = {
            "forum": r.forum_id, "vy": r.vy, "family": r.family,
            "accept": accept.get(r.forum_id) if r.forum_id in iclr_forums else None,
            "raised": (r.forum_id in forum_raised) if r.forum_id in forums_with_reviews else None,
            "words": len(r.full.split()),
            "salutation": sal[0] if sal else "",
            "opening": txt[:3], "closing": txt[-3:] if len(txt) > 3 else [],
            "all": txt,
            "has_list": bool(re.search(r"(?m)^\s*(\d+[.)]|[-*•])\s+\S", r.full)),
            "has_headings": bool(re.search(r"(?m)^\s*(#{1,4} |\*\*[^*\n]{3,80}\*\*\s*:?\s*$)", r.full)),
            "has_table": bool(re.search(r"(?m)^\s*\|.*\|\s*$", r.full)),
            "color_highlight": bool(re.search(r"\b(highlighted|marked|colored|coloured) in\b|\bin (blue|red|green|orange|purple|magenta|teal)\b", r.full, re.I)),
            "cites_reviewer_ids": bool(re.search(r"\breviewers?\s*#?\s*[A-Za-z0-9]{4}\b|\bR\d\b", r.full)),
            "quotes_praise": bool(re.search(r"[\"“][^\"”]{2,60}[\"”]", " ".join(txt[:4]))),
            "numbered_concerns": bool(re.search(r"(?m)^\s*(\*\*)?\s*(\[?(G|GR|C|Q|CR|A|GQ|Common)\s*\d+\]?|Concern\s*\d+|Q\d+)\b", r.full)),
        }
        mlist = [moves_of(s) for s in txt]
        d["all_moves"] = mlist
        d["moves_open"] = sorted({m for ms in mlist[:3] for m in ms})
        d["moves_any"] = sorted({m for ms in mlist for m in ms})
        d["moves_close"] = sorted({m for ms in mlist[-3:] for m in ms}) if len(txt) > 3 else []
        seq = []
        for ms in mlist:
            for m in ms:
                if not seq or seq[-1] != m:
                    seq.append(m)
        d["move_seq"] = seq[:12]
        docs.append(d)
    report["n_general_responses"] = len(docs)

    def outcome_block(sel):
        a = [d["accept"] for d in sel]
        z = [d["raised"] for d in sel]
        pa, na = rate(a)
        pz, nz = rate(z)
        # raise rates differ a lot by venue (NeurIPS > ICLR), so also report them within venue family
        fam = {}
        for f in ("ICLR", "NeurIPS"):
            pf, nf = rate([d["raised"] for d in sel if d.get("family") == f])
            fam[f] = None if pf is None else round(pf, 3)
            fam[f + "_n"] = nf
        return {"n": len(sel),
                "accept_rate": None if pa is None else round(pa, 3), "accept_n": na, "accept_ci95": wilson(pa, na) if na else None,
                "raised_rate": None if pz is None else round(pz, 3), "raised_n": nz, "raised_by_family": fam}

    report["baseline"] = outcome_block(docs)
    report["baseline_by_family"] = {f: outcome_block([d for d in docs if d["family"] == f])
                                    for f in ["ICLR", "NeurIPS", "robot-learning", "EMNLP", "MIDL"]}

    # moves
    mv = {}
    for scope in ["moves_open", "moves_any", "moves_close"]:
        mv[scope] = {}
        for m in MOVES:
            w = [d for d in docs if m in d[scope]]
            wo = [d for d in docs if m not in d[scope]]
            mv[scope][m] = {"share": round(len(w) / max(1, len(docs)), 3),
                            "with": outcome_block(w), "without": outcome_block(wo)}
    report["moves"] = mv

    # common move orders (first 5 distinct)
    orders = collections.Counter(" > ".join([m for m in d["move_seq"] if m not in ("gratitude",)][:4]) for d in docs)
    report["move_orders_top"] = orders.most_common(25)

    # structure features
    feats = ["has_list", "has_headings", "has_table", "color_highlight", "cites_reviewer_ids", "quotes_praise", "numbered_concerns"]
    report["structure"] = {f: {"share": round(sum(d[f] for d in docs) / max(1, len(docs)), 3),
                               "with": outcome_block([d for d in docs if d[f]]),
                               "without": outcome_block([d for d in docs if not d[f]])} for f in feats}
    # length buckets
    buckets = [(0, 150), (150, 300), (300, 600), (600, 1200), (1200, 2500), (2500, 10 ** 9)]
    report["length"] = {f"{a}-{b if b < 10 ** 9 else 'inf'}": outcome_block([d for d in docs if a <= d["words"] < b]) for a, b in buckets}
    import statistics
    for lab, sel in [("accepted", [d for d in docs if d["accept"] is True]), ("rejected", [d for d in docs if d["accept"] is False])]:
        report.setdefault("length_median_words", {})[lab] = statistics.median([d["words"] for d in sel]) if sel else None

    # salutations
    sal = collections.Counter(normalize(d["salutation"]) for d in docs if d["salutation"])
    report["salutations_top"] = sal.most_common(25)
    report["salutation_share"] = round(sum(1 for d in docs if d["salutation"]) / max(1, len(docs)), 3)

    # ---------------- phrases (document frequency, >= min_df distinct forums)
    def phrase_table(section_docs, key, min_df):
        dfc = collections.Counter()
        holders = collections.defaultdict(list)
        for i, d in enumerate(section_docs):
            grams = set()
            for s in d[key]:
                grams |= ngrams(tokens(s), 3, 9)
            for g in grams:
                dfc[g] += 1
                holders[g].append(i)
        kept = [(g, c) for g, c in dfc.items() if c >= min_df]
        kept.sort(key=lambda x: (-x[1], -len(x[0])))
        # drop sub-grams that are explained by a longer gram with similar df
        final = []
        for g, c in kept:
            if any(g in h and c <= hc * 1.15 for h, hc in final):
                continue
            final.append((g, c))
        rows = []
        for g, c in final[: args.top]:
            sel = [section_docs[i] for i in holders[g]]
            ob = outcome_block(sel)
            rows.append({"phrase": g, "df": c, "share": round(c / max(1, len(section_docs)), 4), **ob})
        return rows

    report["phrases_opening"] = phrase_table(docs, "opening", args.min_df)
    report["phrases_closing"] = phrase_table([d for d in docs if d["closing"]], "closing", args.min_df)

    # phrases per move, over all sentences of the general responses (gratitude excluded to avoid
    # the 'we thank ...' n-grams dominating every move)
    report["phrases_by_move"] = {}
    for m in MOVES:
        mdocs = []
        for d in docs:
            ss = [s for s, ms in zip(d["all"], d["all_moves"]) if m in ms and (m == "gratitude" or "gratitude" not in ms)]
            if ss:
                mdocs.append({**d, "_m": ss})
        report["phrases_by_move"][m] = {"n_docs": len(mdocs),
                                        "rows": phrase_table(mdocs, "_m", max(15, args.min_df // 2))[:50]}

    # ---------------- per-reviewer first replies
    rep = au[au.note_replyto.isin(review_owner.keys())].sort_values("created").groupby("note_replyto").head(1)
    rdocs = []
    for r in rep.itertuples():
        fid, rsig = review_owner[r.note_replyto]
        txt = [s for k, s in sentences(body_of(r.note_text)) if k == "text"]
        if not txt:
            continue
        rdocs.append({"forum": fid, "vy": r.vy, "family": r.family,
                      "accept": accept.get(fid) if fid in iclr_forums else None,
                      "raised": (fid, rsig) in raised_by,
                      "opening": txt[:2], "closing": txt[-2:] if len(txt) > 2 else [],
                      "moves_open": sorted({m for s in txt[:2] for m in moves_of(s)}),
                      "moves_close": sorted({m for s in txt[-2:] for m in moves_of(s)}) if len(txt) > 2 else []})
    report["n_reviewer_replies"] = len(rdocs)
    report["reply_baseline"] = outcome_block(rdocs)
    report["reply_moves"] = {scope: {m: {"share": round(sum(m in d[scope] for d in rdocs) / max(1, len(rdocs)), 3),
                                         "with": outcome_block([d for d in rdocs if m in d[scope]]),
                                         "without": outcome_block([d for d in rdocs if m not in d[scope]])}
                                     for m in MOVES} for scope in ["moves_open", "moves_close"]}
    report["phrases_reply_opening"] = phrase_table(rdocs, "opening", args.min_df * 3)
    report["phrases_reply_closing"] = phrase_table([d for d in rdocs if d["closing"]], "closing", args.min_df * 3)

    # ---------------- thread-level follow-ups
    rc = df[(df.role == "reviewer") & df.note_type.isin(["official_comment", "comment"])]
    raise_notes = {nid for nid, txt in zip(rc.note_id, rc.note_text) if raised(body_of(txt))}
    after_raise = au[au.note_replyto.isin(raise_notes)]
    tdocs = [{"opening": [s for k, s in sentences(body_of(t)) if k == "text"][:2],
              "accept": accept.get(f) if f in iclr_forums else None, "raised": True}
             for f, t in zip(after_raise.forum_id, after_raise.note_text)]
    report["n_thanks_after_raise"] = len(tdocs)
    report["phrases_thanks_after_raise"] = phrase_table(tdocs, "opening", args.min_df)
    nudges = []
    for f, rep_to, t in zip(au.forum_id, au.note_replyto, au.note_text):
        if rep_to == f:
            continue
        b = body_of(t)
        if len(b.split()) > 200:
            continue
        ss = [s for k, s in sentences(b) if k == "text"][:3]
        if any("reminder" in moves_of(s) for s in ss):
            nudges.append({"opening": ss, "accept": accept.get(f) if f in iclr_forums else None,
                           "raised": None})
    report["n_reply_reminders"] = len(nudges)
    report["phrases_reply_reminder"] = phrase_table(nudges, "opening", args.min_df)

    # ---------------- follow-up notes (reminder / thanks / ac summary / withdrawal): phrases only
    for cls in ["reminder", "thanks", "ac_summary"]:
        sub = top[top.cls == cls]
        fdocs = [{"opening": [s for k, s in sentences(b) if k == "text"][:3],
                  "accept": accept.get(f) if f in iclr_forums else None,
                  "raised": (f in forum_raised) if f in forums_with_reviews else None}
                 for f, b in zip(sub.forum_id, sub.body)]
        report[f"phrases_{cls}"] = phrase_table(fdocs, "opening", max(10, args.min_df // 2))
        report[f"n_{cls}"] = len(fdocs)

    os.makedirs(args.out, exist_ok=True)
    import pickle
    keep = ("vy", "family", "accept", "raised", "words", "moves_open", "moves_any", "moves_close",
            "has_list", "has_headings", "has_table", "color_highlight", "cites_reviewer_ids", "quotes_praise", "numbered_concerns")
    with open(os.path.join(args.out, "doc_features.pkl"), "wb") as f:
        pickle.dump({"general": [{k: d[k] for k in keep} for d in docs],
                     "replies": [{k: d[k] for k in ("vy", "family", "accept", "raised", "moves_open", "moves_close")} for d in rdocs]}, f)
    with open(os.path.join(args.out, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1, default=str)
    write_md(report, os.path.join(args.out, "stats.md"))

    # samples for the skill author (short excerpts; NOT for shipping)
    import random
    random.seed(0)
    with open(os.path.join(args.out, "samples.jsonl"), "w", encoding="utf-8") as f:
        for m in MOVES:
            pool = [(d, s) for d in docs for s in d["opening"] + d["closing"] if m in moves_of(s)]
            for d, s in random.sample(pool, min(args.samples, len(pool))):
                f.write(json.dumps({"move": m, "vy": d["vy"], "accept": d["accept"], "raised": d["raised"], "s": s[:300]}, ensure_ascii=False) + "\n")
        pool = [d for d in docs if d["accept"] is not None]
        for d in random.sample(pool, min(60, len(pool))):
            f.write(json.dumps({"move": "_doc", "vy": d["vy"], "accept": d["accept"], "raised": d["raised"],
                                "seq": d["move_seq"], "s": " ".join(d["opening"])[:500]}, ensure_ascii=False) + "\n")
    print("wrote", args.out)


def fmt_ob(ob):
    a = "-" if ob["accept_rate"] is None else f"{ob['accept_rate']:.2f} (n={ob['accept_n']})"
    z = "-" if ob["raised_rate"] is None else f"{ob['raised_rate']:.2f}"
    fam = ob.get("raised_by_family") or {}
    if fam.get("ICLR") is not None or fam.get("NeurIPS") is not None:
        z += f" [ICLR {fam.get('ICLR')}, NeurIPS {fam.get('NeurIPS')}]"
    return a, z


def write_md(r, path):
    L = [f"# OpenReview general-response statistics", "", f"source: {r['source']}", "",
         f"notes {r['n_notes']:,} / forums {r['n_forums']:,} / general responses {r['n_general_responses']:,} / per-reviewer first replies {r['n_reviewer_replies']:,}", ""]
    b = r["baseline"]
    L += [f"baseline (docs with a general response): accept {b['accept_rate']} (n={b['accept_n']}), any-reviewer-raised {b['raised_rate']} (n={b['raised_n']})", ""]
    L += ["## coverage", "", "| venue-year | forums | with GR | share | accept w/ GR | accept w/o GR |", "|---|---|---|---|---|---|"]
    for k, v in sorted(r["coverage_by_venue_year"].items()):
        L.append(f"| {k} | {v['forums']} | {v['with_general_response']} | {v['share']} | {v.get('accept_rate_with', '-')} | {v.get('accept_rate_without', '-')} |")
    for scope in ["moves_open", "moves_any", "moves_close"]:
        L += ["", f"## {scope}", "", "| move | share | accept with | accept without | raised with | raised without |", "|---|---|---|---|---|---|"]
        for m, v in r["moves"][scope].items():
            aw, zw = fmt_ob(v["with"]); ao, zo = fmt_ob(v["without"])
            L.append(f"| {m} | {v['share']} | {aw} | {ao} | {zw} | {zo} |")
    L += ["", "## structure", "", "| feature | share | accept with | accept without | raised with | raised without |", "|---|---|---|---|---|---|"]
    for m, v in r["structure"].items():
        aw, zw = fmt_ob(v["with"]); ao, zo = fmt_ob(v["without"])
        L.append(f"| {m} | {v['share']} | {aw} | {ao} | {zw} | {zo} |")
    L += ["", "## length (words)", "", "| bucket | n | accept | raised |", "|---|---|---|---|"]
    for k, v in r["length"].items():
        a, z = fmt_ob(v)
        L.append(f"| {k} | {v['n']} | {a} | {z} |")
    L += ["", f"median words: {r['length_median_words']}", "", "## move orders (top)", ""]
    L += [f"- {c} : {o}" for o, c in r["move_orders_top"]]
    L += ["", f"## salutations (share {r['salutation_share']})", ""] + [f"- {c} : {s}" for s, c in r["salutations_top"]]
    tables = [(k, r.get(k, [])) for k in ["phrases_opening", "phrases_closing", "phrases_reply_opening", "phrases_reply_closing",
                                          "phrases_thanks_after_raise", "phrases_reply_reminder", "phrases_reminder", "phrases_thanks", "phrases_ac_summary"]]
    tables += [(f"move: {m} (docs {v['n_docs']})", v["rows"]) for m, v in r.get("phrases_by_move", {}).items()]
    for key, rows in tables:
        L += ["", f"## {key}", "", "| phrase | df | share | accept | raised |", "|---|---|---|---|---|"]
        for row in rows:
            a = "-" if row["accept_rate"] is None else f"{row['accept_rate']:.2f} ({row['accept_n']})"
            z = "-" if row["raised_rate"] is None else f"{row['raised_rate']:.2f}"
            L.append(f"| {row['phrase']} | {row['df']} | {row['share']} | {a} | {z} |")
    L += ["", "## reply moves (per-reviewer first replies)", "", "| scope | move | share | raised with | raised without |", "|---|---|---|---|---|"]
    for scope, mm in r["reply_moves"].items():
        for m, v in mm.items():
            L.append(f"| {scope} | {m} | {v['share']} | {fmt_ob(v['with'])[1]} | {fmt_ob(v['without'])[1]} |")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")

# ---------------------------------------------------------------- search

def cmd_search(args):
    df = load_notes(args.data_dir)
    df["sig"] = df.note_signatures.apply(lambda s: " ".join(s) if s is not None else "")
    au = df[df.sig.str.contains(r"/Authors\b")]
    if args.section == "reply":
        au = au[au.note_replyto != au.forum_id]
    else:
        au = au[au.note_replyto == au.forum_id]
    q = normalize(args.phrase)
    hits = 0
    for vy, txt in zip(au.venue, au.note_text):
        sents = [s for k, s in sentences(body_of(txt)) if k == "text"]
        part = sents[:3] if args.section in ("opening", "reply") else sents[-3:]
        for s in part:
            if q in normalize(s):
                print(f"[{vy}] {s[:240]}")
                hits += 1
                break
        if hits >= args.n:
            break
    print(f"-- {hits} shown")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("files")
    p = sub.add_parser("download"); p.add_argument("data_dir")
    p = sub.add_parser("analyze"); p.add_argument("data_dir"); p.add_argument("-o", "--out", required=True)
    p.add_argument("--min-df", type=int, default=40); p.add_argument("--top", type=int, default=80); p.add_argument("--samples", type=int, default=40)
    p = sub.add_parser("search"); p.add_argument("data_dir"); p.add_argument("phrase")
    p.add_argument("--section", choices=["opening", "closing", "reply"], default="opening"); p.add_argument("-n", type=int, default=5)
    a = ap.parse_args()
    {"files": cmd_files, "download": cmd_download, "analyze": cmd_analyze, "search": cmd_search}[a.cmd](a)


if __name__ == "__main__":
    main()
