#!/usr/bin/env python3
"""State, issue ledger and integrity checks for review2revise-loop (closed-loop manuscript refinement).

  r2r.py init        PAPER --venue NAME [--ws DIR] [--max-iter 5] [--hours H] [--depth standard]
                     [--experiments auto|design|off] [--code PATH]... [--data PATH]... [--exp-budget-min 60]
                     [--lang ja|en] [--force]
  r2r.py locate      [--hint DIR]                    find the deep-review-modoki skill
  r2r.py baseline    WS [--pdf PDF] [--main FILE] [--src-only]   iterations/it01/input: paper.pdf, paper.txt, src/
  r2r.py start|end   WS --it N --phase PHASE         phase timer
  r2r.py ingest      WS --it N                       findings + venue review + triage.json -> ledger.json, metrics
  r2r.py decide      WS --issue I003 --choice approve|reject|defer [--action edit|experiment|analysis] [--note T]
  r2r.py exp-new     WS --it N --slug SLUG --issues I003,I005 [--kind experiment|analysis|simulation]
  r2r.py exp-register WS E01                         freeze protocol.md (sha256 + time) before anything runs
  r2r.py exp-check   WS [--it N]                     validate experiment manifests and outputs
  r2r.py changes     WS --it N                       changes.json -> ledger statuses
  r2r.py provenance  WS --it N                       numbers / citations added by the revision without a source
  r2r.py venue-check WS --it N [--which input|output] pages, words, sections vs venue/venue_profile.json
  r2r.py audit       WS --it N                       audit.json -> ledger (rejected rebuttals are reopened)
  r2r.py promote     WS --it N                       iterations/itNN/output -> iterations/it(N+1)/input
  r2r.py log         WS --it N                       iterations/itNN/iteration_log.md
  r2r.py status      WS                              metrics, time budget, convergence -> NEXT: CONTINUE | STOP
  r2r.py limits      WS [--max-iter N] [--hours H | --extend H | --no-deadline]   change the budget mid-run
  r2r.py summary     WS                              ledger.md, progress.md, response_letter.md, human_decisions.md
  r2r.py finish      WS --reason TEXT [--pick N]     close the loop and copy out the deliverable version

Layout of one iteration (itNN): input/ (the version that is reviewed: paper.pdf, paper.txt, src/),
review/ (deep-review-modoki workspace), venue_review.json, triage.json, changes.json, output/ (the revised
version: paper.pdf, paper.txt, src/, changes.diff), provenance.md, audit.json, iteration_log.md.
The output of itNN becomes the input of it(N+1) (`promote`).
"""
import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from snapshot import text_files as snap_files  # noqa: E402  (same file set as snapshot.py)

PHASES = ("setup", "venue", "core", "review", "venue_review", "triage", "human", "revise", "experiment",
          "integrate", "build", "audit", "log")
DEPTHS = ("quick", "standard", "deep")
EXP_MODES = ("auto", "design", "off")
TYPES = ("major", "minor", "suggestion")
RANK = {t: i for i, t in enumerate(TYPES)}
ACTIONS = ("edit", "experiment", "analysis", "rebut", "human", "author", "defer", "none")
RISKS = ("L0", "L1", "L2", "L3")
ACTIONABLE = {"edit", "experiment", "analysis"}
# ledger statuses
ACTIVE = {"open", "addressed", "partially_addressed", "deferred"}          # still in play for the loop
BLOCKED = {"needs_human", "needs_author", "rebutted", "kept_by_human"}     # the loop cannot settle these alone
CLOSED = {"resolved", "lapsed", "declined"}
ACTION_STATUS = {"human": "needs_human", "author": "needs_author", "rebut": "rebutted",
                 "defer": "deferred", "none": "declined"}
CHANGE_STATUS = {"addressed": "addressed", "partially_addressed": "partially_addressed", "rebutted": "rebutted",
                 "deferred": "deferred", "needs_author": "needs_author", "needs_human": "needs_human",
                 "not_addressed": "open"}
EXP_KINDS = ("experiment", "analysis", "simulation")
EXP_STATUS = ("planned", "registered", "running", "completed", "failed", "abandoned", "needs_author")
OUTCOMES = ("supports", "contradicts", "mixed", "inconclusive")
AUDIT_VERDICTS = ("pass", "pass_with_fixes", "fail")
STATUS_JA = {
    "open": "未対応", "addressed": "対応済（再査読待ち）", "partially_addressed": "一部対応（再査読待ち）",
    "deferred": "保留（次回以降）", "needs_human": "人間の判断待ち", "needs_author": "著者の作業が必要",
    "rebutted": "反論（指摘は誤りと判断）", "kept_by_human": "人間の判断で現状維持", "resolved": "解決（再査読で再指摘なし）",
    "lapsed": "未対応・再指摘なし", "declined": "対応しない（理由あり）",
}
TEXT_EXT = {".tex", ".bib", ".md", ".txt", ".html", ".htm", ".bbl"}
DATA_EXT = {".json", ".csv", ".tsv", ".txt", ".tex", ".md", ".log", ".yaml", ".yml"}
REVIEW_MIN = {"quick": 20, "standard": 45, "deep": 90}  # first guess for one review, before any was timed
WRAP_MIN = 20      # build + text + snapshot + checks + audit between the end of a revision and the next review
FINAL_MIN = 10     # finish, summary and final report
MIN_REVISE = 20    # a revision shorter than this is not worth starting
INTEGRATE_MIN = 15  # experiments must stop this long before revise-by so their results can be integrated


# ---------------------------------------------------------------- helpers

def now():
    return dt.datetime.now().replace(microsecond=0)


def iso(t):
    return t.isoformat(timespec="seconds") if t else None


def parse_t(s):
    return dt.datetime.fromisoformat(s) if s else None


def fmt_td(td):
    m = int(td.total_seconds() // 60)
    return f"{m // 60}h{m % 60:02d}m" if m >= 60 else f"{m}m"


def load_json(p, default=None):
    p = Path(p)
    if not p.exists():
        if default is not None:
            return default
        sys.exit(f"missing: {p}")
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        sys.exit(f"invalid JSON in {p}: {e}")


def save_json(p, obj):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def itdir(ws, n):
    return Path(ws) / "iterations" / f"it{n:02d}"


def ctx(ws):
    ws = Path(ws)
    if not (ws / "config.json").exists():
        sys.exit(f"not a review2revise workspace (no config.json): {ws}")
    return ws, load_json(ws / "config.json"), load_json(ws / "state.json"), load_json(ws / "ledger.json")


def checkpoint(ws, tag, ledger):
    """Make per-iteration steps idempotent: a re-run starts from the ledger as it was before the first
    successful run. Returns (ledger to work on, function that records the starting point once it succeeds)."""
    p = Path(ws) / "work" / "checkpoints" / f"{tag}.json"
    if p.exists():
        print(f"note: {tag} was run before; starting again from the ledger as it was before that run "
              f"(re-run the later steps of this iteration afterwards)")
        return load_json(p), lambda: None
    base = json.loads(json.dumps(ledger))
    return ledger, lambda: save_json(p, base)


def drop_later_checkpoints(ws, n, step):
    order = ["ingest", "changes", "audit"]
    later = [f"{s}_it{n:02d}" for s in order[order.index(step) + 1:]] + \
            [f"{s}_it{k:02d}" for k in range(n + 1, n + 30) for s in order]
    for tag in later:
        (Path(ws) / "work" / "checkpoints" / f"{tag}.json").unlink(missing_ok=True)


def loc_str(loc):
    if not isinstance(loc, dict):
        return str(loc or "")
    parts = []
    if loc.get("page") not in (None, ""):
        parts.append(f"p.{loc['page']}")
    for k in ("section", "anchor"):
        if loc.get(k):
            parts.append(str(loc[k]))
    return " ".join(parts)


def md_cell(s, n=None):
    s = re.sub(r"\s+", " ", str(s if s is not None else "")).replace("|", "\\|").strip()
    return s if n is None or len(s) <= n else s[: n - 1] + "…"


def stem_of(cfg):
    return Path(cfg["paper"]).stem


# ---------------------------------------------------------------- locate deep-review-modoki

def find_deep_review(hint=None):
    cands = []
    if hint:
        cands.append(Path(hint))
    cands.append(HERE.parent.parent / "deep-review-modoki")          # installed side by side
    home = Path.home()
    cands += [home / ".claude" / "skills" / "deep-review-modoki", Path.cwd() / ".claude" / "skills" / "deep-review-modoki",
              Path.cwd() / "skills" / "deep-review-modoki"]
    for pat in ("/mnt/skills/*/deep-review-modoki", "/mnt/skills/*/*/deep-review-modoki",
                str(home / ".claude" / "plugins" / "**" / "deep-review-modoki")):
        try:
            cands += [Path(p) for p in glob.glob(pat, recursive=True)]
        except OSError:
            pass
    for c in cands:
        if (c / "SKILL.md").exists() and (c / "scripts" / "deep_review.py").exists():
            return c.resolve()
    return None


def cmd_locate(a):
    p = find_deep_review(a.hint)
    if not p:
        print("NOT FOUND: deep-review-modoki (install it next to this skill or in ~/.claude/skills/)")
        sys.exit(1)
    print(p)


# ---------------------------------------------------------------- init / baseline

def cmd_init(a):
    src = Path(a.paper).resolve()
    if not src.exists():
        sys.exit(f"not found: {src}")
    ws = Path(a.ws).resolve() if a.ws else src.parent / f"{src.stem}_r2r"
    if (ws / "config.json").exists() and not a.force:
        sys.exit(f"workspace already exists: {ws}\n  resume from it (r2r.py status), or pass --force to start over")
    try:
        ws.mkdir(parents=True, exist_ok=True)
    except OSError:
        if a.ws:
            raise
        ws = Path.cwd() / f"{src.stem}_r2r"
        ws.mkdir(parents=True, exist_ok=True)
    if a.force:
        for d in ("iterations", "work", "experiments"):
            shutil.rmtree(ws / d, ignore_errors=True)
        for f in ("state.json", "ledger.json", "ledger.md", "progress.md", "response_letter.md",
                  "human_decisions.md", "final_report.md"):
            (ws / f).unlink(missing_ok=True)
    for d in ("original", "src", "venue", "core", "iterations", "experiments", "work"):
        (ws / d).mkdir(exist_ok=True)
    dst = ws / "original" / src.name
    if not dst.exists():
        if src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns(f"{src.stem}_r2r", "*_r2r", ".git"))
        else:
            shutil.copy2(src, dst)
    kind = "dir" if src.is_dir() else src.suffix.lower().lstrip(".")
    deep = find_deep_review()
    t = now()
    cfg = {
        "skill": "review2revise-loop", "paper": str(src), "original": f"original/{src.name}", "kind": kind,
        "venue": a.venue, "max_iter": a.max_iter, "hours": a.hours, "depth": a.depth,
        "experiments": a.experiments, "code": [str(Path(c).resolve()) for c in a.code],
        "data": [str(Path(d).resolve()) for d in a.data], "exp_budget_min": a.exp_budget_min, "lang": a.lang,
        "deep_review_dir": str(deep) if deep else "", "created": iso(t),
    }
    state = {"started": iso(t), "deadline": iso(t + dt.timedelta(hours=a.hours)) if a.hours else None,
             "status": "running", "finish_reason": "", "phases": [], "metrics": {}, "decisions": []}
    save_json(ws / "config.json", cfg)
    save_json(ws / "state.json", state)
    save_json(ws / "ledger.json", {"next": 1, "issues": {}})
    print(f"workspace : {ws}")
    print(f"paper     : {src} ({kind})")
    print(f"venue     : {a.venue}")
    print(f"limits    : max {a.max_iter} iterations" + (f", deadline {state['deadline']}" if a.hours else ", no time limit"))
    print(f"review    : deep-review-modoki depth={a.depth}   experiments: {a.experiments}"
          + (f" (budget {a.exp_budget_min} min each)" if a.experiments == "auto" else ""))
    print(f"deep-review-modoki: {deep or 'NOT FOUND -> install it before the first review'}")
    if a.experiments == "auto" and not a.code:
        print("WARN: experiments=auto but no --code given; only analyses/simulations that need no author code can run")


