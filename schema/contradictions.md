# Schema — Contradiction detection & resolution (detail)

> **Loaded on demand.** The lean core `CLAUDE.md` routes here via its Workflow router; read
> this file in full before scanning for, flagging, or resolving contradictions. Cross-cutting invariants and the Hard Rules live in `CLAUDE.md`.

---

## Contradiction detection and resolution

Contradictions are a first-class concern. The wiki must actively find, record, and surface them —
not just catch them passively during lint. An undetected contradiction is worse than a gap,
because it produces confident wrong answers.

> **Optional tooling.** A portable, stdlib-only `tools/contradiction_qa.py` automates the
> deterministic parts of this section: it scans every `Status: Unresolved` marker across `wiki/**`,
> classifies each by severity (hard vs soft/scope), and builds the soft/scope aging report. Run
> `python tools/contradiction_qa.py --root .` at lint time (or have the agent run it) — it is dormant
> until run and needs no email/scheduler setup. It only **detects and reports**; the plausibility
> assessment and the resolution decision stay the human judgment described below.

### When to check for contradictions

- **During every ingest** (the Ingest workflow's per-entity step — `schema/ingest.md`): every time an existing page is updated, compare the incoming claim against what the page already says. If they conflict, do not silently overwrite — flag the contradiction immediately.
- **During every query that combines two or more pages**: before synthesizing, check whether the pages being combined make compatible claims. If not, surface the conflict to the user rather than picking a side.
- **During lint**: sweep all pages for internal consistency as a backstop.

### How to flag a contradiction

When a contradiction is detected:

1. **Produce an LLM assessment** of the discrepancy. Analyze both claims against general knowledge of related facts and state which claim is more plausible and why, with a confidence qualifier. Example: "Based on general knowledge of related facts, claim A is far more plausible than claim B because [reasoning]." This assessment is advisory input for the user — it is never grounds for silently resolving the conflict. The assessment must always record the exact model name/version that produced it and a full timestamp, because assessment quality depends on which model performed the analysis.

2. **Record it on both affected pages** under `## Contradictions flagged`:
   - Name both source documents.
   - State exactly what each source says.
   - Include the LLM assessment with model name and timestamp.
   - Add a `Contradiction severity: hard | soft | scope` line — exactly one severity token from the
     severity table, machine-readable. Any automation that gates on severity keys off this token, so it
     is required, not optional; do not leave severity expressed only in prose.
   - Add a `Last reviewed: [model], [timestamp]` line — equal to the assessment timestamp at first
     flagging, then bumped each time the contradiction is re-examined (see *Aging and revisiting soft
     contradictions*). Aging is measured by *time since last review*, not time since first flagged.
   - Set the status to `Unresolved — flagged for user review`.

3. **Record it in `log.md`** immediately:
   ```
   ## [YYYY-MM-DD HH:mm:ss] contradiction | [Page title]
   Source A (raw/filename-a.md): "[exact claim from A]"
   Source B (raw/filename-b.md): "[exact claim from B]"
   LLM assessment ([model name/version]): [short plausibility analysis with reasoning]
   Contradiction severity: hard | soft | scope
   Last reviewed: [model name/version], [YYYY-MM-DD HH:mm:ss]
   Status: Unresolved — flagged for user review
   ```

4. **Notify the user** in the current session. Do not silently resolve by choosing one source. Present both sides clearly, include the LLM assessment as advisory input, and ask the user to review.

### Contradiction severity levels

| Severity | Description | Action |
|----------|-------------|--------|
| **Hard** | Two claims that cannot both be true under any interpretation | Flag immediately. Do not synthesize until resolved. |
| **Soft** | Two claims that seem to conflict but may be compatible with added context | Flag and note the possible reconciliation. Proceed with synthesis but mark the output as tentative. |
| **Scope mismatch** | One source is more general; the other is more specific | Keep both. Document the scope difference on each page. This is not a true contradiction but must be recorded clearly. |

**Always record the chosen severity as the machine-readable `Contradiction severity: hard | soft | scope`
line** on the flagged contradiction (see `schema/page-format.md` and the flagging protocol above) — `scope` uses
the `scope` token. The severity is not just advisory prose: any automation that gates on contradictions
acts on it (e.g. holding a commit for human review on `hard` while auto-accepting `soft`/`scope` with an
on-page flag), so a severity left implicit in prose can be misread. One explicit token per contradiction
makes the decision deterministic.

### How to assist with resolution

When the user is ready to resolve a contradiction:

1. Show both conflicting claims side by side with their source documents.
2. Present the recorded LLM assessment (with its model name and timestamp). If the current session runs a different model than the one that produced the recorded assessment, offer to re-run the analysis with the current model.
3. Note which source is more recent, more authoritative, or more specific — if determinable.
4. Ask the user which claim to keep, or whether both can be true under different conditions.
5. Update both affected pages and the log entry with the resolution and the reason.
6. If both claims can coexist (e.g., true under different conditions), document the conditions on the page — do not discard a claim when its scope can be preserved.

### Aging and revisiting soft contradictions

`hard` contradictions are gated and resolved promptly, so they do not linger. `soft` and `scope` ones
are recorded as **tentative** ("may be compatible with added context") and then proceed — so without a
revisit mechanism they **accumulate silently**, and the synthesis quietly rests on provisional ground
nobody re-examines. Two complementary triggers keep them honest:

**1. Event-driven revisit (related evidence arrives).** A `soft`/`scope` contradiction is provisional
*pending more context*, and new ingestion is that context arriving. Whenever a reasoning pass — an
ingest contradiction-scan, or the scoped lint of a changed neighbourhood (see `schema/lint.md`'s
*Scope* rule) — covers a page carrying an unresolved or acknowledged contradiction, **re-assess it
against the new material** and update its `Last reviewed:` line. Outcomes honour Hard rule 7 (in `CLAUDE.md`; never
silently resolve):
- *Still tentative* → bump `Last reviewed:` (`unchanged`); no human needed.
- *Now hard* → **escalate**: set `Contradiction severity:` to `hard`, raising it to the human gate.
  Escalating toward review is always safe to do automatically; de-escalating is not.
- *Now reconcilable* → **propose** the resolution to the user — resolution stays a human decision.

**2. Time-driven aging (no evidence arrives).** Some contradictions sit on pages no new source touches,
so the event trigger never fires. A periodic **aging report** (where an automated pipeline exists it
owns this; otherwise it is part of a manual lint) lists open `soft`/`scope` contradictions
**oldest-`Last reviewed:` first**, and **escalates to a forced human decision** any that stay
`Unresolved` *and* un-reviewed past a threshold (e.g. ~90 days, or N related ingests with no movement),
so nothing rots in limbo.

**The `Acknowledged` state — parking a reviewed contradiction.** Many soft contradictions are
legitimately two compatible framings that should *both* stand permanently; forcing them to "resolve" is
wrong. When the user has reviewed one and accepts it as tentative-but-fine, set its status to
`Acknowledged — accepted as tentative (reviewed [ts])`. An acknowledged contradiction stays visible on
the page but drops out of the "needs attention" aging report, keeping the report signal-rich instead of
re-nagging decisions already made. So three lifecycle states: **Unresolved** (never reviewed),
**Acknowledged** (reviewed, deliberately kept tentative), **Resolved** (decided).
