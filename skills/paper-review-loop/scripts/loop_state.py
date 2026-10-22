#!/usr/bin/env python3
"""Clock and bookkeeping for the review -> revise -> rebuild loop.

Claude cannot perceive elapsed time, so every "is there time for another
cycle?" decision goes through `status`, which estimates the cost of the next
revise + re-review cycle from the phases measured so far.

  loop_state.py init    WS (--hours H | --minutes M | --review-only) [--paper PDF] [--venue TEXT] [--force]
  loop_state.py start   WS --round N --phase {setup,review,revise}
  loop_state.py end     WS --round N --phase {setup,review,revise}
  loop_state.py status  WS [--json]
  loop_state.py finish  WS --reason TEXT
  loop_state.py summary WS [--json]    # writes WS/issue_tracker.md from rounds/r*/issues.json
"""
import argparse
import json
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path

DEFAULT_REVIEW_MIN = 20   # used until a review has actually been timed
DEFAULT_REVISE_MIN = 20   # floor for the revise estimate until a revision has been timed
REVISE_PER_REVIEW = 2.0   # before that, a revision is assumed to take this many review-lengths
SAFETY = 1.15             # margin on the estimate for the next cycle
PHASES = ("setup", "review", "revise")
STATUS_LABEL = {
    "open": "未解決",
    "partially_resolved": "一部解決",
    "resolved": "解決",
    "needs_author": "著者対応待ち",
}


def now():
    return datetime.now().astimezone()


def iso(dt):
    return dt.isoformat(timespec="seconds")


def hm(td):
    secs = int(td.total_seconds())
    sign = "-" if secs < 0 else ""
    secs = abs(secs)
    return f"{sign}{secs // 3600}h{(secs % 3600) // 60:02d}m"


def clock(dt):
    return dt.strftime("%m-%d %H:%M")


def state_path(ws):
    return Path(ws) / "state.json"


def load(ws):
    p = state_path(ws)
    if not p.exists():
        sys.exit(f"state.json not found in {ws}. Run `init` first.")
    return json.loads(p.read_text(encoding="utf-8"))


def save(ws, st):
    p = state_path(ws)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def durations(st, phase):
    out = []
    for ph in st["phases"]:
        if ph["phase"] == phase and ph.get("end"):
            out.append(datetime.fromisoformat(ph["end"]) - datetime.fromisoformat(ph["start"]))
    return out


def mean_td(tds, default_min):
    if not tds:
        return timedelta(minutes=default_min)
    return timedelta(seconds=statistics.mean(td.total_seconds() for td in tds))


# ---------------------------------------------------------------- commands

def cmd_init(a):
    ws = Path(a.ws)
    ws.mkdir(parents=True, exist_ok=True)
    if state_path(ws).exists() and not a.force:
        st = load(ws)
        if st.get("status") == "running":
            sys.exit("A running loop already exists here (resume it, or pass --force to restart the clock).")
    t0 = now()
    if a.review_only:
        budget = timedelta(0)
    elif a.minutes is not None:
        budget = timedelta(minutes=a.minutes)
    elif a.hours is not None:
        budget = timedelta(hours=a.hours)
    else:
        sys.exit("Give --hours, --minutes or --review-only.")
    st = {
        "paper": a.paper,
        "venue": a.venue,
        "review_only": bool(a.review_only),
        "budget_minutes": round(budget.total_seconds() / 60, 1),
        "start": iso(t0),
        "deadline": iso(t0 + budget),
        "status": "running",
        "finish_reason": None,
        "phases": [],
    }
    save(ws, st)
    if a.review_only:
        print(f"Started (review-only mode) at {clock(t0)}")
    else:
        print(f"Started at {clock(t0)}; budget {hm(budget)}; deadline {clock(t0 + budget)}")


def cmd_start(a):
    st = load(a.ws)
    for ph in st["phases"]:
        if not ph.get("end"):
            print(f"warning: r{ph['round']:02d} {ph['phase']} was never ended; closing it now.")
            ph["end"] = iso(now())
    st["phases"].append({"round": a.round, "phase": a.phase, "start": iso(now()), "end": None})
    save(a.ws, st)
    print(f"r{a.round:02d} {a.phase} started at {clock(now())}")


