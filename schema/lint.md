# Schema — Lint workflow (detail)

> **Loaded on demand.** The lean core `CLAUDE.md` routes here via its Workflow router; read
> this file in full before running a lint pass. Cross-cutting invariants and the Hard Rules live in `CLAUDE.md`.

---

## Lint workflow

Run this workflow periodically (after every 3–4 ingests, or on request).

### Scope: incremental by default, full sweep on request

Lint splits into **cheap deterministic checks** and **expensive reasoning checks**, which scope
differently:

- **Deterministic, shell-based checks** (Orphan pages, Missing pages, Stale pending-pointers, Broken
  asset links, Unreferenced source images) are `grep`/`comm`/`find` passes with no context cost — run
  them **repo-wide every time**.
- **Reasoning-heavy checks** (Contradictions, Causal-chain gaps, Thin pages, Missing cross-references)
  cost LLM context, so by default scope them to the **changed neighbourhood**:
  1. **Changed set** — pages created/updated since the last lint. Derive it from `git diff --name-only`
     since the last lint commit (preferred), or by reading only the **tail** of `log.md` (the `ingest |`
     entries after the most recent `lint |` entry). **Never whole-read `log.md`** to find them — it is
     append-only and unbounded (see `schema/formats.md`).
  2. **Neighbourhood** — the changed set plus its **1st- and 2nd-degree `[[wikilink]]` neighbours**.
     This is the *only* surface where a newly-introduced contradiction, broken cross-reference, or
     causal gap can appear: a contradiction can exist only between claims about the **same entity or
     relationship**, and the wikilink graph already encodes which pages are related — two pages sharing
     no link and no concept cannot contradict each other. Re-reasoning the whole wiki for a small edit
     is O(n²) in page count and needlessly burns context as the wiki grows.

**Full reasoning sweep on request** — run the reasoning-heavy checks across the entire wiki when the
user asks for a "full lint", and as good practice at major milestones (e.g. after a large bootstrap
ingest) to catch non-local drift an incremental pass could miss. State which scope you ran.

Whenever a scoped pass covers a page carrying an **unresolved or acknowledged** contradiction, re-assess
that contradiction against the new material and update its `Last reviewed:` line — this is how soft
contradictions get revisited as related evidence arrives (see *Aging and revisiting soft contradictions*
in `schema/contradictions.md`).

Check for:
- **Orphan pages** — `wiki/**` pages with no inbound `[[wikilinks]]` from other pages. Scope this to the synthesized layer only: `raw/NNNN_…/article.md` source packages are **expected** orphans (provenance, not graph nodes — see *The source layer is provenance* in `CLAUDE.md`) and must **not** be flagged or "fixed" by wikilinking them.
- **Missing pages** — concepts or entities mentioned in `[[wikilinks]]` that have no file (ignore `[[raw/...]]` source pointers — they reference source files, not wiki pages)
- **Near-miss slugs** — an orphaned forward link `[[x]]` coexisting with an existing page that may be the same entity under a different name; flag the pair for user review rather than silently merging or renaming, and ensure the link site carries a pending-pointer if the pages are closely related
- **Stale pending-pointers** — `*(page pending — closest coverage: …)*` notes whose wanted slug now has a page; delete the parenthetical and keep the plain, now-resolving wikilink
- **Contradictions** — claims on two pages that cannot both be true; apply the full contradiction protocol (`schema/contradictions.md`)
- **Causal chain gaps** — `What causes this` / `What this causes` sections referencing a node with no wiki page; broken links in `causal-chain` pages
- **Missing direction labels** — causal links with no increase / decrease / activate / inhibit notation
- **EXTERNAL — unverified links** — causal chain links flagged as unverified; prompt user to review
- **Stale sources** — pages whose `sources` list a document that has since been updated in `raw/`
- **Broken asset links** — image links pointing into `raw/` that no longer resolve; borderline illustrative/decorative calls worth a second look
- **Unreferenced source images** — for each already-ingested `raw/NNNN_…/images/` folder, find images referenced **nowhere** in `wiki/` — neither embedded (`![](../../raw/…/images/foo.png)`) nor cited as a source path (`raw/…/images/foo.png`) for a synthesized claim. Each such image is one of two things: a correctly-skipped **decorative** image (fine), or an **illustrative** image whose information was dropped — typically when an ingest was interrupted before its image sweep finished. The lint pass MUST **open each flagged image** and decide: decorative → leave it; carries information absent from the wiki → synthesize it into the right page per Images & assets rule 4 in `schema/ingest.md` (citing the image path). This is the backstop that catches image-borne knowledge lost to an unfinished ingest. (An image whose info was synthesized to text but not embedded is **not** flagged — the source-path citation counts as a reference.)
- **Thin pages** — pages with a "What it is" but empty "How it works" or "When to use it"
- **Missing cross-references** — two pages about related topics with no link between them

For each issue found: fix it, note it in `log.md` as `## [YYYY-MM-DD HH:mm:ss] lint | [description of fix]`.