def cmd_baseline(a):
    ws, cfg, state, _ = ctx(a.ws)
    inp = itdir(ws, 1) / "input"
    inp.mkdir(parents=True, exist_ok=True)
    if a.main:
        main = Path(a.main)
        main = main if main.is_absolute() else ws / "src" / main
        if not main.exists():
            sys.exit(f"main source not found: {main}")
        cfg["main"] = main.resolve().relative_to((ws / "src").resolve()).as_posix()
        save_json(ws / "config.json", cfg)
        print(f"main source: src/{cfg['main']}")
    if not a.src_only:
        pdf = Path(a.pdf) if a.pdf else None
        if pdf is None:
            orig = ws / cfg["original"]
            pdf = orig if orig.suffix.lower() == ".pdf" else None
        if pdf is None or not pdf.exists():
            sys.exit("no PDF to review: build one from src/ (build_pdf.py --out <ws>/work/baseline.pdf) and pass --pdf")
        shutil.copy2(pdf, inp / "paper.pdf")
        write_text_of(inp / "paper.pdf", inp / "paper.txt")
        print(f"it01/input/paper.pdf <- {pdf}")
    src = ws / "src"
    files = list(snap_files(src).items()) if src.exists() else []
    if files:
        snap = inp / "src"
        shutil.rmtree(snap, ignore_errors=True)
        for rel, p in files:
            q = snap / rel
            q.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, q)
        print(f"it01/input/src <- {len(files)} text source file(s) from src/")
    else:
        print("note: src/ has no sources yet; re-run `baseline --src-only` after preparing them")


def write_text_of(pdf, out):
    from pdf_tools import page_texts
    texts = page_texts(str(pdf))
    Path(out).write_text("".join(f"\n=== Page {i + 1} ===\n{t.rstrip()}\n" for i, t in enumerate(texts)),
                         encoding="utf-8")
    return len(texts)


# ---------------------------------------------------------------- phase timer

def cmd_phase(a, which):
    ws, cfg, state, _ = ctx(a.ws)
    if a.phase not in PHASES:
        sys.exit(f"unknown phase {a.phase}; one of {', '.join(PHASES)}")
    t = now()
    if which == "start":
        if a.it:
            for sub in ("input", "output", "review"):
                (itdir(ws, a.it) / sub).mkdir(parents=True, exist_ok=True)
        state["phases"].append({"it": a.it, "phase": a.phase, "start": iso(t), "end": None})
        msg, warn = f"start it{a.it:02d} {a.phase} at {t:%H:%M}", ""
        tp = time_plan(cfg, state, t)
        if tp:
            if a.phase in ("revise", "experiment", "integrate"):
                msg += f"   revise by {tp['revise_by']:%H:%M}, experiments by {tp['experiments_by']:%H:%M}"
                if t > tp["revise_by"]:
                    warn = "\nWARN: already past revise-by — keep this short (Major only) or skip it"
            if a.phase == "review" and t > tp["review_start_by"]:
                warn = f"\nWARN: past the latest start for a review ({tp['review_start_by']:%H:%M}); it may overrun the deadline"
    else:
        warn = ""
        for ph in reversed(state["phases"]):
            if ph["it"] == a.it and ph["phase"] == a.phase and not ph["end"]:
                ph["end"] = iso(t)
                msg = f"end   it{a.it:02d} {a.phase} ({fmt_td(t - parse_t(ph['start']))})"
                break
        else:
            sys.exit(f"no open phase it{a.it:02d} {a.phase}")
    save_json(ws / "state.json", state)
    left = ""
    if state.get("deadline"):
        left = f"   remaining {fmt_td(max(parse_t(state['deadline']) - t, dt.timedelta(0)))}"
    print(msg + left + warn)


# ---------------------------------------------------------------- findings / triage / ledger

def load_findings(d):
    """All review findings of an iteration: deep-review-modoki findings.json + the venue review."""
    out, warns = {}, []
    deep = d / "review" / "findings.json"
    if deep.exists():
        for f in load_json(deep).get("findings", []):
            out[f["id"]] = {**f, "source": "deep_review"}
    else:
        warns.append(f"missing {deep} (deep-review-modoki has not finished)")
    ven = d / "venue_review.json"
    if ven.exists():
        for f in load_json(ven).get("findings", []):
            if f["id"] in out:
                warns.append(f"venue finding id {f['id']} collides with a deep-review id")
            out[f["id"]] = {**f, "source": "venue"}
    else:
        warns.append(f"missing {ven} (venue reviewer has not finished)")
    for f in out.values():
        if f.get("type") not in TYPES:
            warns.append(f"{f['id']}: type must be one of {TYPES}")
    return out, warns


def decision_of(x):
    h = x.get("human") or {}
    return h.get("choice")


def compute_metrics(n, findings, items, ledger, new_ids, reopened, resolved, lapsed):
    issues = ledger["issues"]
    t = Counter(f.get("type") for f in findings.values())
    src = Counter((f.get("source"), f.get("type")) for f in findings.values())
    m = {"major": t["major"], "minor": t["minor"], "suggestion": t["suggestion"],
         "major_deep": src[("deep_review", "major")], "major_venue": src[("venue", "major")],
         "major_actionable": 0, "major_blocked": 0, "new_major": 0,
         "reopened": len(reopened), "resolved": len(resolved), "lapsed": len(lapsed)}
    for it in items:
        f = findings[it["finding"]]
        if f.get("type") != "major":
            continue
        st = issues[it["ledger_id"]]["status"]
        if st in BLOCKED:
            m["major_blocked"] += 1
        else:
            m["major_actionable"] += 1
        if n > 1 and it["ledger_id"] in new_ids:
            m["new_major"] += 1
    m["W"] = 3 * m["major"] + m["minor"]
    return m