def cmd_end(a):
    st = load(a.ws)
    for ph in reversed(st["phases"]):
        if ph["round"] == a.round and ph["phase"] == a.phase and not ph.get("end"):
            ph["end"] = iso(now())
            save(a.ws, st)
            took = datetime.fromisoformat(ph["end"]) - datetime.fromisoformat(ph["start"])
            print(f"r{a.round:02d} {a.phase} ended ({hm(took)})")
            return
    sys.exit(f"No open phase r{a.round:02d} {a.phase}.")


def compute_status(st):
    t = now()
    start = datetime.fromisoformat(st["start"])
    deadline = datetime.fromisoformat(st["deadline"])
    remaining = deadline - t
    reviews, revisions = durations(st, "review"), durations(st, "revise")
    est_review = mean_td(reviews, DEFAULT_REVIEW_MIN)
    est_revise = mean_td(revisions, max(DEFAULT_REVISE_MIN, REVISE_PER_REVIEW * est_review.total_seconds() / 60))
    need = (est_review + est_revise) * SAFETY
    open_phase = next((ph for ph in st["phases"] if not ph.get("end")), None)
    done_reviews = [ph["round"] for ph in st["phases"] if ph["phase"] == "review" and ph.get("end")]

    if st.get("status") == "finished":
        decision, reason = "FINISHED", st.get("finish_reason") or "finished"
    elif st.get("review_only"):
        decision = "STOP" if done_reviews else "CONTINUE"
        reason = "review-only mode" + (": the single review is done" if done_reviews else ": do the review")
    elif remaining.total_seconds() <= 0:
        decision, reason = "STOP", "deadline reached"
    elif remaining < need:
        decision, reason = "STOP", f"remaining {hm(remaining)} < ~{hm(need)} needed for revise + re-review"
    else:
        decision, reason = "CONTINUE", f"remaining {hm(remaining)} >= ~{hm(need)} needed for revise + re-review"

    return {
        "now": iso(t),
        "start": st["start"],
        "deadline": st["deadline"],
        "elapsed_min": round((t - start).total_seconds() / 60, 1),
        "remaining_min": round(remaining.total_seconds() / 60, 1),
        "reviews_done": len(done_reviews),
        "last_review_round": max(done_reviews) if done_reviews else None,
        "revisions_done": len(revisions),
        "est_review_min": round(est_review.total_seconds() / 60, 1),
        "est_revise_min": round(est_revise.total_seconds() / 60, 1),
        "next_cycle_need_min": round(need.total_seconds() / 60, 1),
        # A revision must finish by this time so the revised PDF still gets reviewed.
        "revise_by": iso(deadline - est_review * SAFETY),
        "in_progress": (f"r{open_phase['round']:02d} {open_phase['phase']}" if open_phase else None),
        "decision": decision,
        "reason": reason,
    }


def cmd_status(a):
    s = compute_status(load(a.ws))
    if a.json:
        print(json.dumps(s, ensure_ascii=False, indent=2))
        return
    dl = datetime.fromisoformat(s["deadline"])
    print(f"now        {clock(datetime.fromisoformat(s['now']))}")
    print(f"deadline   {clock(dl)}   elapsed {s['elapsed_min']:.0f}m   remaining {s['remaining_min']:.0f}m")
    print(f"done       reviews {s['reviews_done']} (last r{(s['last_review_round'] or 0):02d}), revisions {s['revisions_done']}")
    print(f"estimate   review ~{s['est_review_min']:.0f}m, revise ~{s['est_revise_min']:.0f}m, "
          f"next cycle ~{s['next_cycle_need_min']:.0f}m incl. margin")
    if s["in_progress"]:
        print(f"running    {s['in_progress']}")
    if s["decision"] == "CONTINUE" and s["reviews_done"]:
        print(f"revise by  {clock(datetime.fromisoformat(s['revise_by']))} (leaves time for the re-review)")
    print(f"NEXT: {s['decision']}  ({s['reason']})")


def cmd_finish(a):
    st = load(a.ws)
    for ph in st["phases"]:
        if not ph.get("end"):
            ph["end"] = iso(now())
    st["status"] = "finished"
    st["finish_reason"] = a.reason
    st["finished_at"] = iso(now())
    save(a.ws, st)
    used = datetime.fromisoformat(st["finished_at"]) - datetime.fromisoformat(st["start"])
    print(f"Finished: {a.reason} (used {hm(used)} of {st['budget_minutes']:.0f}m)")


