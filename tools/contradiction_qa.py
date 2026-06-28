#!/usr/bin/env python3
"""contradiction_qa — portable, stdlib-only core for an llm-wiki's contradiction QA.

This is the shared, pipeline-independent heart of the wiki's contradiction handling: it reads the
`Status: Unresolved` markers the schema writes onto `wiki/**` pages, classifies each by severity
(hard vs soft/scope), and builds the soft/scope aging report. It does NOT email, commit, schedule,
or touch the network — those orchestration concerns stay in whatever caller you wrap it in. Two
example shells (both optional, both yours to write if you want Tier-2 automation):

  - an auto-ingest commit gate     imports scan_contradictions / split_severity to HOLD an automated
                                   commit on HARD contradictions (soft/scope proceed flagged).
  - a scheduled digest / "nag" job imports scan_contradictions / split_severity / aging_report /
                                   _age_days and adds only the email-send + state-write shell
                                   (cadence, dedupe, finalize).

Because it is pure stdlib and free of any orchestrator coupling, the same file drops unchanged into
the compounding-llm-wiki template and any other wiki: there, the Tier-1 CLI alone gives contradiction
QA with zero infrastructure (the agent or a human runs it at lint time).

Tier-1 CLI:
  python tools/contradiction_qa.py [--root .] [--aging-escalate-days 90]
    -> prints open contradictions by severity + the soft/scope aging report (oldest first).
       No email, no git, no scheduler.
"""
import argparse, datetime, os, re, sys

# Windows redirects stdout to a file as cp1252; the em-dash this CLI prints then raises
# UnicodeEncodeError. Force UTF-8 so the Tier-1 CLI can be safely redirected to a file anywhere.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Default wiki root = the parent of this file's tools/ dir. Holds for <wiki>/tools/contradiction_qa.py
# in every wiki, so callers that share the same tools/ dir (e.g. an ingest gate or a scheduled job) get the
# identical root they computed themselves, and the CLI can override it with --root.
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

UNRESOLVED = "Status: Unresolved"                          # the schema's contradiction gate marker

# ---- severity classification ----
# The schema defines severity levels: HARD (two claims that cannot both be true) must block; SOFT
# (seemingly conflicting but possibly compatible) and SCOPE-MISMATCH "proceed with synthesis, marked
# tentative". So the gate HOLDS the commit only on HARD contradictions; soft/scope are committed,
# flagged on-page, and surfaced for review at leisure.
#
# Severity is read in this order of trust (see _verdict):
#   1. The schema's deterministic `Contradiction severity: <soft|hard|scope>` token, if the ingest
#      emitted one (legacy `Classification:` is also accepted as an alias).
#   2. The model's PROSE verdict — "hard/soft contradiction" / "scope mismatch" — as written in the
#      `Status:` line (the terminal gate marker) and the assessment text. The schema's page format
#      does NOT mandate a `Classification:` field, so the verdict often lives only in this prose; an
#      earlier version keyed solely off `Classification:` and mis-held a correctly-labelled SOFT
#      contradiction as hard (thyroid-carb-restoration.md, 2026-06-20) — this is the fix.
#   3. Loose keyword hints, then a conservative default of HARD when nothing is classifiable (ask the
#      human rather than silently commit a possible real conflict).
# Only wiki/ pages are scanned (the gate surface); log.md is a record, so scanning it too double-counts.

SOFT_HINTS = ("scope mismatch", "scope difference", "scope gradient", "not a true contradiction")
HARD_HINTS = ("cannot both be true",)


def _verdict(text):
    """Map text to 'soft'/'hard' by its EXPLICIT severity verdict, or None if it states none.
    Reads the schema's `Contradiction severity:` field first (legacy `Classification:` accepted as an
    alias), then the prose verdict phrases ('hard/soft contradiction', 'scope mismatch'). Strips
    markdown emphasis so `**soft**` matches, and neutralises the negated form ('not a hard
    contradiction') so it can't read as hard."""
    t = text.lower().replace("*", "")
    for neg in ("not a hard contradiction", "isn't a hard contradiction", "is not a hard contradiction",
                "not a soft contradiction", "isn't a soft contradiction", "is not a soft contradiction"):
        t = t.replace(neg, "")
    m = re.search(r"(?:contradiction\s+severity|classification):\s*(soft|hard|scope)", t)
    if m:
        return "hard" if m.group(1) == "hard" else "soft"
    if "hard contradiction" in t:
        return "hard"
    if "soft contradiction" in t or "scope mismatch" in t or "scope contradiction" in t:
        return "soft"
    return None


_TS = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"


def _grab_ts(rx, text):
    """First 'YYYY-MM-DD HH:MM:SS' captured by rx in text, as a string, or None."""
    m = re.search(rx, text)
    return m.group(1) if m else None