def cmd_ingest(a):
    ws, cfg, state, ledger = ctx(a.ws)
    n, d = a.it, itdir(ws, a.it)
    ledger, commit = checkpoint(ws, f"ingest_it{n:02d}", ledger)
    issues = ledger["issues"]
    findings, warns = load_findings(d)
    for w in warns:
        print("WARN:", w)
    if not findings:
        sys.exit("no findings to ingest")
    tri_p = d / "triage.json"
    tri = load_json(tri_p)
    items = tri.get("items", [])
    errors, seen = [], set()
    errors += [w for w in warns if "type must be" in w or "collides" in w]
    for i, it in enumerate(items):
        fid, lid = it.get("finding"), it.get("ledger_id", "new")
        tag = f"triage item {i + 1} ({fid})"
        if fid not in findings:
            errors.append(f"{tag}: unknown finding id")
            continue
        if fid in seen:
            errors.append(f"{tag}: finding triaged twice")
        seen.add(fid)
        if lid != "new" and lid not in issues:
            errors.append(f"{tag}: ledger_id {lid} does not exist (use \"new\")")
        act, risk = it.get("action"), it.get("core_risk")
        if act not in ACTIONS:
            errors.append(f"{tag}: action must be one of {ACTIONS}")
        if risk not in RISKS:
            errors.append(f"{tag}: core_risk must be one of {RISKS}")
        approved = lid in issues and decision_of(issues[lid]) == "approve"
        if risk == "L3" and act != "human" and not approved:
            errors.append(f"{tag}: core_risk L3 needs action \"human\" (no human approval recorded for {lid})")
        if act == "human" and not it.get("human_question"):
            errors.append(f"{tag}: action human needs human_question")
        if act in ACTIONABLE | {"author"} and not it.get("plan"):
            errors.append(f"{tag}: plan is required for action {act}")
        if act in ("rebut", "none", "defer") and not it.get("rationale"):
            errors.append(f"{tag}: rationale is required for action {act}")
        if act == "none" and findings[fid].get("type") == "major":
            errors.append(f"{tag}: a major finding cannot be dropped with action none (rebut, defer or escalate)")
    missing = [fid for fid, f in findings.items() if f.get("type") in ("major", "minor") and fid not in seen]
    if missing:
        errors.append("untriaged major/minor findings: " + ", ".join(missing))
    if errors:
        print("TRIAGE INVALID — ledger not changed:")
        for e in errors:
            print("  -", e)
        sys.exit(1)

    prev_active = {k for k, x in issues.items() if x["status"] in ACTIVE}
    mapped, new_ids, reopened = set(), set(), []
    for it in items:
        f = findings[it["finding"]]
        if it.get("ledger_id", "new") == "new":
            iid = f"I{ledger['next']:03d}"
            ledger["next"] += 1
            issues[iid] = {"title": it.get("title") or f.get("title", ""), "origin": f["source"],
                           "category": f.get("category", ""), "first_seen": n, "type": f["type"], "history": [],
                           "status": "open", "resolution": [], "experiments": [], "reopened": 0}
            new_ids.add(iid)
        else:
            iid = it["ledger_id"]
        x = issues[iid]
        if iid in mapped:  # several findings of this review map to one issue: keep the most severe type
            x["type"] = min(x["type"], f["type"], key=lambda s: RANK[s])
        else:
            x["type"] = f["type"]
        if x["status"] in ("resolved", "lapsed"):
            x["reopened"] = x.get("reopened", 0) + 1
            reopened.append(iid)
        x["history"].append({"it": n, "finding": f["id"], "source": f["source"], "type": f["type"],
                             "title": f.get("title", ""), "location": loc_str(f.get("location"))})
        x.update({"action": it["action"], "core_risk": it["core_risk"], "plan": it.get("plan", ""),
                  "rationale": it.get("rationale", ""), "last_seen": n})
        if it.get("human_question"):
            x["human_question"] = it["human_question"]
        if decision_of(x) == "reject":
            x["status"] = "kept_by_human"
        else:
            x["status"] = ACTION_STATUS.get(it["action"], "open")
        mapped.add(iid)
        it["ledger_id"] = iid
    resolved, lapsed = [], []
    for iid in sorted(prev_active - mapped):
        x = issues[iid]
        if x["status"] in ("addressed", "partially_addressed"):
            x["status"], x["resolved_at"] = "resolved", n
            resolved.append(iid)
        else:
            x["status"], x["lapsed_at"] = "lapsed", n
            lapsed.append(iid)
    commit()
    drop_later_checkpoints(ws, n, "ingest")
    save_json(tri_p, tri)  # ledger ids filled in for later steps
    m = compute_metrics(n, findings, items, ledger, new_ids, reopened, resolved, lapsed)
    state["metrics"][str(n)] = m
    save_json(ws / "ledger.json", ledger)
    save_json(ws / "state.json", state)
    write_human_decisions(ws, ledger)

    print(f"it{n:02d} ingested: {len(findings)} findings -> {len(mapped)} issues "
          f"({len(new_ids)} new, {len(reopened)} reopened); resolved since last review: {len(resolved)}, "
          f"not re-flagged without a fix: {len(lapsed)}")
    print(f"  Major {m['major']} (deep {m['major_deep']}, venue {m['major_venue']}; actionable {m['major_actionable']}, "
          f"blocked {m['major_blocked']}, new {m['new_major']})  Minor {m['minor']}  Suggestion {m['suggestion']}  W={m['W']}")
    print("  finding -> issue / action:")
    for it in items:
        x = issues[it["ledger_id"]]
        print(f"    {it['finding']:<6} -> {it['ledger_id']}  {x['type']:<10} {it['action']:<10} {it['core_risk']}  "
              f"{md_cell(x['title'], 60)}")
    pending = [k for k, x in issues.items() if x["status"] == "needs_human" and decision_of(x) != "defer"]
    if pending:
        print(f"ASK HUMAN: {', '.join(pending)} (see human_decisions.md)")
    if reopened:
        print(f"WARN: reopened after being resolved: {', '.join(reopened)} — check whether a later edit undid the fix")


def cmd_decide(a):
    ws, cfg, state, ledger = ctx(a.ws)
    x = ledger["issues"].get(a.issue)
    if not x:
        sys.exit(f"unknown issue {a.issue}")
    x["human"] = {"choice": a.choice, "note": a.note or "", "at": iso(now()), "question": x.get("human_question", "")}
    if a.choice == "approve":
        x["status"] = "open"
        x["action"] = a.action
        x["approved_action"] = a.action
    elif a.choice == "reject":
        x["status"] = "kept_by_human"
    else:
        x["status"] = "needs_human"
    state["decisions"].append({"issue": a.issue, "choice": a.choice, "note": a.note or "", "at": iso(now())})
    save_json(ws / "ledger.json", ledger)
    save_json(ws / "state.json", state)
    write_human_decisions(ws, ledger)
    print(f"{a.issue}: {a.choice}" + (f" -> action {a.action}" if a.choice == "approve" else "") + f"  [{x['status']}]")


