# Schema — Ingest & source acquisition (detail)

> **Loaded on demand.** The lean core `CLAUDE.md` routes here via its Workflow router; read
> this file in full before acquiring a URL source or ingesting a raw source. Cross-cutting invariants and the Hard Rules live in `CLAUDE.md`.

---

## Source acquisition from URL

Run this workflow when the user provides a URL to add as a source (e.g. "add source <URL>"). It
automates what the manual route does by hand — download the page as markdown plus its images,
package them into a self-contained folder in `raw/`. The manual route (user saves the page
themselves and drops the folder into `raw/`) remains the documented fallback for anything the
automation cannot fetch: gated/paywalled pages, or no fetch engine available.

1. **Fetch the page as main-content markdown.** Current engine: Firecrawl CLI —
   `firecrawl scrape <URL> --only-main-content -f markdown -o <staging>/article.md`. The workflow
   is engine-agnostic: any fetcher that produces clean main-content markdown is acceptable; if no
   engine is available, say so and point the user to the manual fallback. Build the package in a
   staging location first — it moves into `raw/` only once finalized, and immutability begins at
   that moment.
2. **Download every referenced content image** into `images/` beside the markdown. Skip obvious
   non-content assets (tracking pixels, social/share buttons, comment-widget avatars). Do NOT
   judge illustrative vs decorative here — that judgment belongs to the ingest workflow; `raw/` is
   the archive, so keep everything that is part of the article.
3. **Rewrite image links** in the markdown to relative `images/<filename>` paths so the package is
   self-contained and portable, exactly like a manually added source.
4. **Record provenance** as frontmatter at the top of `article.md`: `source_url`, `retrieved`
   (YYYY-MM-DD HH:mm:ss), `engine` (tool + version). The archival copy is a snapshot of a live
   page that can change or vanish, so provenance must be captured at creation time. This is part
   of *creating* the source, not a modification of an immutable file.
5. **Package into `raw/`:** assign the next catalog ID `NNNN`, derive a kebab-case slug from the
   page title, move the staging folder to `raw/NNNN_<slug>/` (containing `article.md` + `images/`).
6. **QA-assess the fetched content** — read the markdown and check:
   - title and author present; content reads complete — no paywall stub or truncation (a gated
     post fetched without credentials typically ends abruptly at a subscribe prompt);
   - no leftover navigation, widget, or comment-section junk;
   - every rewritten image link resolves to a downloaded file; image count plausible vs the page.
7. **Append to `log.md`:** `## [YYYY-MM-DD HH:mm:ss] acquire | <URL> → raw/NNNN_<slug>/`, including
   the engine used and the QA result.
8. **Ask the user whether to ingest now, surfacing the QA findings** so the decision is informed.
   Acquisition never auto-triggers ingestion — a bad scrape must not flow into the wiki.

> **Paywalled pages — why a logged-in URL is not enough.** Access to subscriber-only content lives
> in the browser's session cookies, not in the URL: the same URL serves the full article to a
> logged-in browser and a public preview to everyone else. The fetch engine does not share the
> user's browser session, so it receives the preview. Out of scope for now; use the manual
> fallback (save the page from the logged-in browser, drop it into `raw/` per the standard
> workflow).

---

## Ingest workflow

Run this workflow when a new raw source is added or an existing source is updated.

1. **Read** the raw source document in full.
2. **Identify** all entities worth a wiki page:
   - Concepts (abstract ideas, named entities, domain terms)
   - Tools (named tools, integrations, systems, named interventions)
   - Workflows (repeatable processes with steps)
   - Setup guides (installation or configuration sequences)
   - Causal relationships (cause-effect links — see step 5)
   - Metaphors (named analogies used to explain a concept)
3. **Check orphaned forward links before naming any new page:**
   - Compute the wanted-slug list: every `[[wikilink]]` across `wiki/` and `index.md` that has no matching page file. Ignore `[[raw/...]]` source pointers — they reference source files, not wiki pages. This is one cheap shell pass (seconds, always ground truth — no separate index file is kept), e.g.:
     `comm -23 <(rg -oI '\[\[[^\]#|]+' wiki index.md | sed 's/^\[\[//' | sort -u) <(find wiki -name '*.md' -exec basename {} .md \; | sort -u)`
   - For each new entity that resembles a wanted slug, grep for that `[[slug]]` and **read the linking sentences in context** to recover what the original link meant.
   - Reuse the wanted slug **only if the new page is genuinely the same entity** the linking text refers to — not merely the same subject. Forward links target future pages about entities, never specific source documents, so any source that truly covers the entity may create the page; later sources then update that same page.
   - **When uncertain, do not claim the slug.** Create the page under its own natural name, and at each orphaned link site append a pending-pointer in this exact form: `[[wanted-slug]] *(page pending — closest coverage: [[new-page]])*`. Lint removes the pointer once the wanted page exists. A wrongly claimed slug is silent corruption — the link "works" but points at the wrong entity; a still-orphaned link is a visible, recoverable gap.
