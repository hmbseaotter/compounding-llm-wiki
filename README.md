# compounding-llm-wiki

**"Compounding" means the knowledge base gets richer with every source you add and every question you ask — each ingest cross-links into what is already there, so the whole compounds instead of growing as a flat pile of documents. This repository is a _template_: it ships empty, ready for you to point at your own domain and fill.**

> **Conceptual source.** This tool is a direct implementation of Andrej Karpathy's **"LLM Wiki"** idea, published here:
> <https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f>
> Read that gist first — it is the one-page rationale. Everything below is the working machinery built around it.

> **① Install the companion toolkit first.** The skills that ingest sources and maintain the wiki —
> `/pdf-to-images`, `/pdf-to-md`, `/image-to-md`, `/msword-to-pdf`, `/url-to-md`, `/deepwiki`,
> `/home-page-moc`, `/wiki-compile` — are **not** in this repository. They live in a separate
> companion repo, **[llm-wiki-toolkit](https://github.com/hmbseaotter/llm-wiki-toolkit)**. Clone it
> alongside this one and run its installer **before** you start ingesting; without those skills the
> ingest pipeline has no tools to run. (See the toolkit's README for its prerequisites: Python, and
> optionally LibreOffice and Firecrawl.)
>
> ---
>
> **② What this repository provides.** `compounding-llm-wiki` is the *wiki template* itself: it ships
> the schema (page types and rules) plus an empty, structured knowledge base, ready for you to point at
> your own domain and fill. The toolkit above is the machinery; this repository is the thing it builds.

---

## Table of contents

- [What this is](#what-this-is)
- [Purpose and benefits](#purpose-and-benefits)
- [Limitations](#limitations)
- [How it is laid out on disk](#how-it-is-laid-out-on-disk)
- [Folder rules (what each directory is for, and what you may not do to it)](#folder-rules)
- [How it operates](#how-it-operates)
- [Viewing the wiki](#viewing-the-wiki)
- [Requirements and dependencies](#requirements-and-dependencies)
- [Setups: where you can run this](#setups-where-you-can-run-this)
- [Deployment: getting the repo from GitHub (step by step)](#deployment-getting-the-repo-from-github-step-by-step)
- [Using the tool: what to type and where](#using-the-tool-what-to-type-and-where)
- [Flags and behavioral toggles](#flags-and-behavioral-toggles)
- [External tools for source acquisition](#external-tools-for-source-acquisition)
- [License](#license)

---

## What this is

A **persistent, compounding knowledge base** that an LLM builds and maintains for you out of source
documents in **any domain** — physiology, economics, a software project, a body of articles, legal
material, anything.

It follows the three-layer architecture from Karpathy's gist:

1. **Raw sources** (immutable) — the documents you feed in, kept exactly as received.
2. **The wiki** (LLM-maintained) — synthesized, cross-linked markdown pages compiled _once_ from
   those sources and kept current as more arrive.
3. **The schema** (`CLAUDE.md`) — the rulebook the LLM reads at the start of every session that
   tells it how to ingest, link, lint, and answer.

The wiki is **not** a search index over your raw files. It is a compiled artifact: knowledge is
written down once, cross-referenced, contradictions are flagged, and answers are read off the wiki
pages instead of being re-derived from raw sources every time you ask. That is what makes it
_compound_.

The whole behavioral contract lives in [`CLAUDE.md`](CLAUDE.md). When you open this repo in Claude
Code, that file is auto-loaded as the project instructions, so the assistant already knows how to
behave — you do not paste any prompt to "boot" it.

---

## Why the schema is split (and how the load-gate works)

Earlier versions of this template kept the entire rulebook in one `CLAUDE.md` that the agent
auto-loaded **in full at the start of every session**. That is simple, but it carries a cost worth
understanding, because it shapes how the tool now works.

**The problem — context cost compounds.** An LLM agent has a limited context window, and everything
it must "know" up front is re-read on every fresh session and silently competes for that window. Two
things made this grow without bound as a wiki matured:

- **`log.md` and `index.md` keep growing.** They are append-mostly catalogs of everything that has
  happened and every page that exists. In a mature wiki we measured a `log.md` that had grown **past
  what fits in a single context window**, and an `index.md` (consulted on essentially every question)
  that was **larger than the entire schema**. Re-reading those *whole*, every session, is the real
  token sink.
- **The schema itself was a flat, always-paid tax.** One big `CLAUDE.md` meant every session — and
  every cheap, dispatched sub-task — paid for the *complete* rulebook even when it only needed the
  slice for, say, ingesting one page.

**What the testing showed.** When we actually measured where the tokens went (instead of guessing),
the dominant, unbounded cost was **re-reading those growing catalog files** — not the model's
reasoning, and not re-reading source documents (individual sources turned out to be small). The fixed
schema load was a smaller, *bounded* cost, but a real one — and the piece we could cut most cleanly.

Token counts below are rough estimates (bytes ÷ 4), measured on two real wikis that differ in **both**
how many sources they hold and how big each source is:

| | Wiki A — short slide decks | Wiki B — long articles |
|---|---|---|
| sources / pages | ~80 / ~150 | ~250 / ~400 |
| a typical single source | ~3.5K tokens (median) | ~8.8K tokens (median; longest ~16K) |
| `log.md` (append-only history) | ~96K tokens | ~320K tokens — *past a single context window* |
| `index.md` (page catalog, read per query) | ~10K tokens | ~30K tokens |
| always-loaded schema — **before** the split | ~16K tokens | ~16K tokens |
| always-loaded schema — **after** the split | **~4.4K tokens** | **~4.4K tokens** |

The two wikis differ in source *count* **and** source *size* (short slides vs long articles), and the
catalog files grow with total ingested content and page count — both dimensions, not count alone. Even
the **largest single source (~16K tokens) is smaller than the old always-loaded schema**, and is
dwarfed by `index.md`/`log.md` — which is why re-reading sources was never the bottleneck, and why the
two levers that matter are the schema split (~16K → ~4.4K) and the never-whole-read rule for the
catalog files.

**The fix — load only what the task needs.** The schema is now **split in two**:

- **`CLAUDE.md` is a lean core** (a few KB) that *always* auto-loads: what the wiki is, where things
  live, the cross-cutting rules, and a **router** that says which detail file to read for which job.
- **`schema/` holds the detailed procedure** (page format, ingest, contradictions, causal chains,
  query, lint, index/log formats), and each file is read **on demand** — only when its workflow runs.

Paired with a standing rule to **never whole-read `log.md`/`index.md`** (the agent tails them, greps
them, or reads `git` history instead), this keeps each session's fixed context cost roughly flat as
the wiki grows, instead of climbing with every source you add.

**The load-gate — keeping the guarantee.** Auto-loading the whole schema had one virtue: the rules
were *guaranteed present* whenever the agent acted. On-demand loading could quietly lose that — an
agent might edit a page without having read the page-format rules first. So a small **load-gate**
restores the guarantee as an enforced check. A hook (`.claude/settings.json` → `tools/schema_gate.py`)
**blocks a write to `wiki/`, `index.md`, or `log.md` until the matching `schema/` file has been read
in that session**, then tells the agent exactly which file to open. It is deliberately conservative:

- It **fails open** — if it cannot run (for example, no Python on the machine) it simply stops
  enforcing rather than blocking your work; the periodic lint pass is the backstop.
- It is **cross-platform** — it tries `python3` first (Linux/macOS), then `python` (typical Windows),
  so one config works on either OS. Testing confirmed it fires in real sessions — and even inside the
  dispatched sub-agents the tool uses for cheap work — while staying invisible once the right file has
  been read.

For you as a user this is almost entirely transparent. The one time you'll notice it is if you
**hand-edit** a wiki page and the edit is blocked with a "Schema load-gate" message — that just means
"open the `schema/` file it names, then retry." The agent does exactly that on its own during normal
work.

---

## Purpose and benefits

- **Knowledge accrues instead of resetting.** Each source you add is woven into the existing pages.
  The tenth source benefits from the cross-links laid down by the first nine.
- **Answers are fast and grounded.** Queries read pre-compiled wiki pages, not raw documents, so the
  model is not re-reading and re-reasoning over everything on every question.
- **Traceability is built in.** Every page lists its `sources:` in frontmatter; every factual claim
  is attributable to a specific raw document, and any claim that came from the model's own general
  knowledge is fenced off and labelled `EXTERNAL` with a citation.
- **Contradictions surface instead of hiding.** When two sources disagree, the tool flags it on both
  pages, logs it, and asks _you_ — it never silently picks a winner.
- **Causal reasoning is first-class.** The wiki tracks cause-effect links with explicit direction
  (increase / decrease / activate / inhibit / …), assembles multi-step causal chains, and can
  traverse them ("what causes X?", "what does X cause?", "given symptom Y, what are the possible
  causes?").
- **Domain-agnostic.** Nothing in the schema is hardwired to a subject. Point it at your corpus.

---

## Limitations

- **It needs an LLM agent to run.** This is not a standalone program. It is a schema plus an empty
  scaffold; the "engine" is an AI coding agent (Claude Code is the reference implementation) that
  reads `CLAUDE.md` and does the work. With no agent, the repo is just folders and markdown.
- **Paywalled / login-gated pages cannot be auto-fetched.** The URL scraper does not share your
  browser's logged-in session, so it only sees the public preview. Those must be added manually (see
  the manual fallback under [How it operates](#how-it-operates)).
- **Quality scales with the model.** Reasoning-heavy steps (lint, causal chains, contradiction
  analysis) are routed to a stronger model on purpose; running everything on a weak model degrades
  silently.
- **It is not magic search.** If a fact is in no source and not safely fillable from general
  knowledge, the wiki records the gap rather than inventing an answer. That is by design.
- **You are the resolver of record.** Contradictions are flagged for human review. The tool will not
  resolve a genuine conflict on its own.

---

## How it is laid out on disk

```
compounding-llm-wiki/
├── CLAUDE.md          ← lean-core behavioral schema, auto-loaded every session
├── schema/            ← detailed workflow rules, loaded ON DEMAND (page-format · ingest · contradictions · causal · query · lint · formats)
├── .claude/
│   └── settings.json  ← load-gate hook (+ effort level): enforces the on-demand schema read before any wiki/index/log write
├── tools/             ← stdlib-only helpers: schema_gate.py (the load-gate) · contradiction_qa.py + structure_qa.py (optional QA checkers)
├── README.md          ← this file — project overview and setup guide
├── LICENSE            ← MIT
├── index.md           ← catalog of every wiki page (the LLM keeps this current)
├── home-page.md       ← Obsidian Map of Content (A–Z index) — AUTO-GENERATED by /home-page-moc; appears after the first compile
├── log.md             ← append-only history of ingests, contradictions, lint passes, URL acquisitions
├── raw/               ← source documents — IMMUTABLE, read-only, never modify
│   ├── 0001_source-document/      ← one folder per source, self-contained; NNNN_ = catalog ID
│   │   ├── article.md             ← the source text (filename may vary)
│   │   └── images/                ← assets referenced by relative links from the source text
│   │       ├── figure-001.png
│   │       └── ...
│   ├── 0002_another-source/
│   │   ├── paper.md
│   │   └── figures/
│   └── ... (one folder per source document)
└── wiki/              ← the synthesized, cross-linked knowledge base (LLM-maintained)
    ├── concepts/      ← abstract ideas, named entities, domain terms
    ├── tools/         ← specific named tools, systems, interventions (if the domain includes these)
    ├── workflows/     ← repeatable step-by-step processes and techniques
    ├── setup-guides/  ← installation / configuration walkthroughs (if applicable)
    ├── causal-chains/ ← explicit multi-step cause-effect pathway maps
    └── metaphors/     ← domain-specific teaching analogies
```

The template ships with `raw/` and the six `wiki/` subfolders **empty** (each holds a `.gitkeep`
placeholder so the structure survives in Git). `index.md` and `log.md` ship as empty, correctly
headed stubs. The `schema/` rule files, the `tools/` helper scripts, and the `.claude/settings.json`
load-gate ship ready to use — you never hand-edit them. You add sources; the LLM fills `wiki/`,
`index.md`, and `log.md`.

---

## Folder rules

Each directory has a job and a set of constraints. The LLM enforces these because `CLAUDE.md` tells
it to; you should respect them too when editing by hand.

| Path | What it holds | The rule |
|------|---------------|----------|
| **`raw/`** | Your original source documents, one self-contained folder per source. | **Immutable. Read-only. Never modify, rename, move, or delete anything inside `raw/`.** This is the archive of record. Each source keeps its own `images/` alongside its text so relative image links keep working; assets are never flattened into a shared folder (filenames collide). |
| **`raw/NNNN_<slug>/`** | One source = one folder, named with a 4-digit **catalog ID** + kebab-case slug (e.g. `0003_03-sample-article`). | The catalog ID is assigned once, in sequence, and **frozen forever**. If you remove a source, **leave the numbering gap** — never renumber, because the folder name is embedded in every wiki page's `sources:` field and in image paths. |
| **`wiki/`** | The synthesized pages — the actual knowledge base. | LLM-maintained. You _may_ read and hand-edit, but the LLM is the primary author. Pages follow the exact template in `CLAUDE.md`. Never copy raw binaries (images) in here — wiki pages _link back_ into `raw/`, they do not hold their own copies. |
| **`wiki/<type>/`** | One subfolder per page type (concepts, tools, workflows, setup-guides, causal-chains, metaphors). | A page lives in the subfolder matching its `type`. Filenames are kebab-case; wikilinks use the filename without extension (`[[context-window]]`). |
| **`index.md`** | A catalog of all wiki pages, grouped by type. | The LLM updates it on every ingest. It is the map, not the content. |
| **`log.md`** | Append-only history: ingests, contradictions, lint passes, URL acquisitions. | **Append-only — never edit past entries.** New entries go at the bottom. |
| **`CLAUDE.md`** | The behavioral schema (lean core). | This _is_ the engine's instruction set. Edit it to change how the tool behaves; otherwise leave it. Claude Code auto-loads it as project instructions. |
| **`schema/`** | The detailed workflow rules, split out of `CLAUDE.md` and loaded on demand. | LLM-maintained ruleset; the lean `CLAUDE.md` routes to the right file per task. Don't hand-edit unless you are deliberately changing how the tool behaves. |
| **`.claude/settings.json`** | The load-gate hook + effort level. | Enforces that the matching `schema/` file was read before a `wiki/`/`index.md`/`log.md` write. **If a hand-edit is blocked, this is why** — open the named `schema/` file once, then retry. Needs Python to enforce; **fails open** (no Python → no enforcement, never a block). |
| **`tools/`** | Stdlib-only helper scripts: `schema_gate.py` (the load-gate), plus the optional QA checkers `contradiction_qa.py` (claim conflicts) and `structure_qa.py` (schema/repo defects). | Run/maintained by the tool; no setup. |

> **Note on the `CLAUDE.md` name.** Claude Code automatically loads a file named `CLAUDE.md` at the
> repo root as project instructions — that is why the schema uses that name. If you drop this wiki
> into an _existing_ repo that already uses `CLAUDE.md` for something else, rename the schema (e.g.
> `WIKI_CLAUDE.md`) and point the assistant at it manually.

---

## How it operates

These are the operating rules the LLM follows. You trigger most of them with plain-English requests;
the schema does the rest.

### The skill sequence (at a glance)

If you are not sure what to run when, this is the path from a raw document to a fully-usable wiki.
The `/...` items are Claude Code custom skills configured on your machine (see
[External tools for source acquisition](#external-tools-for-source-acquisition)); the rest are plain
requests you type to the agent.

```mermaid
flowchart TD
  A[You have a source] --> B{What format?}
  B -->|Web page / URL| U["say: 'add source URL'<br/>(Firecrawl · /url-to-md)"]
  B -->|Word or ODF| W["/msword-to-pdf"]
  B -->|PDF| P{Text-only, or has graphics?}
  B -->|Other / offline| M["save it manually into raw/NNNN_slug/"]
  W --> P
  P -->|text-only prose| P1["/pdf-to-md"]
  P -->|diagrams · slides · tables| P2["/pdf-to-images → /image-to-md"]
  U --> RAW[("self-contained folder in raw/")]
  P1 --> RAW
  P2 --> RAW
  M --> RAW
  RAW --> ING["ingest: say 'ingest raw/NNNN_…' (Sonnet)<br/>pages · links · images · index · log · MOC"]
  ING --> Q{Last source in this round?}
  Q -->|no — more coming| B
  Q -->|yes| C["/wiki-compile (Opus)<br/>build causal-chains + full lint + MOC"]
  C --> USE["use it: ask questions anytime ·<br/>resolve flagged contradictions when prompted"]
```

1. **Acquire** — land the source in `raw/` as a self-contained `NNNN_<slug>/` folder, picking the
   route by format:
   - **Web page** → say **"add source `<URL>`"** (Firecrawl / `/url-to-md`).
   - **Word / ODF** (`.doc/.docx/.rtf/.odt`) → `/msword-to-pdf`, then treat the resulting PDF as below.
   - **Text-only PDF** (prose, no diagrams) → `/pdf-to-md`.
   - **PDF with graphics** (diagrams, slides, tables) → `/pdf-to-images`, then `/image-to-md`.
   - **Anything else / offline** → save it manually into `raw/NNNN_<slug>/`.
2. **Ingest** — say **"ingest `raw/NNNN_…`"**. The agent builds/updates pages, cross-links them,
   synthesizes image content into text, updates `index.md` and `log.md`, and regenerates the MOC.
   When it finishes it asks whether this was the **last source in the round**.
3. **Finish the round** — run **`/wiki-compile`** once per round (the agent prompts you at step 2).
   It builds the deferred `causal-chain` candidates into pages, runs the full lint, and regenerates
   the MOC — the step that makes the new material *fully* usable. It is safe to run anytime: it
   self-cancels when nothing has changed, and it is also the right thing to run after **manual
   Obsidian edits** (it reconciles lint + MOC and re-reasons only what changed).
4. **Use it** — ask questions anytime; resolve any flagged **contradictions** when the agent surfaces
   them. Good questions also compound the wiki (see [Querying](#querying)).

### Adding a source (two routes)

- **Manual route (always works).** Save the document yourself, put it in a folder named
  `raw/NNNN_<slug>/` (next free catalog ID + a kebab-case slug), with its text file and an `images/`
  subfolder, and tell the assistant to **ingest** it.
- **URL route (automated).** Say **"add source `<URL>`"**. The tool fetches the page as clean
  markdown, downloads its content images, rewrites the image links to be self-contained, records
  provenance (source URL, retrieval time, engine), files it as the next `raw/NNNN_<slug>/`, runs a
  QA check, logs an `acquire` entry, and then **asks you whether to ingest** — acquisition never
  auto-ingests, so a bad scrape can't flow into the wiki. The URL route depends on
  [Firecrawl](#external-tools-for-source-acquisition). Paywalled pages fall back to the manual route.

### Ingesting

On ingest the LLM reads the source in full, identifies every entity worth a page (concepts, tools,
workflows, setup-guides, causal relationships, metaphors), creates or updates the matching wiki
pages, cross-links them liberally (including **forward links** to pages that don't exist yet — those
are expected and resolve later), synthesizes any information that lives only in images into page
text, updates `index.md`, and appends an `ingest` entry to `log.md`. One source typically touches
8–15 pages.

### Contradiction handling (manual resolution)

Contradictions are a first-class concern, **never silently resolved**. When an incoming source
conflicts with an existing page (or two pages conflict during a query), the tool:

1. produces an **LLM plausibility assessment** (recording which model produced it and when),
2. records the conflict on **both** affected pages under `## Contradictions flagged`,
3. logs it in `log.md` as `Unresolved — flagged for user review`, and
4. **tells you** in the session and asks you to decide.

You resolve it; the tool then records your decision and the reason on both pages and in the log. The
only thing it resolves on its own is an unambiguous _scope mismatch_ (one source general, one
specific) — and even then it documents the scope on both pages rather than discarding a claim.

### QA tooling (optional automation)

Two small **stdlib-only** checkers ship in `tools/` so you (or the agent) don't have to eyeball every
page. Both are **dormant**: they do nothing until run, need no setup, no install, no API key — and
nothing breaks if you never touch them.

| Tool | Answers | Run it |
|---|---|---|
| `contradiction_qa.py` | which claim-level conflicts are open, by severity, and which are going stale | `python tools/contradiction_qa.py` |
| `structure_qa.py` | where the repo violates its own schema: duplicate slugs, index parity both ways, stale pending-pointers, broken image links, direction tokens outside the sanctioned vocabulary | `python tools/structure_qa.py` |

*(On macOS/Linux use `python3`. Both accept `--root <path>` if you are not in the wiki root.)*

**What is expected of you: nothing routine.** `/wiki-compile` runs both automatically as part of its
lint step, so a normal ingest-then-compile cycle already checks the wiki. Run them by hand only when
you want a check between compiles, or to confirm a fix.

- **Tier 1 — run it (zero infrastructure).** Each prints a plain report and exits. No email, git, or
  scheduler involved — they only detect and report.
- **Tier 2 — automate it (optional).** To have reports emailed on a schedule, wire the modules into a
  small daily job (cron / Task Scheduler) plus your mailer: they expose everything such a shell needs
  (`scan_contradictions` / `split_severity` / `aging_report`, and `scan_structure` /
  `structure_report`) and leave the send, cadence and state-write to your wrapper. Extra
  infrastructure, entirely optional — the wiki is fully functional on Tier 1.

**The two kinds of finding need different things from you:**

- A **contradiction** needs a *judgment*: two sources disagree and you decide, by editing the
  `Status:` line on the page (see the manual resolution above). A HARD one blocks an automated commit
  until you do; soft/scope ones never block and can be parked as `Acknowledged`.
- A **structural finding** needs a *fix*, not a judgment — rename the duplicate page, add the missing
  index line, correct the broken image path. There is **no marker to clear**: every check is
  recomputed from the repo, so the finding disappears by itself once the defect is gone. Structural
  findings never block a commit.

> **Keep the checkers identical across wikis.** Both files are meant to be byte-identical in every
> wiki, with `llm-wiki-toolkit/wiki-tools/` as the upstream; refresh them with the toolkit's
> `install-wiki-tools.ps1` / `.sh` (`--check` reports drift and exits non-zero). This matters because
> they were once hand-copied and silently diverged by ~70 lines — some wikis ran an older, weaker
> check for weeks without anyone noticing. If you are not using the toolkit, just leave them alone.

### Causal chains

The wiki records cause-effect links with an explicit **direction token** on every link
(increase / decrease / activate / inhibit / trigger / suppress / enable / block — an unlabelled link
is incomplete and gets flagged at lint). Chains of 3+ links become dedicated `causal-chain` pages
with a machine-traversable link table, including branches and feedback loops. You can then ask
causal questions and get upstream traces, downstream cascades, or a full symptom→cause tree. Where a
bridging link isn't in any source, the tool may fill it from general knowledge **only** if it labels
it `EXTERNAL` and cites a reputable source; an unsourceable bridge is marked `EXTERNAL — unverified`
and flagged for you.

### Querying

Ask a question. The tool reads `index.md`, opens the relevant wiki pages (not the raw sources),
checks for contradictions before combining pages, and answers in plain language citing the pages
used. If the answer is a useful synthesis not yet captured anywhere, it files it as a new page — so
**good questions also compound the wiki.**

### Linting

Periodically (after every 3–4 ingests, or when you ask), the tool sweeps for orphan pages, missing
pages, stale pointers, unlabelled causal directions, broken image links, unreferenced source images,
thin pages, and contradictions — fixing what it can and logging each fix.

The mechanical half of that sweep is the two QA checkers above: `/wiki-compile` runs
`structure_qa.py` and `contradiction_qa.py` first, then reasons about what they cannot check
(fabricated citations, an inverted causal direction, a thin page). So the deterministic defects are
caught the same way every time, and the model's attention goes to the parts that need judgment.
Anything a checker reports is either fixed in that pass or written into the `log.md` lint entry as
explicitly OPEN — never mentioned in passing, because a finding recorded only in a log nobody reads
is a finding nobody acts on.

### Images

Source images that carry real information (diagrams, charts, annotated screenshots) are linked back
into `raw/` from the relevant page **and** their information is transcribed into page text (a linked
picture alone is invisible to search and causal traversal). Purely decorative images are skipped. A
hard rule: the model must actually **open** an image before describing, citing, or even classifying
it — guessing an image's contents from surrounding prose is treated as fabrication.

### Model routing and cost

To match spend to need, the schema routes heavy reasoning (lint, causal-chain construction,
contradiction analysis) to a stronger model and routine ingestion to a cheaper one, by dispatching
subagents with an explicit model override. The orchestrating session does this automatically — you
are **not** asked to switch models by hand. (Reference defaults in `CLAUDE.md`: ingestion on a Sonnet
model, reasoning on an Opus model. Update that table, not your habits, if the model lineup changes.)

---

## Viewing the wiki

The wiki uses two conventions that **plain Markdown previews — including VS Code's built-in preview — do not render**: `[[wikilinks]]` (the cross-links between pages) and Mermaid diagrams (on `causal-chain` pages). To get clickable links, backlinks, a graph view, and graphical diagrams, open the wiki in a tool that understands them.

### Option 1 — Obsidian (recommended)

[Obsidian](https://obsidian.md/) is a free Markdown knowledge-base app built around exactly these conventions.

1. Download and install it from <https://obsidian.md/>.
2. Choose **"Open folder as vault"** and select this repository's root folder.
3. You immediately get: clickable `[[wikilinks]]`, **backlinks** (what links to the page you're on), a **graph view** of the whole wiki, inline images, and native **Mermaid** rendering.

Links to pages that don't exist yet show as "unresolved" — that's expected; they are forward links that light up automatically once the page is created.

### Option 2 — VS Code + two extensions

To stay in VS Code, add:

- **Foam** (or **Markdown Memo**) — makes `[[wikilinks]]` clickable and adds backlinks + a graph view.
- **Markdown Preview Mermaid Support** — renders the Mermaid diagrams in VS Code's preview.

**How to install a VS Code extension** (if you've not done it before):

1. Open the **Extensions** view — click the four-squares icon in the left **Activity Bar**, or press **Ctrl+Shift+X** (Windows/Linux) / **Cmd+Shift+X** (macOS), or use the menu **View → Extensions**.
2. Type the extension's name into the search box (e.g. `Foam`).
3. Click **Install** on the matching result; reload if VS Code prompts you.
4. Open any wiki page and choose **Open Preview** (**Ctrl+Shift+V** / **Cmd+Shift+V**) — wikilinks and Mermaid now render.

### Option 3 — GitHub (online)

GitHub's Markdown viewer renders **Mermaid diagrams automatically**, so the causal-chain flowcharts display right on the repository website, and it shows images. It does **not** make `[[wikilinks]]` clickable — for full navigation use Obsidian or the VS Code extensions above.

> Every `causal-chain` page also carries a plain-text (ASCII) version of its diagram, which renders in **any** viewer with no extension — so the visual is never lost, even in a bare Markdown preview.

---

## Requirements and dependencies

| Requirement | Needed for | Notes |
|-------------|-----------|-------|
| **An AI coding agent that reads `CLAUDE.md`** | Everything. | **Claude Code is the reference implementation** and the only setup verified here. The agent must support: auto-loading `CLAUDE.md` as project instructions, reading/writing files in the repo, and (ideally) dispatching subagents with a model override for cost routing. |
| **Git** | Cloning/updating the repo. | Standard Git install. |
| **Git LFS** | Cloning/pushing the repo's binary assets — per-page images in `raw/**/images/` and master PDFs in `raw/_master/`. | Run `git lfs install` once. Without it you get LFS pointer text files instead of the images. See the **Git LFS note** below if a push is ever rejected with `GH008`. |
| **Firecrawl** (optional) | The automated "add source `<URL>`" route only. | Not required for manual source-adding or for any query/lint work. |
| **LibreOffice** (optional) | Converting Word/ODF sources (`.doc/.docx/.rtf/.odt`) to PDF before ingest, via the `/msword-to-pdf` skill. | Not required otherwise. Install elevated: `winget install --id TheDocumentFoundation.LibreOffice -e --silent --accept-package-agreements --accept-source-agreements`. MS Word not needed. |
| **Python 3 + PyMuPDF** (optional) | Rasterizing a PDF (or a converted Word doc) to per-page images for the vision pass, via `/pdf-to-images`. | PyMuPDF auto-installs on first run; no Ghostscript/poppler. Not required for text-only sources or query/lint. |

The **wiki template itself** needs no Node and no build step — the "program" is the schema plus your
agent. The one place Python appears is the optional **load-gate** hook (`tools/schema_gate.py`): it
enforces the on-demand schema split, but **fails open**, so without Python it simply does not enforce
and everything else still works. (`tools/contradiction_qa.py` and `tools/structure_qa.py` are likewise optional and stdlib-only.) The optional tools above matter only for
*automated source acquisition* — fetching a URL, or converting a PDF/Word file into ingestible
per-page form. Manual source-adding and all query / lint / contradiction work need none of them. See
[External tools for source acquisition](#external-tools-for-source-acquisition).

> **Git LFS note.** Raw images (`raw/**/images/`) and master PDFs (`raw/_master/`) are stored in Git
> LFS. Normally `git push` uploads them automatically. But if your environment sets a custom
> `core.hooksPath` (e.g. a push-guard hook), it can **shadow git-lfs's own pre-push hook**, and a push
> that adds **new** binaries is then rejected remotely with `GH008: ... unknown Git LFS objects`. Fix:
> run `git lfs push --all origin`, then `git push` — or chain `git lfs pre-push "$@"` into your custom
> hook so it happens automatically.

---

## Setups: where you can run this

You drive this tool through an AI agent. Here is where that works, and the particulars of each.

### 1. Claude Code CLI (terminal) — **recommended, fully supported**

The reference setup. You run `claude` in a terminal that is `cd`'d into the repo folder. `CLAUDE.md`
auto-loads, subagent model routing works, Firecrawl (a CLI/skill) is available. Everything in this
README assumes this setup unless stated otherwise.

### 2. Claude Code in the browser (claude.ai/code) — **supported, with caveats**

The web GUI for Claude Code. You connect it to the repository and work in a hosted environment.
Ingest, query, lint, and contradiction handling all work. The one caveat is environment-dependent
tooling: the **URL-scrape route needs Firecrawl available in that environment**; if it isn't, use
the manual source-adding route (which works everywhere). If subagent model-override isn't available
in the hosted environment, the tool falls back to running inline and tells you which model it's on —
so reasoning-heavy work isn't silently done on a weak model.

### 3. Claude Code in the Claude Desktop app — **supported, same as browser GUI**

The desktop app exposes the same Claude Code GUI as the browser, pointed at your repo. Same
capabilities and the same Firecrawl/subagent caveats as setup #2.

### 4. IDE extensions (VS Code, JetBrains) — **supported**

Claude Code's IDE integrations run against the open repository folder. `CLAUDE.md` auto-loads the
same way. Treat this like the CLI setup with an editor wrapped around it.

### 5. Other AI agents (e.g. Codex, or any non-Claude agent) — **not verified; use at your own risk**

The schema in `CLAUDE.md` is plain markdown and another capable agent could in principle follow it.
**But it has not been tested outside Claude Code, and two things specifically may not carry over:**
(a) automatic loading of `CLAUDE.md` as project instructions — on another agent you may have to paste
or point it at the schema manually each session; and (b) the **subagent model-routing** mechanism,
which is Claude Code-specific — without it, cost routing won't happen automatically and you'd manage
model choice yourself. If your agent can't read the repo files or can't follow the schema, **the tool
simply cannot be used in that setup** — there is no fallback that makes a non-file-aware chatbot work.

> **The honest baseline:** if an interface can't (a) read and write the files in this repo and (b)
> read `CLAUDE.md` as its instructions, this tool will not work there. Both conditions are met by
> Claude Code in all four of its flavors above.

---

## Deployment: getting the repo from GitHub (step by step)

This section is deliberately detailed for people who have never used GitHub or a terminal. If you
already know your way around Git, skip to ["Using the tool"](#using-the-tool-what-to-type-and-where) —
the one-liner is `git clone <your-repo-url>` then open it in Claude Code.

### Step 0 — Install the prerequisites (done once on your machine)

- **Git.** Download from <https://git-scm.com/downloads>, run the installer, accept the defaults.
  To confirm it worked, open a terminal (on Windows: **PowerShell**; on macOS: **Terminal**) and
  type `git --version`. You should see a version number.
- **Claude Code.** Follow the official install at <https://docs.anthropic.com/en/docs/claude-code>.
  Confirm with `claude --version` in the same terminal.

### Step 1 — Make your own copy of the template on GitHub

This repo is a **template**, so you don't work in it directly — you spin up your own copy:

1. In your web browser, open this repository's page on **GitHub**.
2. Click the green **"Use this template"** button near the top right, then **"Create a new
   repository"**. (If you don't see that button, use **"Fork"** instead — same end result for our
   purposes.)
3. Give your new repository a name (e.g. `my-physiology-wiki`), choose Public or Private, and click
   **"Create repository"**. GitHub now hosts _your_ copy.

### Step 2 — Copy your repository's address

On **your** new repository's GitHub page, click the green **"Code"** button. Under the **HTTPS** tab
you'll see a URL like `https://github.com/<your-username>/<your-repo>.git`. Click the copy icon next
to it.

### Step 3 — Download it to your computer ("clone")

1. Open a terminal (**PowerShell** on Windows, **Terminal** on macOS/Linux).
2. Move to the folder where you want the project to live, e.g. `cd Documents`.
3. Run, pasting the URL you copied:
   ```
   git clone https://github.com/<your-username>/<your-repo>.git
   ```
   > **HTTPS vs SSH?** The **HTTPS** URL above (from the green **Code** button) needs no setup and
   > works for everyone. If you have already set up **SSH keys** with GitHub, you may instead use the
   > SSH form `git@github.com:<your-username>/<your-repo>.git`; if that means nothing to you, stick
   > with HTTPS.

   By default this creates a folder named after your repo. To clone into a folder name **of your
   choosing** instead, add that name as a final argument:
   ```
   git clone https://github.com/<your-username>/<your-repo>.git my-physiology-wiki
   ```
4. This creates a new folder (named after your repo, or the custom name you gave), containing all the
   files. Enter it:
   ```
   cd <your-repo>          # or: cd my-physiology-wiki
   ```

> **No-terminal alternative:** on your repo's GitHub page, **"Code" → "Download ZIP"**, then unzip
> it. You still need a terminal (or the IDE/GUI setups above) to actually run Claude Code against it.

### Step 4 — Open it in your agent

- **CLI:** from inside the repo folder, run `claude`.
- **GUI (browser or Desktop app):** connect Claude Code to the repository / open the folder.
- **IDE:** open the repo folder in VS Code or JetBrains with the Claude Code extension installed.

`CLAUDE.md` loads automatically and the assistant is ready. You're now ready to add sources.

### Step 5 (optional) — Save your work back to GitHub

As you add sources and the wiki grows, commit and push so your knowledge base is backed up:
```
git add .
git commit -m "Add first sources and initial wiki pages"
git push
```
(The very first push may ask you to sign in to GitHub — follow the prompt.)

> **`git add .` does not mean "everything."** It stages new and changed files _except_ those listed
> in `.gitignore`. This template ignores your machine-local files — `project_prompts.txt` and
> `resume_session.txt` — so they are automatically skipped and **never pushed to GitHub**. Your local
> prompt history stays local, by design.

---

## Using the tool: what to type and where

A recurring source of confusion in guides is _where_ a given command runs. Here it is spelled out.
Three distinct "places" matter: **(A)** your computer's **terminal**, **(B)** the **GitHub website**
in your browser, and **(C)** the **Claude Code prompt** (the chat box — same whether you reach it via
CLI, browser GUI, Desktop app, or IDE).

| What you want to do | Where you do it | Exactly what you type / click |
|---------------------|-----------------|-------------------------------|
| Install Git / Claude Code | **(A) Terminal**, anywhere | per [Step 0](#step-0--install-the-prerequisites-done-once-on-your-machine) |
| Create your own copy of the template | **(B) GitHub website**, on the template's page | "Use this template" → "Create a new repository" |
| Clone the repo to your machine | **(A) Terminal**, in the parent folder where you want it | `git clone <your-repo-url>` |
| Launch the agent | **(A) Terminal**, **inside the repo folder** | `claude` (CLI) — or open the folder in the GUI/IDE |
| Add a source from a URL | **(C) Claude Code prompt**, with the repo open | `add source https://example.com/article` |
| Add a source manually | **(A) Terminal/file manager** to drop the folder into `raw/`, then **(C) prompt** | place `raw/NNNN_<slug>/…`, then say `ingest the new source in raw/` |
| Ask a question of the wiki | **(C) Claude Code prompt** | plain English, e.g. `what causes context-window exhaustion?` |
| Run a lint pass | **(C) Claude Code prompt** | `run a lint pass` |
| Resolve a flagged contradiction | **(C) Claude Code prompt** | `resolve the contradiction on <page>` and tell it which claim to keep |
| Back up your growing wiki | **(A) Terminal**, inside the repo folder | `git add . && git commit -m "…" && git push` |

The golden rule: **anything starting with `git` or `claude` is a terminal command run from inside the
repo folder; anything that is a request _about your content_ is typed into the Claude Code prompt.**

---

## Flags and behavioral toggles

**This tool defines no command-line flags of its own.** It is not a binary you invoke with switches;
it is a schema an agent follows. So there is no `--separate` or similar flag built into the wiki —
if you've seen flags like that in other tools, they don't apply here. What you _do_ have are a few
real toggles and switches:

- **Manual vs. automated source intake** — a behavior you choose by how you phrase the request
  ("`add source <URL>`" = automated/Firecrawl; dropping a folder into `raw/` + "ingest" = manual).
  This is the closest thing to a "mode switch" the tool has.
- **Effort level** — set in `.claude/settings.json` (`"effortLevel": "high"` ships as the default).
  The workspace convention is to run everything at high effort.
- **Model routing** — governed by the table in `CLAUDE.md` (which model handles ingestion vs.
  reasoning), not by a flag. Change behavior by editing that table.
- **Schema filename** — rename `CLAUDE.md` to `WIKI_CLAUDE.md` (and point the agent at it) only if it
  collides with another `CLAUDE.md`. See the note under [Folder rules](#folder-rules).
- **Firecrawl's own flags** — the URL route runs Firecrawl internally, roughly
  `firecrawl scrape <URL> --only-main-content -f markdown -o <out>`. Those flags belong to Firecrawl,
  not to this tool, and you normally never type them yourself — the agent does.

If you want a genuine new toggle (say, "ingest but skip image processing"), the way to add it is to
write the rule into `CLAUDE.md` — the schema _is_ the configuration surface.

---

## External tools for source acquisition

The wiki's core — ingest, query, lint, contradiction handling — needs nothing beyond your agent. The
tools below are each **optional** and unlock one *source-acquisition* route; you only need the one(s)
for the route you use, and none of them for manually-added sources.

### Firecrawl — the "add source `<URL>`" route

Firecrawl is used for **one thing only**: the automated "add source `<URL>`" route, which fetches a
web page as clean markdown plus its images. **You do not need Firecrawl at all** if you only add
sources manually or only query/lint an existing wiki.

To enable the URL route:

1. **Install the Firecrawl CLI.** Follow the official instructions at
   <https://www.firecrawl.dev> / <https://docs.firecrawl.dev>. (In a Claude Code environment that
   already exposes a Firecrawl skill, the capability may be present without a separate install.)
2. **Get an API key.** Create a Firecrawl account and copy your API key from its dashboard.
3. **Make the key available to the environment** Claude Code runs in — typically as an environment
   variable such as `FIRECRAWL_API_KEY`. Set it in the terminal (or your environment's secrets) the
   same way you'd set any API key:
   - PowerShell: `$env:FIRECRAWL_API_KEY = "fc-…"`
   - macOS/Linux: `export FIRECRAWL_API_KEY="fc-…"`
   (To persist it, add it to your shell profile or your environment's secret store.)
4. **Verify** by asking the assistant to add a source from any public URL. If Firecrawl isn't
   available or the key is missing, the tool will tell you and point you to the manual route — it
   won't fail silently.

> The schema is engine-agnostic: any fetcher that produces clean main-content markdown can stand in
> for Firecrawl. Firecrawl is just the current default. **Paywalled / logged-in pages can't be
> fetched this way** (the scraper doesn't share your browser session) — add those manually.

### LibreOffice — the Word / ODF source route

To ingest a Microsoft Word (`.doc/.docx`) or ODF (`.rtf/.odt`) document, the `/msword-to-pdf` skill
converts it to PDF (via LibreOffice headless), after which it flows through the **same image+vision
pipeline as any PDF**. This matters because a Word file can carry embedded images, diagrams, charts,
and line-tables that a text-only extraction would silently drop — converting to PDF and rasterizing
preserves them.

- **Install** (run in an **elevated** terminal so the MSI finalizes cleanly):
  `winget install --id TheDocumentFoundation.LibreOffice -e --silent --accept-package-agreements --accept-source-agreements`
- MS Word itself is **not** required. If LibreOffice is missing, `/msword-to-pdf` says so and prints this command.
- A genuinely pure-text Word doc can instead be extracted directly with `firecrawl-parse` (no LibreOffice) — but prefer the convert-to-PDF route whenever the document has any figures, so nothing graphic is lost.

### PyMuPDF — rasterizing PDFs to per-page images

The `/pdf-to-images` skill (used on PDFs, and on the PDFs produced from Word) rasterizes each page to
an image for the vision pass. It runs on Python 3 with **PyMuPDF**, which it **auto-installs on first
run** — so there is normally nothing to set up, and no Ghostscript/poppler is needed.

---

## License

MIT — see [`LICENSE`](LICENSE).