def write_human_decisions(ws, ledger):
    rows_p, rows_d = [], []
    for k, x in ledger["issues"].items():
        h = x.get("human")
        if x["status"] == "needs_human" and (not h or h.get("choice") == "defer"):
            rows_p.append(f"| {k} | {x['type']} | {md_cell(x['title'], 70)} | {md_cell(x.get('human_question', ''), 160)} |")
        if h:
            rows_d.append(f"| {k} | {h['choice']} | {md_cell(x['title'], 60)} | {md_cell(h.get('note', ''), 120)} | {h['at']} |")
    lines = ["# 人間の判断が必要な事項", "",
             "scientific core（研究課題・中心的アイデア・主要手法）に触れる変更は自動では行わない。", "",
             "## 判断待ち", ""]
    lines += (["| ID | 重大度 | 指摘 | 質問 |", "|---|---|---|---|"] + rows_p) if rows_p else ["（なし）"]
    lines += ["", "## 判断済み", ""]
    lines += (["| ID | 判断 | 指摘 | メモ | 日時 |", "|---|---|---|---|---|"] + rows_d) if rows_d else ["（なし）"]
    (Path(ws) / "human_decisions.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- experiments

def exp_dirs(ws):
    return sorted(p for p in (Path(ws) / "experiments").glob("E[0-9][0-9]*") if (p / "manifest.json").exists())


def find_exp(ws, eid):
    for p in exp_dirs(ws):
        if p.name == eid or p.name.startswith(eid + "_"):
            return p
    sys.exit(f"unknown experiment {eid}")


PROTOCOL_TEMPLATE = """# {eid} {slug} — 事前登録プロトコル

- 対応する指摘: {issues}
- 種類: {kind}
- 作成: {created}（`r2r.py exp-register` で凍結するまで編集可。凍結後の変更は manifest の deviations に書く）

## 1. 問い
<!-- どの主張（core.json の C 番号）と、どの指摘に答えるのか -->

## 2. 仮説と判定基準
<!-- どの結果なら主張を支持 / 否定 / 判断不能とするか。実行前に決める -->

## 3. 設計
<!-- データ・分割、ベースライン、指標、seed 数、統計手法、比較の公平性（チューニング予算を揃える等） -->

## 4. 実行計画
<!-- コマンド、計算資源の見積もり、上限時間。ユーザーのコード・データは読み取り専用で使う -->

## 5. 報告のしかた
<!-- 結果の向きにかかわらず報告する図・表。結果ごとに本文のどこをどう変えるか -->

## 6. リスク・制約
"""


def cmd_exp_new(a):
    ws, cfg, state, ledger = ctx(a.ws)
    slug = re.sub(r"[^a-z0-9]+", "-", a.slug.lower()).strip("-") or "exp"
    ids = [int(re.match(r"E(\d+)", p.name).group(1)) for p in exp_dirs(ws)]
    eid = f"E{(max(ids) + 1 if ids else 1):02d}"
    issues = [s.strip() for s in a.issues.split(",") if s.strip()]
    unknown = [i for i in issues if i not in ledger["issues"]]
    if unknown:
        sys.exit(f"unknown ledger issue(s): {', '.join(unknown)} (run ingest first)")
    d = Path(ws) / "experiments" / f"{eid}_{slug}"
    for sub in ("scripts", "outputs", "logs"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    desc = ", ".join(f"{i}（{ledger['issues'][i]['title']}）" for i in issues)
    (d / "protocol.md").write_text(PROTOCOL_TEMPLATE.format(eid=eid, slug=slug, issues=desc, kind=a.kind,
                                                            created=iso(now())), encoding="utf-8")
    save_json(d / "manifest.json", {
        "id": eid, "slug": slug, "kind": a.kind, "iteration": a.it, "issues": issues, "status": "planned",
        "created": iso(now()), "protocol_sha256": None, "registered_at": None, "commands": [], "environment": "",
        "results": [], "figures": [], "tables": [], "outcome": None, "summary": "", "deviations": [],
        "runtime_min": None, "integrated_into": []})
    for i in issues:
        ex = ledger["issues"][i].setdefault("experiments", [])
        if eid not in ex:
            ex.append(eid)
    save_json(ws / "ledger.json", ledger)
    print(f"{eid}: {d}")


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def protocol_sections_filled(text):
    body = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    parts = re.split(r"^## ", body, flags=re.M)[1:]
    empty = []
    for part in parts:
        title, _, rest = part.partition("\n")
        if not rest.strip() and not title.startswith("6"):
            empty.append(title.strip())
    return empty


def cmd_exp_register(a):
    ws, cfg, state, ledger = ctx(a.ws)
    d = find_exp(ws, a.exp)
    man = load_json(d / "manifest.json")
    if man.get("registered_at"):
        sys.exit(f"{man['id']} already registered at {man['registered_at']}; record changes in deviations")
    empty = protocol_sections_filled((d / "protocol.md").read_text(encoding="utf-8"))
    if empty:
        sys.exit(f"protocol.md has empty sections: {', '.join(empty)}")
    outs = [p for p in (d / "outputs").rglob("*") if p.is_file()]
    if outs:
        print(f"WARN: outputs/ already has {len(outs)} file(s) before registration — note this in deviations")
    man.update({"protocol_sha256": sha256(d / "protocol.md"), "registered_at": iso(now()), "status": "registered"})
    save_json(d / "manifest.json", man)
    print(f"{man['id']} registered {man['registered_at']}  sha256={man['protocol_sha256'][:12]}")


def check_manifest(d, man):
    probs = []
    st = man.get("status")
    if st not in EXP_STATUS:
        probs.append(f"status must be one of {EXP_STATUS}")
    if st in ("running", "completed", "failed") and not man.get("registered_at"):
        probs.append("ran without a registered protocol (exp-register)")
    if man.get("protocol_sha256") and (d / "protocol.md").exists() and \
            sha256(d / "protocol.md") != man["protocol_sha256"] and not man.get("deviations"):
        probs.append("protocol.md changed after registration but no deviations recorded")
    if st == "completed":
        if not man.get("results"):
            probs.append("completed but results[] is empty")
        if man.get("outcome") not in OUTCOMES:
            probs.append(f"outcome must be one of {OUTCOMES}")
        if not man.get("summary"):
            probs.append("summary is empty")
        if not man.get("commands"):
            probs.append("commands[] is empty (record how it was run)")
        reg = parse_t(man.get("registered_at"))
        for key in ("results", "figures", "tables"):
            for rel in man.get(key, []):
                p = d / rel
                if not p.exists():
                    probs.append(f"{key}: missing file {rel}")
                    continue
                if p.suffix == ".json":
                    try:
                        json.loads(p.read_text(encoding="utf-8-sig"))
                    except json.JSONDecodeError:
                        probs.append(f"{rel}: invalid JSON")
                if reg and dt.datetime.fromtimestamp(p.stat().st_mtime) < reg - dt.timedelta(seconds=5):
                    probs.append(f"{rel} is older than the protocol registration")
    if st in ("failed", "abandoned", "needs_author") and not man.get("summary"):
        probs.append(f"{st}: say why in summary")
    return probs


def cmd_exp_check(a):
    ws, cfg, state, ledger = ctx(a.ws)
    bad = 0
    rows = []
    for d in exp_dirs(ws):
        man = load_json(d / "manifest.json")
        if a.it and man.get("iteration") != a.it:
            continue
        probs = check_manifest(d, man)
        bad += bool(probs)
        rows.append((man, probs))
        for i in man.get("issues", []):
            if i in ledger["issues"]:
                ex = ledger["issues"][i].setdefault("experiments", [])
                if man["id"] not in ex:
                    ex.append(man["id"])
    save_json(ws / "ledger.json", ledger)
    if not rows:
        print("no experiments")
        return
    for man, probs in rows:
        print(f"{man['id']} it{man.get('iteration', 0):02d} {man.get('kind', ''):<10} {man.get('status', ''):<12} "
              f"outcome={man.get('outcome') or '-':<12} issues={','.join(man.get('issues', []))}  "
              f"{'OK' if not probs else 'PROBLEMS'}")
        for p in probs:
            print(f"    - {p}")
    if bad:
        sys.exit(1)


# ---------------------------------------------------------------- changes / audit

def cmd_changes(a):
    ws, cfg, state, ledger = ctx(a.ws)
    n, d = a.it, itdir(ws, a.it)
    ledger, commit = checkpoint(ws, f"changes_it{n:02d}", ledger)
    issues = ledger["issues"]
    ch = load_json(d / "changes.json")
    errors = []
    for i, c in enumerate(ch.get("items", [])):
        lid = c.get("ledger_id")
        if lid not in issues:
            errors.append(f"item {i + 1}: unknown ledger_id {lid}")
        if c.get("status") not in CHANGE_STATUS:
            errors.append(f"item {i + 1} ({lid}): status must be one of {tuple(CHANGE_STATUS)}")
        if not c.get("summary"):
            errors.append(f"item {i + 1} ({lid}): summary is required")
        if c.get("status") in ("addressed", "partially_addressed") and not c.get("locations"):
            errors.append(f"item {i + 1} ({lid}): locations are required when the manuscript changed")
        if lid in issues and c.get("status") in ("addressed", "partially_addressed") \
                and issues[lid].get("core_risk") == "L3" and decision_of(issues[lid]) != "approve":
            errors.append(f"item {i + 1} ({lid}): L3 (core) change applied without human approval — revert it")
    for j, cc in enumerate(ch.get("claim_changes", [])):
        miss = [k for k in ("claim", "before", "after", "reason") if not cc.get(k)]
        if miss:
            errors.append(f"claim_changes {j + 1}: missing {', '.join(miss)}")
    if errors:
        print("CHANGES INVALID — ledger not changed:")
        for e in errors:
            print("  -", e)
        sys.exit(1)
    done = set()
    for c in ch.get("items", []):
        x = issues[c["ledger_id"]]
        x["resolution"] = [r for r in x.get("resolution", []) if r.get("it") != n]
        x["resolution"].append({"it": n, "status": c["status"], "summary": c["summary"],
                                "locations": c.get("locations", []), "response": c.get("response", ""),
                                "experiments": c.get("experiments", [])})
        if decision_of(x) == "reject":
            x["status"] = "kept_by_human"
        else:
            x["status"] = CHANGE_STATUS[c["status"]]
        done.add(c["ledger_id"])
    commit()
    drop_later_checkpoints(ws, n, "changes")
    tri = load_json(d / "triage.json", {"items": []})
    todo = sorted({it["ledger_id"] for it in tri.get("items", [])
                   if issues.get(it.get("ledger_id"), {}).get("status") == "open"
                   and issues[it["ledger_id"]].get("action") in ACTIONABLE} - done)
    save_json(ws / "ledger.json", ledger)
    save_json(ws / "state.json", state)
    st = Counter(c["status"] for c in ch.get("items", []))
    print(f"it{n:02d} changes: " + ", ".join(f"{k} {v}" for k, v in st.items())
          + f"; claim changes {len(ch.get('claim_changes', []))}")
    if todo:
        print(f"WARN: actionable issues with no entry in changes.json (still open): {', '.join(todo)}")


def cmd_audit(a):
    ws, cfg, state, ledger = ctx(a.ws)
    n, d = a.it, itdir(ws, a.it)
    ledger, commit = checkpoint(ws, f"audit_it{n:02d}", ledger)
    au = load_json(d / "audit.json")
    if au.get("verdict") not in AUDIT_VERDICTS:
        sys.exit(f"audit.json: verdict must be one of {AUDIT_VERDICTS}")
    commit()
    drop_later_checkpoints(ws, n, "audit")
    reopened = []
    for rr in au.get("rebuttal_reviews", []):
        x = ledger["issues"].get(rr.get("ledger_id"))
        if x is None:
            print(f"WARN: rebuttal review for unknown issue {rr.get('ledger_id')}")
            continue
        x["rebuttal_audit"] = {"it": n, "upheld": bool(rr.get("upheld")), "reason": rr.get("reason", "")}
        if not rr.get("upheld") and x["status"] == "rebutted":
            x["status"] = "open"
            reopened.append(rr["ledger_id"])
    fixes = au.get("required_fixes", [])
    pending = [f.get("id", "?") for f in fixes if not f.get("applied")]
    save_json(ws / "ledger.json", ledger)
    save_json(ws / "state.json", state)
    print(f"it{n:02d} audit: {au['verdict']}; required fixes {len(fixes)} (unapplied {len(pending)}); "
          f"rebuttals reviewed {len(au.get('rebuttal_reviews', []))}, not upheld {len(reopened)}")
    if reopened:
        print(f"  reopened (rebuttal not upheld): {', '.join(reopened)} — address them before promote, or next iteration")
    if pending:
        print(f"BLOCK: apply fixes {', '.join(pending)}, rebuild, set \"applied\": true and re-run audit")
        sys.exit(1)
    if au["verdict"] == "fail":
        print("BLOCK: verdict fail — revert the offending changes (or fix them) and re-audit before promote")
        sys.exit(1)


# ---------------------------------------------------------------- provenance

NUM_RE = re.compile(r"(?<![A-Za-z_\\\d.])(\d+(?:\.\d+)?)(\s*\\?%)?(?![\d])")
STRIP_CMDS = re.compile(
    r"\\(?:label|ref|eqref|cref|Cref|autoref|pageref|nameref|cite\w*|input|include|includegraphics|includepdf|"
    r"bibitem|url|href|begin|end|usepackage|documentclass|vspace|hspace|setlength|addtolength|color|textcolor|"
    r"definecolor|newcommand|renewcommand|setcounter|resizebox|scalebox|multicolumn|multirow|cline|cmidrule)"
    r"\*?(?:\s*\[[^\]]*\])*(?:\s*\{[^{}]*\})?")
REF_WORDS = re.compile(
    r"(?:\b(?:Sec(?:tion)?s?\.?|Eqs?\.?|Equations?|Figs?\.?|Figures?|Tables?|Tab\.|Appendi(?:x|ces)|App\.|Theorems?|"
    r"Lemmas?|Corollar(?:y|ies)|Propositions?|Definitions?|Assumptions?|Algorithms?|Alg\.|Steps?|Lines?|Remarks?|"
    r"Examples?|Chapters?|Claims?|Refs?\.?|C|E|I)|§|図|表|式|定理|補題|定義|仮定|節|章|付録)\s*~?\(?[A-Z]?\d+(?:\.\d+)*\)?")
NOISE = [re.compile(p) for p in (
    r"(?<!\\)%.*$", r"\[[^\]]*=[^\]]*\]", r"\d*\.?\d+\s*(?:pt|mm|cm|in|em|ex|bp)\b",
    r"\d*\.?\d+\s*\\(?:line|text|column)(?:width|height)", r"https?://\S+", r"!?\[[^\]]*\]\([^)]*\)",
    r"\b(?:19|20)\d\d[a-z]?\b", r"\b[A-Z]{2,}[-\d]+\b", r"\b\w+[-_]\d+\b", r"\{\d+(?:\.\d+)?\}")]


def numbers_in(text, keep_small=False):
    out = []
    for m in NUM_RE.finditer(text):
        s = m.group(1)
        val = float(s)
        dec = len(s.split(".")[1]) if "." in s else 0
        if dec == 0 and not keep_small and val <= 10 and not m.group(2):
            continue
        out.append((s + (m.group(2) or "").replace("\\", "").replace(" ", ""), val, dec))
    return out


def clean_line(line):
    line = re.sub(r"(\d),(\d{3})", r"\1\2", line)
    for rx in NOISE[:1]:
        line = rx.sub("", line)
    line = STRIP_CMDS.sub(" ", line)
    line = REF_WORDS.sub(" ", line)
    for rx in NOISE[1:]:
        line = rx.sub(" ", line)
    return line


def source_numbers(paths):
    vals = set()
    for p in paths:
        try:
            if p.stat().st_size > 5_000_000:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        text = re.sub(r"(\d),(\d{3})", r"\1\2", text)
        for m in re.finditer(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", text):
            try:
                vals.add(float(m.group(0)))
            except ValueError:
                pass
    table = {}
    for dec in range(0, 7):
        s = set()
        for v in vals:
            for w in (v, v * 100, v / 100, abs(v)):
                s.add(round(w, dec))
        table[dec] = s
    return table


def cite_keys(text):
    keys = set()
    for m in re.finditer(r"\\(?:no)?cite\w*\*?(?:\[[^\]]*\])*\{([^}]*)\}", text):
        keys |= {k.strip() for k in m.group(1).split(",") if k.strip()}
    return keys


def bib_keys(root):
    keys = set()
    for p in Path(root).rglob("*") if Path(root).exists() else []:
        if p.suffix.lower() in (".bib", ".tex", ".bbl"):
            t = p.read_text(encoding="utf-8", errors="replace")
            keys |= set(re.findall(r"@\w+\s*\{\s*([^,\s]+)\s*,", t))
            keys |= set(re.findall(r"\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}", t))
    return keys


def count_todo(root):
    n = 0
    for p in Path(root).rglob("*") if Path(root).exists() else []:
        if p.suffix.lower() in (".tex", ".md"):
            t = p.read_text(encoding="utf-8", errors="replace")
            n += len(re.findall(r"\\authortodo\{", t)) + len(re.findall(r"\[AUTHOR TODO", t))
    return n


def added_lines(diff):
    """(file, new line number, text) for every line a unified diff adds."""
    rows = diff.read_text(encoding="utf-8", errors="replace").splitlines()
    out, cur, ln = [], None, 0
    for i, raw in enumerate(rows):
        if raw.startswith("--- ") and i + 1 < len(rows) and rows[i + 1].startswith("+++ "):
            continue
        if raw.startswith("+++ ") and i > 0 and rows[i - 1].startswith("--- "):
            cur = raw[4:].strip().replace("this/", "", 1)
            continue
        if raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            ln = int(m.group(1)) if m else 1
            continue
        if cur is None:
            continue
        if raw.startswith("+"):
            out.append((cur, ln, raw[1:]))
            ln += 1
        elif not raw.startswith("-"):
            ln += 1
    return out


def cmd_provenance(a):
    ws, cfg, state, ledger = ctx(a.ws)
    d = itdir(ws, a.it)
    diff = d / "output" / "changes.diff"
    if not diff.exists():
        sys.exit(f"missing {diff} (run snapshot.py <ws>/src <it>/output --prev <it>/input first)")
    added = [(f, ln, t) for f, ln, t in added_lines(diff) if Path(f).suffix.lower() in (".tex", ".md", ".html", ".htm")]
    srcs = [p for p in (d / "input").rglob("*") if p.is_file() and p.suffix.lower() in TEXT_EXT]
    for e in exp_dirs(ws):
        srcs += [p for p in e.rglob("*") if p.is_file() and p.suffix.lower() in DATA_EXT]
    table = source_numbers(srcs)
    untraced, checked = [], 0
    for f, ln, text in added:
        for tok, val, dec in numbers_in(clean_line(text)):
            checked += 1
            if round(val, dec) not in table.get(min(dec, 6), set()):
                untraced.append((f, ln, tok, text.strip()))
    new_text = "\n".join(t for _, _, t in added)
    old_keys = bib_keys(d / "input")
    old_tex = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                        for p in (d / "input").rglob("*.tex"))
    new_cites = sorted(cite_keys(new_text) - cite_keys(old_tex))
    out_keys = bib_keys(d / "output")
    undefined = [k for k in new_cites if k not in out_keys]
    added_bib = sorted(out_keys - old_keys)
    todo_in, todo_out = count_todo(d / "input"), count_todo(d / "output")
    lines = [f"# Provenance check — it{a.it:02d}", "",
             f"- 追加された行: {len(added)}　検査した数値: {checked}　出所不明: {len(untraced)}",
             f"- 新しい引用キー: {len(new_cites)}（文献リストに未定義: {len(undefined)}）　新しい文献エントリ: {len(added_bib)}",
             f"- AUTHOR TODO: {todo_in} → {todo_out}", "",
             "出所 = この反復の入力版（本文・ソース）または experiments/ の記録・出力に、丸めを考慮して同じ値があること。",
             "出所不明の数値は、実験記録から転記し直すか、導出（例：表の値からの差）を changes.json に書くか、削除する。", ""]
    if untraced:
        lines += ["## 出所不明の数値", "", "| ファイル:行 | 値 | 行 |", "|---|---|---|"]
        lines += [f"| {f}:{ln} | {tok} | {md_cell(t, 140)} |" for f, ln, tok, t in untraced]
        lines.append("")
    if new_cites:
        lines += ["## 新しく引用された文献（実在と内容を確認すること）", ""]
        lines += [f"- `{k}`" + ("  ← 文献リストに未定義" if k in undefined else "") for k in new_cites]
        lines.append("")
    if added_bib:
        lines += ["## 新しく追加された文献エントリ", ""] + [f"- `{k}`" for k in added_bib] + [""]
    (d / "provenance.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"it{a.it:02d} provenance: {len(added)} added lines, {checked} numbers, UNTRACED {len(untraced)}; "
          f"new citations {len(new_cites)} (undefined {len(undefined)}); AUTHOR TODO {todo_in}->{todo_out}")
    for f, ln, tok, t in untraced[:15]:
        print(f"  {f}:{ln}  {tok}  | {md_cell(t, 90)}")
    if len(untraced) > 15:
        print(f"  ... {len(untraced) - 15} more in {d / 'provenance.md'}")


# ---------------------------------------------------------------- venue check

HEAD_RE = re.compile(r"^\s*(?:\d{1,2}(?:\.\d{1,2})*\.?\s+)?[A-Z][A-Za-z ,&\-]{2,60}\s*$")


def cmd_venue_check(a):
    ws, cfg, state, ledger = ctx(a.ws)
    prof = load_json(ws / "venue" / "venue_profile.json", {})
    txt = itdir(ws, a.it) / a.which / "paper.txt"
    if not txt.exists():
        sys.exit(f"missing {txt}")
    raw = txt.read_text(encoding="utf-8", errors="replace")
    pages = re.split(r"\n=== Page \d+ ===\n", raw)[1:]
    ref_page = None
    for i, pg in enumerate(pages):
        if re.search(r"^\s*(?:\d+\.?\s*)?(References|Bibliography|REFERENCES|参考文献|Literature Cited)\s*$", pg, re.M):
            ref_page = i + 1
            break
    body = "\n".join(pages[: ref_page or len(pages)])
    cut = re.split(r"^\s*(?:\d+\.?\s*)?(?:References|Bibliography|REFERENCES|参考文献)\s*$", body, flags=re.M)[0]
    cjk = len(re.findall(r"[\u3040-\u30ff\u4e00-\u9fff]", cut))
    words = len(re.findall(r"[A-Za-z0-9][\w'\-]*", cut)) + cjk // 2
    abs_m = re.search(r"^\s*(?:Abstract|ABSTRACT|概要|要旨)\s*[.:—-]?\s*(.*?)(?=^\s*(?:\d+\.?\s+|I\.\s+)?"
                      r"(?:Introduction|INTRODUCTION|Keywords|Index Terms|はじめに|序論)\b)", raw, re.S | re.M)
    abs_words = len(re.findall(r"[A-Za-z0-9][\w'\-]*", abs_m.group(1))) if abs_m else None
    figs = {m.group(1) for m in re.finditer(r"^\s*(?:Figure|Fig\.)\s*(\d+)\s*[:.|]", raw, re.M)}
    tabs = {m.group(1) for m in re.finditer(r"^\s*(?:Table|TABLE)\s*([IVX\d]+)\s*[:.|]?", raw, re.M)}
    lim = prof.get("limits", {}) or {}
    rows = [("pages (total)", len(pages), lim.get("pages")),
            ("pages before references", ref_page, lim.get("main_pages")),
            ("words before references (approx.)", words, lim.get("words")),
            ("abstract words (approx.)", abs_words, lim.get("abstract_words")),
            ("figures (captions)", len(figs), lim.get("figures")),
            ("tables (captions)", len(tabs), lim.get("tables"))]
    print(f"venue-check it{a.it:02d}/{a.which} vs {prof.get('name', cfg['venue'])}  (heuristic — confirm on the PDF)")
    for name, val, lim_v in rows:
        if val is None:
            flag = "?"
        elif lim_v in (None, ""):
            flag = "-"
        else:
            flag = "OVER" if val > lim_v else "OK"
        print(f"  {name:<36} {str(val if val is not None else '?'):>7}   limit {str(lim_v if lim_v not in (None, '') else '-'):>7}   {flag}")
    lines = [ln.strip() for ln in raw.splitlines()]
    for sec in prof.get("required_sections", []):
        key = re.sub(r"\s+", " ", sec.lower())
        hit = any(ln.lower().startswith(key) or (key in ln.lower() and len(ln) <= len(key) + 12) for ln in lines)
        print(f"  section: {sec:<44} {'OK' if hit else 'MISSING?'}")


# ---------------------------------------------------------------- promote

def cmd_promote(a):
    ws, cfg, state, ledger = ctx(a.ws)
    n = a.it
    out, nxt = itdir(ws, n) / "output", itdir(ws, n + 1) / "input"
    for f in ("paper.pdf", "paper.txt"):
        if not (out / f).exists():
            sys.exit(f"missing {out / f}")
    if not (out / "src").exists():
        sys.exit(f"missing {out / 'src'} (snapshot.py)")
    au = load_json(itdir(ws, n) / "audit.json", {})
    if not au:
        sys.exit(f"no audit.json for it{n:02d}: run the integrity audit before the next review")
    if au.get("verdict") == "fail" or any(not f.get("applied") for f in au.get("required_fixes", [])):
        sys.exit("audit is failing or has unapplied fixes; fix, rebuild and re-run `audit` first")
    src_files, snapped = snap_files(ws / "src"), snap_files(out / "src")
    stale = sorted(k for k, p in src_files.items()
                   if k not in snapped or p.read_bytes() != snapped[k].read_bytes())
    if stale:
        sys.exit(f"output/src is not the current src/ ({', '.join(stale[:5])}): rebuild, snapshot and re-audit first")
    newest = max((p.stat().st_mtime for p in src_files.values()), default=0)
    if newest > (out / "paper.pdf").stat().st_mtime + 2:
        sys.exit("output/paper.pdf is older than src/: rebuild the PDF (build_pdf.py --out) and re-audit first")
    if nxt.exists():
        shutil.rmtree(nxt)
    nxt.mkdir(parents=True)
    shutil.copy2(out / "paper.pdf", nxt / "paper.pdf")
    shutil.copy2(out / "paper.txt", nxt / "paper.txt")
    shutil.copytree(out / "src", nxt / "src")
    for sub in ("output", "review"):
        (itdir(ws, n + 1) / sub).mkdir(exist_ok=True)
    print(f"it{n + 1:02d}/input <- it{n:02d}/output")


# ---------------------------------------------------------------- log

def phase_minutes(state, n):
    out = {}
    for ph in state["phases"]:
        if ph["it"] == n and ph["end"]:
            out[ph["phase"]] = out.get(ph["phase"], 0) + (parse_t(ph["end"]) - parse_t(ph["start"])).total_seconds() / 60
    return out


def diff_stats(diff):
    stats = {}
    if not diff.exists():
        return stats
    cur = None
    for ln in diff.read_text(encoding="utf-8", errors="replace").splitlines():
        if ln.startswith("+++ "):
            cur = ln[4:].replace("this/", "", 1)
            stats.setdefault(cur, [0, 0])
        elif cur and ln.startswith("+") and not ln.startswith("+++"):
            stats[cur][0] += 1
        elif cur and ln.startswith("-") and not ln.startswith("---"):
            stats[cur][1] += 1
    return stats


def cmd_log(a):
    ws, cfg, state, ledger = ctx(a.ws)
    n, d = a.it, itdir(ws, a.it)
    issues = ledger["issues"]
    findings, _ = load_findings(d)
    tri = load_json(d / "triage.json", {"items": []})
    ch = load_json(d / "changes.json", {"items": []})
    au = load_json(d / "audit.json", {})
    m = state["metrics"].get(str(n), {})
    by_finding = {it["finding"]: it for it in tri.get("items", [])}
    L = [f"# Iteration {n:02d} — {cfg['venue']}", ""]
    mins = phase_minutes(state, n)
    if mins:
        L.append("- 所要時間: " + ", ".join(f"{k} {v:.0f}分" for k, v in mins.items()))
    L.append(f"- 査読対象: `iterations/it{n:02d}/input/paper.pdf`　改訂版: "
             + (f"`iterations/it{n:02d}/output/paper.pdf`" if (d / "output" / "paper.pdf").exists() else "（この反復では改訂なし）"))
    if m:
        L.append(f"- 指標: Major {m['major']}（deep {m['major_deep']} / venue {m['major_venue']}、新規 {m['new_major']}、"
                 f"人間・著者待ち等 {m['major_blocked']}）、Minor {m['minor']}、Suggestion {m['suggestion']}、"
                 f"W={m['W']}、前回から解決 {m['resolved']}")
    L += ["", "## 1. 査読コメント", ""]
    deep_f = load_json(d / "review" / "findings.json", {})
    if deep_f.get("overall", {}).get("bottom_line"):
        L += [f"**deep-review-modoki 総括**: {md_cell(deep_f['overall']['bottom_line'])}", ""]
    ven_f = load_json(d / "venue_review.json", {})
    if ven_f.get("scope_fit"):
        sf = ven_f["scope_fit"]
        L += [f"**投稿先との適合（{sf.get('verdict', '?')}）**: {md_cell(sf.get('rationale', ''))}", ""]
    L += ["| 指摘 | 出所 | 重大度 | 分類 | 内容 | 場所 | → 課題 |", "|---|---|---|---|---|---|---|"]
    for fid, f in sorted(findings.items(), key=lambda kv: (RANK.get(kv[1].get("type"), 9), kv[0])):
        it = by_finding.get(fid, {})
        L.append(f"| {fid} | {'査読' if f['source'] == 'deep_review' else '投稿先'} | {f.get('type')} | "
                 f"{f.get('category', '')} | {md_cell(f.get('title', ''), 90)} | {md_cell(loc_str(f.get('location')), 40)} | "
                 f"{it.get('ledger_id', '—')} |")
    L += ["", "## 2. 対応内容", "", "| 課題 | 指摘 | 方針 | core | 結果 | 内容 | 変更箇所 |", "|---|---|---|---|---|---|---|"]
    ch_by = {c["ledger_id"]: c for c in ch.get("items", [])}
    shown = set()
    for it in tri.get("items", []):
        lid = it.get("ledger_id")
        if lid in shown:
            continue
        shown.add(lid)
        c = ch_by.get(lid, {})
        res = c.get("status") or STATUS_JA.get(issues.get(lid, {}).get("status"), "")
        what = c.get("summary") or it.get("plan") or it.get("rationale", "")
        L.append(f"| {lid} | {it['finding']} | {it.get('action')} | {it.get('core_risk')} | {res} | "
                 f"{md_cell(what, 160)} | {md_cell('; '.join(c.get('locations', [])), 60)} |")
    for lid, c in ch_by.items():
        if lid not in shown:
            L.append(f"| {lid} | （前回から） | — | {issues.get(lid, {}).get('core_risk', '')} | {c.get('status')} | "
                     f"{md_cell(c.get('summary', ''), 160)} | {md_cell('; '.join(c.get('locations', [])), 60)} |")
    L += ["", "## 3. 追加実験・追加分析", ""]
    exps = [load_json(e / "manifest.json") | {"_dir": e.name} for e in exp_dirs(ws)]
    exps = [e for e in exps if e.get("iteration") == n]
    if exps:
        L += ["| ID | 種類 | 課題 | 状態 | 結果の向き | 要約 | 本文への反映 |", "|---|---|---|---|---|---|---|"]
        for e in exps:
            L.append(f"| [{e['id']}](../../experiments/{e['_dir']}/) | {e.get('kind')} | {','.join(e.get('issues', []))} | "
                     f"{e.get('status')} | {e.get('outcome') or '—'} | {md_cell(e.get('summary', ''), 160)} | "
                     f"{md_cell('; '.join(e.get('integrated_into', [])), 60) or '—'} |")
    else:
        L.append("（なし）")
    L += ["", "## 4. 論文の変更箇所", ""]
    stats = diff_stats(d / "output" / "changes.diff")
    if stats:
        L += [f"- `{f}`: +{p} −{q}" for f, (p, q) in stats.items()]
        L.append(f"- 差分: `iterations/it{n:02d}/output/changes.diff`")
    else:
        L.append("（差分なし）")
    if ch.get("claim_changes"):
        L += ["", "### 主張の変更（scientific core の範囲内）", "", "| 主張 | 変更前 | 変更後 | 理由 | 課題 |", "|---|---|---|---|---|"]
        for cc in ch["claim_changes"]:
            L.append(f"| {cc['claim']} | {md_cell(cc['before'], 80)} | {md_cell(cc['after'], 80)} | "
                     f"{md_cell(cc['reason'], 80)} | {cc.get('issue', '')} |")
    if ch.get("other_changes"):
        L += ["", "### 指摘に紐づかない変更", ""] + [f"- {md_cell(s)}" for s in ch["other_changes"]]
    if (d / "provenance.md").exists():
        first = [ln for ln in (d / "provenance.md").read_text(encoding="utf-8").splitlines() if ln.startswith("- ")][:3]
        L += ["", "### 出所検査（provenance.md）", ""] + first
    L += ["", "## 5. 健全性監査", ""]
    if au:
        L.append(f"- 判定: **{au.get('verdict')}**")
        for c in au.get("checks", []):
            L.append(f"- {c.get('name')}: {c.get('result')} — {md_cell(c.get('notes', ''), 200)}")
        for f in au.get("required_fixes", []):
            L.append(f"- 修正 {f.get('id')}: {md_cell(f.get('problem', ''), 120)} → {'適用済' if f.get('applied') else '未適用'}")
        for rr in au.get("rebuttal_reviews", []):
            L.append(f"- 反論の検証 {rr.get('ledger_id')}: {'妥当' if rr.get('upheld') else '不採用（再対応）'} — "
                     f"{md_cell(rr.get('reason', ''), 120)}")
    else:
        L.append("（未実施）")
    L += ["", "## 6. 未解決事項（この反復の終了時点）", ""]
    unresolved = [(k, x) for k, x in issues.items() if x["status"] not in CLOSED and x["status"] not in ("addressed",)]
    if unresolved:
        L += ["| 課題 | 重大度 | 状態 | 内容 | 次の一手 |", "|---|---|---|---|---|"]
        for k, x in sorted(unresolved, key=lambda kv: (RANK.get(kv[1].get("type"), 9), kv[0])):
            if x["status"] == "needs_human":
                nxt_step = x.get("human_question", "")
            elif x["status"] == "kept_by_human":
                nxt_step = "人間の判断: " + (x.get("human") or {}).get("note", "")
            elif x["status"] == "rebutted":
                nxt_step = "反論: " + x.get("rationale", "")
            else:
                nxt_step = x.get("plan") or x.get("rationale", "")
            L.append(f"| {k} | {x.get('type')} | {STATUS_JA.get(x['status'], x['status'])} | {md_cell(x['title'], 80)} | "
                     f"{md_cell(nxt_step, 120)} |")
    else:
        L.append("（なし）")
    dec = [x for x in state.get("decisions", []) if x.get("at", "") >= min(
        (p["start"] for p in state["phases"] if p["it"] == n), default="9999")]
    if dec:
        L += ["", "## 7. 人間の判断", ""] + [f"- {x['issue']}: {x['choice']} — {md_cell(x.get('note', ''), 150)}" for x in dec]
    (d / "iteration_log.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {d / 'iteration_log.md'}")


# ---------------------------------------------------------------- status / convergence

def phase_durations(state, phase):
    per_it = {}
    for ph in state["phases"]:
        if ph["phase"] == phase and ph["end"]:
            per_it[ph["it"]] = per_it.get(ph["it"], 0) + (parse_t(ph["end"]) - parse_t(ph["start"])).total_seconds() / 60
    return list(per_it.values())


def time_plan(cfg, state, t=None):
    """Deadlines derived from the budget. None when there is no time limit."""
    if not state.get("deadline"):
        return None
    t = t or now()
    dl = parse_t(state["deadline"])
    reviews = phase_durations(state, "review")
    review_est = sum(reviews) / len(reviews) if reviews else REVIEW_MIN.get(cfg.get("depth"), 45)
    revise_by = dl - dt.timedelta(minutes=review_est + WRAP_MIN + FINAL_MIN)
    return {"deadline": dl, "left": (dl - t).total_seconds() / 60, "review_est": review_est,
            "review_timed": bool(reviews), "revise_by": revise_by,
            "experiments_by": revise_by - dt.timedelta(minutes=INTEGRATE_MIN),
            "review_start_by": dl - dt.timedelta(minutes=review_est + FINAL_MIN),
            "revise_window": (revise_by - t).total_seconds() / 60}


def best_iteration(metrics):
    if not metrics:
        return None
    return min(metrics, key=lambda k: (metrics[k]["major"], metrics[k]["W"], -int(k)))


def decide_next(ws, cfg, state, ledger):
    ms = state["metrics"]
    tp = time_plan(cfg, state)
    if not ms:
        return "CONTINUE", "no review ingested yet — run iteration 1"
    its = sorted(int(k) for k in ms)
    n = its[-1]
    m = ms[str(n)]
    # promoted but not yet reviewed: only the time can stop us before the next review
    if (itdir(ws, n + 1) / "input" / "paper.pdf").exists():
        started = any(ph["it"] == n + 1 and ph["phase"] == "review" for ph in state["phases"])
        if started:
            return "CONTINUE", f"finish the review of it{n + 1:02d} that is in progress"
        if tp and now() > tp["review_start_by"]:
            return "STOP", (f"time: {max(tp['left'], 0):.0f} min left < one more review (~{tp['review_est']:.0f} min) + wrap-up (~{FINAL_MIN} min) — "
                            f"deliver the last reviewed version; the it{n:02d} revision stays unreviewed")
        return "CONTINUE", f"run the review of it{n + 1:02d}"
    if m["major"] == 0:
        return "STOP", f"converged: no Major finding in it{n:02d}"
    live = [x for x in ledger["issues"].values() if x.get("last_seen") == n and x.get("type") == "major"]
    actionable = [x for x in live if x["status"] not in BLOCKED | CLOSED]
    if not actionable:
        return "STOP", (f"blocked: all {m['major']} Major finding(s) of it{n:02d} need a human decision, author "
                        f"resources or are rebutted — nothing left the loop may change on its own")

    def progress(k):
        a, b = ms[str(k - 1)], ms[str(k)]
        return b["major"] < a["major"] or b["W"] <= 0.9 * a["W"]

    if n >= 3 and str(n - 1) in ms and str(n - 2) in ms and not progress(n) and not progress(n - 1):
        return "STOP", f"plateau: no meaningful improvement in it{n - 1:02d} and it{n:02d} (Major not down, W down <10%)"
    if n >= cfg["max_iter"]:
        return "STOP", f"max iterations reached ({cfg['max_iter']})"
    if tp and tp["revise_window"] < MIN_REVISE:
        return "STOP", (f"time: {max(tp['left'], 0):.0f} min left — not enough for a revision (≥{MIN_REVISE} min) "
                        f"plus build/audit (~{WRAP_MIN} min) and another review (~{tp['review_est']:.0f} min)")
    return "CONTINUE", f"{len(actionable)} actionable Major issue(s) remain"


def cmd_status(a):
    ws, cfg, state, ledger = ctx(a.ws)
    t = now()
    print(f"review2revise-loop: {cfg['venue']}   status {state['status']}"
          + (f" ({state['finish_reason']})" if state.get("finish_reason") else ""))
    el = t - parse_t(state["started"])
    line = f"elapsed {fmt_td(el)}"
    if state.get("deadline"):
        line += f"   deadline {parse_t(state['deadline']):%m-%d %H:%M}   remaining {fmt_td(max(parse_t(state['deadline']) - t, dt.timedelta(0)))}"
    print(line + f"   max_iter {cfg['max_iter']}   depth {cfg['depth']}   experiments {cfg['experiments']}")
    tp = time_plan(cfg, state, t)
    if tp and state["status"] != "finished":
        guess = "" if tp["review_timed"] else " (first guess for this depth)"
        print(f"time plan: revise by {tp['revise_by']:%H:%M}   experiments by {tp['experiments_by']:%H:%M}   "
              f"start the next review by {tp['review_start_by']:%H:%M}   (one review ~{tp['review_est']:.0f} min{guess})")
        if tp["left"] <= 0:
            print("TIME OVER: the deadline has passed — start nothing new; finish with the last reviewed version")
        elif t > tp["revise_by"]:
            print("TIME: past revise-by — start no new edits or experiments; build, audit and promote now")
    ms = state["metrics"]
    if ms:
        print(" it   Major(deep/venue)  actionable  blocked  new  Minor  Sugg   W   resolved  reopened")
        for k in sorted(ms, key=int):
            m = ms[k]
            print(f" {int(k):02d}   {m['major']:>3} ({m['major_deep']}/{m['major_venue']})       {m['major_actionable']:>3}"
                  f"        {m['major_blocked']:>3}   {m['new_major']:>3}  {m['minor']:>4}  {m['suggestion']:>4}  {m['W']:>3}"
                  f"     {m['resolved']:>3}      {m['reopened']:>3}")
        ks = sorted(ms, key=int)
        if len(ks) >= 2:
            a_, b_ = ms[ks[-2]], ms[ks[-1]]
            if b_["W"] > a_["W"] or b_["new_major"]:
                print(f"REGRESSION: it{int(ks[-1]):02d} is worse than it{int(ks[-2]):02d} or has new Major findings "
                      f"({b_['new_major']}) — check whether the last revision caused them")
        print(f"BEST: it{int(best_iteration(ms)):02d} (fewest Major, then lowest W)")
    st = Counter(x["status"] for x in ledger["issues"].values())
    if st:
        print("issues: " + ", ".join(f"{k} {v}" for k, v in sorted(st.items())))
    pending = [k for k, x in ledger["issues"].items() if x["status"] == "needs_human" and decision_of(x) != "defer"]
    if pending:
        print(f"ASK HUMAN: {', '.join(pending)}")
    if state["status"] == "finished":
        print("NEXT: DONE")
        return
    verdict, why = decide_next(ws, cfg, state, ledger)
    print(f"NEXT: {verdict} — {why}")


# ---------------------------------------------------------------- summary / finish

def cmd_summary(a):
    ws, cfg, state, ledger = ctx(a.ws)
    issues = ledger["issues"]
    write_human_decisions(ws, ledger)
    L = [f"# 課題台帳 — {cfg['venue']}", "", "| 課題 | 重大度 | 出所 | 状態 | 初出 | 最終指摘 | 再発 | 内容 | 実験 |",
         "|---|---|---|---|---|---|---|---|---|"]
    for k, x in sorted(issues.items(), key=lambda kv: (RANK.get(kv[1].get("type"), 9), kv[0])):
        L.append(f"| {k} | {x.get('type')} | {x.get('origin')} | {STATUS_JA.get(x['status'], x['status'])} | "
                 f"it{x['first_seen']:02d} | it{x.get('last_seen', x['first_seen']):02d} | {x.get('reopened', 0)} | "
                 f"{md_cell(x['title'], 90)} | {','.join(x.get('experiments', []))} |")
    (ws / "ledger.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    ms = state["metrics"]
    P = [f"# 改善の推移 — {cfg['venue']}", "", "| 反復 | Major | うち投稿先 | 対応可能 | 判断待ち等 | 新規Major | Minor | Suggestion | W | 解決 | 再発 |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for k in sorted(ms, key=int):
        m = ms[k]
        P.append(f"| it{int(k):02d} | {m['major']} | {m['major_venue']} | {m['major_actionable']} | {m['major_blocked']} | "
                 f"{m['new_major']} | {m['minor']} | {m['suggestion']} | {m['W']} | {m['resolved']} | {m['reopened']} |")
    P += ["", "W = 3 × Major + Minor（収束判定に使う重み付きの指摘数）"]
    (ws / "progress.md").write_text("\n".join(P) + "\n", encoding="utf-8")
    R = [f"# Response to reviewers — {cfg['venue']}", "",
         "各課題について、反復ごとの対応を記録したもの。投稿時の response letter の下書きとして使う（AI による記録。内容は著者が確認すること）。", ""]
    for k, x in sorted(issues.items(), key=lambda kv: (RANK.get(kv[1].get("type"), 9), kv[0])):
        if not x.get("resolution") and x["status"] not in BLOCKED:
            continue
        R += [f"## {k} [{x.get('type')}] {x['title']}", "", f"- 状態: {STATUS_JA.get(x['status'], x['status'])}"]
        for h in x.get("history", [])[:1]:
            R.append(f"- 初出: it{h['it']:02d} {h['finding']}（{h['location']}）")
        for r in x.get("resolution", []):
            R.append(f"- it{r['it']:02d} {r['status']}: {r.get('response') or r['summary']}"
                     + (f"（変更箇所: {', '.join(r['locations'])}）" if r.get("locations") else "")
                     + (f"（実験: {', '.join(r['experiments'])}）" if r.get("experiments") else ""))
        if x["status"] == "rebutted" and x.get("rationale"):
            R.append(f"- 反論の根拠: {x['rationale']}")
        if x.get("human"):
            R.append(f"- 人間の判断: {x['human']['choice']} — {x['human'].get('note', '')}")
        R.append("")
    (ws / "response_letter.md").write_text("\n".join(R) + "\n", encoding="utf-8")
    T = [f"# 著者の作業が必要な事項 — {cfg['venue']}", "",
         "ループに無い資源・情報が必要なもの。本文の該当箇所には [AUTHOR TODO] を置いている。", ""]
    todo = [(k, x) for k, x in issues.items() if x["status"] == "needs_author"]
    for k, x in sorted(todo, key=lambda kv: (RANK.get(kv[1].get("type"), 9), kv[0])):
        T += [f"## {k} [{x.get('type')}] {x['title']}", "", f"- 必要なこと: {x.get('plan') or x.get('rationale', '')}"]
        for r in x.get("resolution", [])[-1:]:
            T.append(f"- 現状: {r['summary']}" + (f"（{', '.join(r['locations'])}）" if r.get("locations") else ""))
        T.append("")
    designs = []
    for e in exp_dirs(ws):
        man = load_json(e / "manifest.json")
        if man.get("status") in ("needs_author", "planned", "registered"):
            designs.append(f"- {man['id']} {man['slug']}（課題 {', '.join(man.get('issues', []))}）: "
                           f"`experiments/{e.name}/protocol.md` — {man.get('summary') or man.get('status')}")
    if designs:
        T += ["## 設計済みで未実行の実験", ""] + designs + [""]
    if not todo and not designs:
        T.append("（なし）")
    (ws / "author_todo.md").write_text("\n".join(T) + "\n", encoding="utf-8")
    print(f"wrote ledger.md ({len(issues)} issues), progress.md ({len(ms)} iterations), response_letter.md, "
          f"human_decisions.md, author_todo.md ({len(todo)} issue(s), {len(designs)} experiment design(s))")


def cmd_finish(a):
    ws, cfg, state, ledger = ctx(a.ws)
    ms = state["metrics"]
    best = str(a.pick) if a.pick else best_iteration(ms)
    latest = max(ms, key=int) if ms else None
    state.update({"status": "finished", "finish_reason": a.reason, "finished": iso(now()),
                  "deliverable_it": int(best) if best else None})
    save_json(ws / "state.json", state)
    if not best:
        print("finished (no review was completed)")
        return
    inp = itdir(ws, int(best)) / "input"
    stem = stem_of(cfg)
    if int(best) > 1 and (inp / "paper.pdf").exists():
        shutil.copy2(inp / "paper.pdf", ws / f"{stem}_revised.pdf")
        if (inp / "src").exists():
            shutil.rmtree(ws / "final_src", ignore_errors=True)
            shutil.copytree(inp / "src", ws / "final_src")
        print(f"deliverable: it{int(best):02d}/input -> {ws / (stem + '_revised.pdf')}, {ws / 'final_src'}")
    else:
        print("deliverable: the original manuscript (no revised version scored better)")
    unrev = itdir(ws, int(latest)) / "output" / "paper.pdf" if latest else None
    if unrev and unrev.exists():
        shutil.copy2(unrev, ws / f"{stem}_revised_unreviewed.pdf")
        state["unreviewed_it"] = int(latest)
        save_json(ws / "state.json", state)
        print(f"unreviewed: the it{int(latest):02d} revision was not reviewed (stopped before the next review) -> "
              f"{ws / (stem + '_revised_unreviewed.pdf')} — say so in final_report.md")
    if latest and latest != best:
        print(f"note: the latest reviewed version is it{int(latest):02d}; it{int(best):02d} scored better "
              f"(Major {ms[best]['major']} vs {ms[latest]['major']}, W {ms[best]['W']} vs {ms[latest]['W']}). "
              f"Explain the choice in final_report.md")
    print(f"finished: {a.reason}")


def cmd_limits(a):
    ws, cfg, state, _ = ctx(a.ws)
    if a.max_iter:
        cfg["max_iter"] = a.max_iter
    if a.no_deadline:
        state["deadline"], cfg["hours"] = None, None
    elif a.hours:
        state["deadline"] = iso(parse_t(state["started"]) + dt.timedelta(hours=a.hours))
        cfg["hours"] = a.hours
    elif a.extend:
        base = parse_t(state["deadline"]) if state.get("deadline") else now()
        state["deadline"] = iso(base + dt.timedelta(hours=a.extend))
        start = parse_t(state["started"])
        cfg["hours"] = round((parse_t(state["deadline"]) - start).total_seconds() / 3600, 2)
    save_json(ws / "config.json", cfg)
    save_json(ws / "state.json", state)
    print(f"max_iter {cfg['max_iter']}   deadline {state['deadline'] or 'none'}")


# ---------------------------------------------------------------- main

def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init")
    s.add_argument("paper")
    s.add_argument("--venue", required=True)
    s.add_argument("--ws")
    s.add_argument("--max-iter", type=int, default=5)
    s.add_argument("--hours", type=float)
    s.add_argument("--depth", choices=DEPTHS, default="standard")
    s.add_argument("--experiments", choices=EXP_MODES, default="design")
    s.add_argument("--code", action="append", default=[])
    s.add_argument("--data", action="append", default=[])
    s.add_argument("--exp-budget-min", type=int, default=60)
    s.add_argument("--lang", choices=("ja", "en"), default="ja")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("locate")
    s.add_argument("--hint")
    s.set_defaults(fn=cmd_locate)

    s = sub.add_parser("baseline")
    s.add_argument("ws")
    s.add_argument("--pdf")
    s.add_argument("--main", help="main source file, relative to <ws>/src (e.g. main.tex)")
    s.add_argument("--src-only", action="store_true")
    s.set_defaults(fn=cmd_baseline)

    for name in ("start", "end"):
        s = sub.add_parser(name)
        s.add_argument("ws")
        s.add_argument("--it", type=int, default=0)
        s.add_argument("--phase", required=True)
        s.set_defaults(fn=lambda a, w=name: cmd_phase(a, w))

    for name, fn in (("ingest", cmd_ingest), ("changes", cmd_changes), ("provenance", cmd_provenance),
                     ("audit", cmd_audit), ("promote", cmd_promote), ("log", cmd_log)):
        s = sub.add_parser(name)
        s.add_argument("ws")
        s.add_argument("--it", type=int, required=True)
        s.set_defaults(fn=fn)

    s = sub.add_parser("decide")
    s.add_argument("ws")
    s.add_argument("--issue", required=True)
    s.add_argument("--choice", choices=("approve", "reject", "defer"), required=True)
    s.add_argument("--action", choices=sorted(ACTIONABLE), default="edit")
    s.add_argument("--note")
    s.set_defaults(fn=cmd_decide)

    s = sub.add_parser("exp-new")
    s.add_argument("ws")
    s.add_argument("--it", type=int, required=True)
    s.add_argument("--slug", required=True)
    s.add_argument("--issues", required=True)
    s.add_argument("--kind", choices=EXP_KINDS, default="experiment")
    s.set_defaults(fn=cmd_exp_new)

    s = sub.add_parser("exp-register")
    s.add_argument("ws")
    s.add_argument("exp")
    s.set_defaults(fn=cmd_exp_register)

    s = sub.add_parser("exp-check")
    s.add_argument("ws")
    s.add_argument("--it", type=int)
    s.set_defaults(fn=cmd_exp_check)

    s = sub.add_parser("venue-check")
    s.add_argument("ws")
    s.add_argument("--it", type=int, required=True)
    s.add_argument("--which", choices=("input", "output"), default="output")
    s.set_defaults(fn=cmd_venue_check)

    for name, fn in (("status", cmd_status), ("summary", cmd_summary)):
        s = sub.add_parser(name)
        s.add_argument("ws")
        s.set_defaults(fn=fn)

    s = sub.add_parser("limits")
    s.add_argument("ws")
    s.add_argument("--max-iter", type=int)
    g = s.add_mutually_exclusive_group()
    g.add_argument("--hours", type=float, help="total budget counted from the start of the loop")
    g.add_argument("--extend", type=float, help="add this many hours to the current deadline")
    g.add_argument("--no-deadline", action="store_true")
    s.set_defaults(fn=cmd_limits)

    s = sub.add_parser("finish")
    s.add_argument("ws")
    s.add_argument("--reason", required=True)
    s.add_argument("--pick", type=int, help="deliver this iteration's input version instead of the best-scoring one")
    s.set_defaults(fn=cmd_finish)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