def load_rounds(ws):
    rounds = []
    for d in sorted((Path(ws) / "rounds").glob("r*")):
        f = d / "issues.json"
        if f.exists():
            try:
                rounds.append((d.name, json.loads(f.read_text(encoding="utf-8"))))
            except json.JSONDecodeError as e:
                print(f"warning: {f} is not valid JSON ({e}); skipped", file=sys.stderr)
    return rounds


def cmd_summary(a):
    rounds = load_rounds(a.ws)
    if not rounds:
        sys.exit("No rounds/r*/issues.json yet.")
    rows, matrix, meta = [], {}, {}
    for name, data in rounds:
        r = data.get("rating", {})
        issues = data.get("issues", [])
        count = lambda sev, sts: sum(1 for i in issues if i.get("severity") == sev and i.get("status") in sts)
        rows.append({
            "round": name,
            "overall": r.get("overall"),
            "overall_label": r.get("overall_label", ""),
            "quality": r.get("quality"), "clarity": r.get("clarity"),
            "significance": r.get("significance"), "originality": r.get("originality"),
            "confidence": r.get("confidence"),
            # Waiting on the authors is still unresolved; it is broken out in its own column.
            "major_open": count("major", ("open", "partially_resolved", "needs_author")),
            "minor_open": count("minor", ("open", "partially_resolved", "needs_author")),
            "needs_author": sum(1 for i in issues if i.get("status") == "needs_author"),
            "resolved": sum(1 for i in issues if i.get("status") == "resolved"),
        })
        for i in issues:
            iid = i.get("id", "?")
            meta.setdefault(iid, i)
            meta[iid] = {**meta[iid], **{k: v for k, v in i.items() if v}}
            matrix.setdefault(iid, {})[name] = i.get("status", "open")

    if a.json:
        print(json.dumps({"rounds": rows, "issues": matrix}, ensure_ascii=False, indent=2))
        return

    def v(x):
        return "-" if x is None else str(x)

    names = [n for n, _ in rounds]
    out = ["# Issue tracker", "", "## 評価の推移", "",
           "| Round | Overall | Quality | Clarity | Significance | Originality | Confidence | Major 未解決 | Minor 未解決 | うち著者対応待ち | 解決済み |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        overall = v(r["overall"]) + (f" ({r['overall_label']})" if r["overall_label"] else "")
        out.append(f"| {r['round']} | {overall} | {v(r['quality'])} | {v(r['clarity'])} | {v(r['significance'])} | "
                   f"{v(r['originality'])} | {v(r['confidence'])} | {r['major_open']} | {r['minor_open']} | "
                   f"{r['needs_author']} | {r['resolved']} |")
    out += ["", "## 指摘ごとの状態", "",
            "| ID | 重大度 | カテゴリ | 概要 | 本文修正で対応可 | " + " | ".join(names) + " |",
            "|---|---|---|---|---|" + "---|" * len(names)]

    def key(iid):
        digits = "".join(ch for ch in iid if ch.isdigit())
        return (iid.rstrip("0123456789"), int(digits) if digits else 0)

    for iid in sorted(matrix, key=key):
        m = meta[iid]
        cells = [STATUS_LABEL.get(matrix[iid].get(n), matrix[iid].get(n, "")) if n in matrix[iid] else "" for n in names]
        title = str(m.get("title", "")).replace("|", "/")
        out.append(f"| {iid} | {m.get('severity', '')} | {m.get('category', '')} | {title} | "
                   f"{m.get('fixable_by_revision', '')} | " + " | ".join(cells) + " |")
    text = "\n".join(out) + "\n"
    (Path(a.ws) / "issue_tracker.md").write_text(text, encoding="utf-8")
    print(text)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init")
    s.add_argument("ws")
    s.add_argument("--hours", type=float)
    s.add_argument("--minutes", type=float)
    s.add_argument("--review-only", action="store_true")
    s.add_argument("--paper")
    s.add_argument("--venue")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_init)

    for name, fn in (("start", cmd_start), ("end", cmd_end)):
        s = sub.add_parser(name)
        s.add_argument("ws")
        s.add_argument("--round", type=int, required=True)
        s.add_argument("--phase", choices=PHASES, required=True)
        s.set_defaults(fn=fn)

    s = sub.add_parser("status")
    s.add_argument("ws")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("finish")
    s.add_argument("ws")
    s.add_argument("--reason", required=True)
    s.set_defaults(fn=cmd_finish)

    s = sub.add_parser("summary")
    s.add_argument("ws")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_summary)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
