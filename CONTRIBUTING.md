# Contributing

Thanks for your interest in **compounding-llm-wiki** — the **template** for an LLM-maintained
compounding knowledge base. Note what this repo *is*: a schema plus an empty scaffold, not a wiki
with content.

## Contribute to the machinery, not to wiki content
- **To USE the tool**, don't contribute here — click **"Use this template"** to make your own copy and
  fill it with *your* sources. Please don't open PRs that add domain content (sources or wiki pages)
  to this template; it ships empty by design.
- **To IMPROVE the tool**, contributions to the **schema and helpers** are very welcome: the lean
  `CLAUDE.md` core, the on-demand `schema/` rule files, the `tools/` helpers (load-gate,
  contradiction QA), and the docs.

## Ways to contribute
- **Open an issue** for a schema ambiguity, a `tools/` bug, or a proposed rule change.
- **Send a PR** that changes the machinery, keeping the constraints below.

## Conventions (the load-bearing ones)
- **`raw/` is immutable** — never modify, rename, or renumber a source folder; catalog IDs are frozen.
- **Schema stays split + on-demand.** The lean `CLAUDE.md` routes to `schema/<file>` per task, and the
  **load-gate** (`tools/schema_gate.py`) enforces that the right `schema/` file was read before any
  `wiki/` / `index.md` / `log.md` write. Keep the gate **fail-open** (no Python → no block, never a
  hard stop).
- **Catalog files:** `log.md` is **append-only**; nothing should require whole-reading
  `log.md` / `index.md` (the context-cost lesson the README documents).
- **`tools/` stays standard-library only** and cross-platform (it tries `python3`, then `python`).
- **Contradictions are never auto-resolved** — they are flagged for the human.

## Testing
Open the template in Claude Code and run a small end-to-end pass on a throwaway copy: ingest one
sample source, confirm the load-gate fires on a `wiki/` write before the matching `schema/` read, run
`python tools/contradiction_qa.py --root .` (macOS/Linux: `python3`), and check that
`index.md` / `log.md` update correctly.

## Pull requests
- Keep changes **focused**; clear commit messages (subject + a short "why").
- A change to page format / ingest / MOC must stay in sync with the companion
  [llm-wiki-toolkit](https://github.com/hmbseaotter/llm-wiki-toolkit) skills.

## License
By contributing, you agree your contributions are licensed under the repo's [MIT License](LICENSE).
