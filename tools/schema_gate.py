#!/usr/bin/env python3
"""Schema load-gate hook for the LLM wiki template.

Enforces the on-demand schema split (see CLAUDE.md -> Workflow router): you cannot mutate a wiki
page, index.md, or log.md without having Read the matching schema/*.md file earlier in the SAME
session. This restores, as an enforced point-of-use check, the guarantee that auto-loading the whole
schema used to give for free.

Wired in .claude/settings.json as two hooks pointing at this one script:
  - PostToolUse  (matcher "Read"):           records a marker when a schema/*.md file is Read.
  - PreToolUse   (matcher "Write|Edit|...."): blocks the mutation if the required marker is absent,
                                              telling the model exactly which schema file to Read.

Marker store: <project>/.claude/.gate/<session_id>/loaded-<name> (gitignored runtime state).

Artifact-keyed, not workflow-keyed: the hook can see the file being written, not which workflow you
believe you are in, so it enforces the per-artifact floor:
  - any wiki/** page write          -> requires schema/page-format.md
  - a wiki/causal-chains/** write    -> additionally requires schema/causal.md
  - index.md / log.md write          -> requires schema/formats.md
The deeper workflow rules (ingest/lint/contradiction procedure) are routed by the core's Workflow
router but not hard-gated here, because they have no single artifact signature.

Fail-OPEN by design (workspace convention): any error, or a missing session id, -> allow. A wiki you
cannot edit is worse than a missed reminder, and lint is the backstop. (Contrast the global push-owner
guard, which fails CLOSED because a wrong-repo push is the irreversible danger.)
"""
import json
import os
import sys

MARKER_TO_FILE = {
    "page-format": "schema/page-format.md",
    "causal": "schema/causal.md",
    "formats": "schema/formats.md",
}


def project_dir():
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def gate_dir(session_id):
    return os.path.join(project_dir(), ".claude", ".gate", session_id or "nosession")


def required_markers(target):
    """Markers a write to `target` requires, keyed off the artifact path."""
    t = target.replace("\\", "/")
    if "wiki/causal-chains/" in t:
        return ["page-format", "causal"]
    if "/wiki/" in t or t.startswith("wiki/"):
        return ["page-format"]
    base = os.path.basename(t)
    if base in ("index.md", "log.md"):
        return ["formats"]
    return []


def main():
    data = json.loads(sys.stdin.read())
    event = data.get("hook_event_name", "")
    tool = data.get("tool_name", "")
    tin = data.get("tool_input") or {}
    fpath = tin.get("file_path") or tin.get("path") or ""
    sid = data.get("session_id", "")

    # PostToolUse on Read: record a marker for any schema/*.md that was read.
    if event == "PostToolUse" and tool == "Read":
        p = fpath.replace("\\", "/")
        if ("/schema/" in p or p.startswith("schema/")) and p.endswith(".md"):
            name = os.path.basename(p)[:-3]  # page-format.md -> page-format
            gd = gate_dir(sid)
            os.makedirs(gd, exist_ok=True)
            with open(os.path.join(gd, "loaded-" + name), "w") as fh:
                fh.write("1")
        return 0

    # PreToolUse on a mutating tool: block if a required schema file was not read this session.
    if event == "PreToolUse" and tool in ("Write", "Edit", "MultiEdit"):
        need = required_markers(fpath)
        if not need:
            return 0
        gd = gate_dir(sid)
        missing = [m for m in need if not os.path.exists(os.path.join(gd, "loaded-" + m))]
        if not missing:
            return 0
        files = ", ".join(MARKER_TO_FILE.get(m, "schema/%s.md" % m) for m in missing)
        reason = (
            "Schema load-gate: before writing %s you must Read %s in full this session "
            "(the wiki format rules live there, per CLAUDE.md -> Workflow router). "
            "Read it, then retry the edit." % (os.path.basename(fpath), files)
        )
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }
        print(json.dumps(out))
        return 0

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # fail OPEN