4. **For each entity:**
   - If no wiki page exists: create one using the page format (see `schema/page-format.md`).
   - If a page exists: read it, then update it — add new information, update `sources` and `last_updated` frontmatter.
   - **On every update, actively scan for contradictions** between the incoming source and what the page already says. See `schema/contradictions.md`. Do not silently overwrite — flag every conflict.
5. **Identify causal relationships:**
   - Scan for causal language: "causes," "leads to," "triggers," "results in," "inhibits," "suppresses," "increases," "decreases," "is associated with," "activates," "blocks," and domain-specific equivalents. Include cause-effect relationships depicted in kept images (diagram arrows, flow charts) — see Images and assets rule 3.
   - For each causal statement, identify the source node and target node. Record the direction of effect (increase / decrease / activate / inhibit / trigger / suppress / other).
   - Add or update `What causes this` and `What this causes` sections on the relevant concept pages.
   - If a chain of three or more links can be assembled (A → B → C or longer), create or update a `causal-chain` page in `wiki/causal-chains/`. **When ingesting on a non-Opus subagent (the normal case), defer this:** log the chain under a `Causal-chain candidates` block in `log.md` and let the batched Opus `/wiki-compile` pass (step 10) build it — but still add the `What causes this` / `What this causes` concept-page bullets now.
   - If a causal link is not supported by any source document, mark it EXTERNAL and cite the reputable source used. See `schema/causal.md`.
6. **Handle images and assets** — see the Images and assets section below.
7. **Update `index.md`:** add or update the entry for every page touched.
8. **Append to `log.md`:** one entry per ingest, format: `## [YYYY-MM-DD HH:mm:ss] ingest | [Source Title]`
9. **Regenerate `home-page.md`** as the last build step of the ingest — run the `home-page-moc`
   generator skill (`python <skills>/home-page-moc.py --root .`). This rewrites the Obsidian Map of
   Content from the current page set so it never drifts. `home-page.md` is a build artifact — never
   hand-edit it. If this ingest created a new `-vs-` page, add a `moc_mirror: <swapped-operand-slug>`
   line to that page's frontmatter *before* regenerating, so its mirror entry appears under the other
   letter (the spelling cannot be derived by string-swapping; see `schema/page-format.md`).
10. **Check the round boundary — don't let the finishing step be forgotten.** Ingestion defers the
    reasoning-heavy work: causal-chain construction (step 5) and the lint pass run as a batched
    **Opus** pass, the `/wiki-compile` skill — not per ingest. The one reliable trigger for that pass
    is the *end of a round of ingestion*, which only the user knows. So after completing this ingest,
    **ask the user**:
    > "Was this the last ingest in this round? If yes, I'll run `/wiki-compile` now — the finishing
    > step that builds the logged causal-chain candidates into pages and lints the new material so it
    > is fully usable. If more sources are queued, I'll defer and re-ask after the last one."
    Run `/wiki-compile` when the user confirms the round is done. **Backstop:** even mid-round, if the
    `Causal-chain candidates` logged in `log.md` since the last compile exceed ~15 (count them by `grep`/`tail`ing the log since the last `lint |`/`compile` marker — never whole-read it; see `schema/formats.md`), surface that and
    offer to compile now, so a very long batch never sits un-compiled. `/wiki-compile` is itself safe
    to run anytime — its STEP 0 dirty-check exits cheaply (no Opus spend) when there is nothing to do,
    which also makes it the right pass to run after manual Obsidian edits (lint + MOC reconcile).

One source document typically touches 8–15 wiki pages. Cross-link liberally — if page A mentions a
concept that has its own page B, add `[[page-b]]` to A's Related section.

---

### Source folder naming

Each source folder in `raw/` is named `NNNN_<slug>`:

- **`NNNN`** is a zero-padded 4-digit **catalog ID** — exactly four numeric digits, `0`–`9` only (no letters, no hex, no symbols), matching `^[0-9]{4}$`. It is assigned in sequence the moment the source is added to `raw/` (`0001`, `0002`, …) and gives every source — numbered series and one-off alike — a uniform, sortable, unique handle.
- **`<slug>`** is a unique kebab-case name for the source. If the source carries its own meaningful sequence (e.g. a numbered article series), keep that inside the slug (`0003_03-sample-article`): the catalog ID is additive metadata, not a replacement for the source's own ordering.
- **The catalog ID is a stable handle, not an ingestion-order field.** True ingestion chronology lives in `log.md` with full timestamps — do not infer it from the catalog ID.
- **Assign once, freeze forever.** The folder name is embedded in every page's `sources:` frontmatter and in image link-back paths, so it is load-bearing. If a source is ever removed, **leave the gap** — never renumber existing folders.

---

## Images and assets

Source documents may contain images. Some carry real explanatory value (a diagram of a mechanism, a
chart, an annotated screenshot); others are decorative — placed only to break up long text and
conveying no information the page depends on. During ingest, decide per image which it is.