def scan_contradictions(repo=None):
    """Return [{file, line, severity, last_reviewed, assessed}] for every `Status: Unresolved` marker
    in wiki/ pages. `last_reviewed`/`assessed` are the timestamp strings parsed from the bullet's
    `Last reviewed:` and `LLM assessment(...)` lines (or None) — consumed by the aging report. Only
    `Status: Unresolved` is matched, so `Acknowledged`/`Resolved` contradictions are excluded here.
    `repo` is the wiki root (defaults to this module's wiki); `wiki/` beneath it is scanned."""
    repo = repo or _REPO
    wiki = os.path.join(repo, "wiki")
    out = []
    for r, _, fs in os.walk(wiki):
        for fn in fs:
            if not fn.endswith(".md"):
                continue
            p = os.path.join(r, fn)
            try:
                lines = open(p, encoding="utf-8").read().splitlines()
            except OSError:
                continue
            for i, line in enumerate(lines):
                if UNRESOLVED not in line:
                    continue
                # context = this contradiction's whole bullet (from its "- " start up to the Status
                # line). Read the explicit verdict from the Status line FIRST (it is the model's
                # terminal call and the gate marker itself), then from the whole bullet (Classification
                # field or assessment prose), then loose hints, then the conservative HARD default.
                j = i
                while j > 0 and not lines[j].lstrip().startswith("- "):
                    j -= 1
                ctx = "\n".join(lines[j:i + 1]).lower().replace("*", "")
                sev = _verdict(line) or _verdict(ctx)
                if sev is None:
                    if any(h in ctx for h in HARD_HINTS):
                        sev = "hard"
                    elif any(h in ctx for h in SOFT_HINTS):
                        sev = "soft"
                    else:
                        sev = "hard"                      # unclassified -> conservative: block
                rel = os.path.relpath(p, repo).replace("\\", "/")
                out.append({"file": rel, "line": i + 1, "severity": sev,
                            "last_reviewed": _grab_ts(r"last reviewed:[^,\n]*,\s*(" + _TS + ")", ctx),
                            "assessed": _grab_ts(r"assessment\s*\([^,\n]*,\s*(" + _TS + ")", ctx)})
    return out


def split_severity(cons):
    return ([c for c in cons if c["severity"] == "hard"],
            [c for c in cons if c["severity"] != "hard"])


# ---- soft/scope aging ----

def _age_days(basis):
    if not basis:
        return None
    try:
        return (datetime.datetime.now() - datetime.datetime.strptime(basis, "%Y-%m-%d %H:%M:%S")).days
    except ValueError:
        return None


def aging_report(cons, escalate_days=90):
    """PURE builder for the soft/scope aging report (schema: 'Aging and revisiting soft contradictions').
    Lists OPEN soft/scope contradictions oldest-`Last reviewed:`-first and marks any past escalate_days
    as overdue. Returns a dict {soft_count, overdue_count, subject, body, rows}; subject/body are None
    when there are no open soft/scope items. Does NOT send, persist, or apply send-cadence — those
    (the send cadence, the email, the state write) stay in the scheduled job that wraps this."""
    soft = [c for c in cons if c["severity"] != "hard"]   # open soft/scope (all Unresolved by scan)
    if not soft:
        return {"soft_count": 0, "overdue_count": 0, "subject": None, "body": None, "rows": []}
    rows = [(_age_days(c.get("last_reviewed") or c.get("assessed")),
             c.get("last_reviewed") or c.get("assessed"), c) for c in soft]
    overdue = [r for r in rows if r[0] is not None and r[0] >= escalate_days]
    rows.sort(key=lambda r: (r[0] is not None, -(r[0] or 0)))   # unknown-age first, then oldest

    def fmt(r):
        age, basis, c = r
        age_s = f"{age}d" if age is not None else "age unknown"
        return f"  - [{c['severity']}] {c['file']}:{c['line']} — last reviewed {basis or '?'} ({age_s})"

    body = (f"Soft/scope contradiction aging report — {len(soft)} open (oldest first).\n"
            "These are tentative and non-blocking, but should be revisited so they do not rot.\n\n"
            + "\n".join(fmt(r) for r in rows))
    if overdue:
        body += (f"\n\nOVERDUE: {len(overdue)} past the {escalate_days}-day threshold — please "
                 "make a decision (resolve it, or park it as Acknowledged):\n"
                 + "\n".join(fmt(r) for r in overdue))
    body += ("\n\nOn each wiki page: resolve it, or park it with "
             "`Status: Acknowledged — accepted as tentative (reviewed <ts>)` so it stops appearing here.")
    subj = (f"[corpus-watch] soft-contradiction aging report — {len(soft)} open"
            + (f", {len(overdue)} OVERDUE" if overdue else ""))
    return {"soft_count": len(soft), "overdue_count": len(overdue),
            "subject": subj, "body": body, "rows": rows}


def main():
    ap = argparse.ArgumentParser(description="Report open wiki contradictions by severity + age (Tier 1).")
    ap.add_argument("--root", default=".", help="wiki root (the dir containing wiki/); default cwd")
    ap.add_argument("--aging-escalate-days", type=int, default=90,
                    help="open soft/scope older than this is flagged OVERDUE")
    a = ap.parse_args()
    repo = os.path.abspath(a.root)
    cons = scan_contradictions(repo)
    hard, soft = split_severity(cons)
    print(f"contradiction-qa | {repo} | {len(cons)} unresolved | {len(hard)} hard | {len(soft)} soft/scope")
    if hard:
        print("\nHARD (would block an auto-commit):")
        for c in hard:
            print(f"  - {c['file']}:{c['line']}")
    rep = aging_report(cons, a.aging_escalate_days)
    if rep["soft_count"]:
        print("\n" + rep["body"])


if __name__ == "__main__":
    main()
