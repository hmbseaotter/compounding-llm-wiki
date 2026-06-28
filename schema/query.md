# Schema — Query workflow (detail)

> **Loaded on demand.** The lean core `CLAUDE.md` routes here via its Workflow router; read
> this file in full before answering a reader question. Cross-cutting invariants and the Hard Rules live in `CLAUDE.md`.

---

## Query workflow

Run this workflow when answering a reader question.

1. **Find relevant pages via `index.md` — section-read or `grep` it, don't whole-read a large one.** `index.md` is sectioned by page type (`## Concepts`, `## Tools`, …); read only the `## Type` section(s) the question touches, or `grep` it for candidate slugs. On a mature wiki the full index runs to tens of thousands of tokens (see `schema/formats.md`), so whole-reading it on every query is the largest recurring query cost. Whole-read only a small/early index.
2. **Read the relevant pages** — do not go back to raw sources unless a page is missing entirely.
3. **If the question is causal:** apply the causal chain query patterns described in `schema/causal.md`.
4. **Before synthesizing from multiple pages:** check for contradictions between the pages being combined. If a contradiction exists, surface it to the user rather than silently picking one side.
5. **Synthesize the answer** in plain language, citing the wiki pages used.
6. **If the answer is a useful synthesis** not already captured in a single wiki page: file it as a new concept or workflow page and add it to `index.md`.

Good answers compound the wiki. Do not let useful synthesis disappear into chat history.