Rules:

1. **Judge each image in context.** Read the image (filename, alt text, and the image itself) against the surrounding text. Ask: does the text rely on this image to be understood, or is it a visual breather? This is a judgment call the ingesting model makes while reading the source.
2. **Preserve illustrative images by linking back into `raw/`.** When an image carries explanatory value and belongs on a wiki page, reference it from that page with a relative link into the immutable source folder — e.g. from `wiki/metaphors/water-tank.md`: `![Water tank](../../raw/0003_03-sample-article/images/water-tank.png)`. Do not copy, move, or rename the image. Raw is immutable, so the path is stable.
3. **Open every image before you cite, summarize, embed, or skip it.** Never attribute content to an image you have not actually opened with the Read tool. Naming an image as the source of a claim (`raw/…/images/foo.png`), describing what a diagram or table shows, embedding it as evidence for a specific statement, or even classifying it decorative-vs-illustrative all require that you have read **that exact image** first. Inferring an image's contents from the surrounding prose — "the text here is about narrow commands, so the adjacent image probably shows that" — is **fabrication**, the same violation as inventing a source quote, and it produces confident false citations. If you have not opened an image, you may not describe it, cite it, or judge it: leave it unprocessed and let the lint pass (and its unreferenced-image check) surface it. When an ingest is interrupted, un-opened images are simply unfinished work — never paper over the gap with a guess.
4. **Synthesize image-borne information into the page text.** For every image kept as illustrative, read it and ask a second question: does it contain information **absent from the surrounding text** — figures, labels, table contents, steps in an annotated screenshot, cause-effect arrows in a diagram? If yes, that information MUST be written into the relevant page sections as text, in addition to linking the image — including causal bullets when the image depicts cause-effect. When the image depicts arrows/flows, **read each arrow's direction from its actual arrowheads at both ends, never from the diagram's overall layout**: a head at one end is one-way, heads at both ends are bidirectional. A missed second arrowhead silently turns a mutually-reinforcing (bidirectional) relationship into a one-way one and inverts the causal topology — so on a causal-chain page, render a double-headed arrow as two reciprocal links, not one. Bidirectional and upstream-pointing arrows are easiest to miss when they run counter to the expected flow or are short. A linked picture alone is invisible to wiki queries, search, and causal traversal; image-borne knowledge that stays only in the image is lost to every reader who doesn't open it. Image-derived claims are **source-grounded, not EXTERNAL** (the image is part of the source document), but cite the image path (`raw/NNNN_…/images/foo.png`) alongside the claim so it stays traceable to what a reader can verify. If part of an image is illegible (dense or small text in a screenshot), record what could not be read rather than guessing — the same no-fabrication discipline as everywhere else. When you reproduce text **verbatim** from an image (a quote, a transcribed label, a table cell), keep each transcribed sentence or cell on a single line and faithful to the source — do **not** inject newlines mid-sentence to hit a column width. Such breaks are arbitrary, do not mirror the image, and make the transcription unfaithful; this applies to quoted/transcribed image text specifically (the page's own explanatory prose follows the wiki's normal wrapping).
5. **Skip decorative images.** Do not link images whose only purpose is to break up text. Noting their existence is unnecessary.
6. **Never duplicate binaries into `wiki/`.** The wiki layer is synthesized text that points at source assets; it does not hold its own copies.
7. **When in doubt, lean toward preserving.** A wrongly-kept image is low-cost; a wrongly-dropped illustrative one loses information. The lint pass can review borderline calls.
8. **PDF-derived sources: deposit lightweight images, keep the original PDF as the master.** When a source is a PDF rasterized to per-page/per-slide images, distinguish two image generations with different jobs:
   - **Extraction images are transient.** The high-DPI PNGs (~200 DPI) produced to feed vision text/relationship extraction are *working files*, not archive material. They do **not** go into `raw/`. (The vision model downsamples to ~1568 px ≈ 150 DPI anyway, so 200 DPI buys nothing once extraction is done.)
   - **Deposit lightweight JPEGs in `raw/`.** Store per-page **JPEG at ~150 DPI** in the source folder's `images/` (e.g. `raw/0023_…/images/0387.jpg`). These exist only to render **inline** beside their extracted text and for human reference, so viewing quality is enough; this keeps `raw/` an order of magnitude smaller. Re-render them **straight from the PDF** (one clean generation), not by recompressing the extraction PNGs.
   - **Archive the original PDF once as `raw/_master/<file>.pdf`** — the full-fidelity fallback. `_master/` is a reserved non-`NNNN_` folder holding source masters shared across the PDF's derived lesson/section folders.
   - **A PDF does not render inline in markdown** (`![](x.pdf)` does not embed — you get only a click-to-open link). So the PDF is the reference-on-demand copy, never the embed. Every PDF-derived `article.md` MUST carry a one-line pointer to its master (`../_master/<file>.pdf`, opens in a new tab) so a reader who needs full fidelity of any page can reach it.
