# Schema — Index & log formats (detail)

> **Loaded on demand.** The lean core `CLAUDE.md` routes here via its Workflow router; read
> this file in full before updating index.md or appending to log.md. Cross-cutting invariants and the Hard Rules live in `CLAUDE.md`.

---

## Index format

`index.md` is the LLM's map of the wiki. Update it on every ingest. Format:

```markdown
# [Project] Wiki — Index

## Concepts
- [[concept-page]] — one-line description
...

## Tools
- [[tool-page]] — one-line description
...

## Workflows
- [[workflow-page]] — one-line description
...

## Setup Guides
- [[setup-page]] — one-line description
...

## Causal Chains
- [[chain-page]] — [trigger] → [end state]
...

## Metaphors
- [[metaphor-page]] — one-line description
...
```

**Keep `index.md` compact, and do not whole-read it once it is large.** It is the query router, read
on every question, but it grows with the wiki — measured at ~30K tokens around 400 pages, larger than
this entire schema. Hold each entry to one tight line; at query time read only the relevant `## Type`
section(s) or `grep` for the slugs you need rather than loading the whole file. If one section itself
grows unwieldy, shard the index into per-type files the router links to.

---

## Log format

`log.md` is append-only. Never edit past entries. Add new entries at the bottom. **It also grows
without bound** — measured at ~320K tokens around 250 sources, far past a single context window — so
**never whole-read it.** To find recent activity (the last `lint |`/`compile` marker, the changed set,
candidate counts) use `git log`/`git diff`, or `grep`/`tail` only the trailing entries since the
relevant marker. You only ever need the tail; reading the whole file is unnecessary and, past a point,
impossible.

```markdown
## [YYYY-MM-DD HH:mm:ss] ingest | [Source Title]
Pages created: page-a, page-b, page-c
Pages updated: page-d (added causal links), page-e (revised definition)

## [YYYY-MM-DD HH:mm:ss] contradiction | [Page title]
Source A (raw/file-a.md): "[exact claim]"
Source B (raw/file-b.md): "[exact claim]"
LLM assessment ([model name/version]): [short plausibility analysis]
Contradiction severity: hard | soft | scope
Last reviewed: [model name/version], [YYYY-MM-DD HH:mm:ss]
Status: Unresolved — flagged for user review

## [YYYY-MM-DD HH:mm:ss] lint | Initial lint pass
Fixed: 2 orphan pages — added cross-links
Missing page created: page-f (referenced by page-g but absent)
EXTERNAL — unverified: 1 link flagged in chain-x for user review
```
