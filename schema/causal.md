# Schema — Causal chain capability (detail)

> **Loaded on demand.** The lean core `CLAUDE.md` routes here via its Workflow router; read
> this file in full before tracking, building, or querying causal chains. Cross-cutting invariants and the Hard Rules live in `CLAUDE.md`.

---

## Causal chain capability

The wiki tracks, assembles, and traverses multi-step cause-effect chains of any length. This is
useful for any domain where effects cascade: physiology, economics, ecological systems, technology
failure modes, and more.

### What the wiki tracks for causal reasoning

For every named concept or entity, the wiki tracks:

- **Upstream causes:** what entities cause or contribute to this one, by what mechanism, and in what direction
- **Downstream effects:** what entities this one causes or contributes to, by what mechanism, and in what direction
- **Direction of effect on every link:** use a consistent vocabulary — increase / decrease / activate / inhibit / trigger / suppress / enable / block. Never leave direction ambiguous.

This is captured in three places:
1. `What causes this` and `What this causes` sections on individual concept pages
2. Dedicated `causal-chain` pages for chains of 3+ links, including branches
3. Wikilinks between pages that allow traversal in either direction

### Querying causal chains

When a user asks a causal question, answer in one of three modes depending on the question:

**"What causes X?" / "What leads to X?"**
Read X's page. Report everything in `What causes this`, including direction of each effect. Traverse any `causal-chain` pages that include X as an effect node and report the full upstream path to root causes.

**"What does X cause?" / "What happens when X increases/decreases?"**
Read X's page. Report everything in `What this causes`, including direction. Traverse downstream through causal-chain pages. Report the full cascade.

**"Given symptom or outcome Y, what are the possible causes?"**
Find all causal chains and concept pages where Y appears as an effect. Traverse backwards to all root-cause nodes. Present the result as a cause tree:

```
Y is caused by:
├── A — [direction + mechanism]
│   └── A is caused by: P [direction], Q [direction]
│       └── P is caused by: S [direction]
└── B — [direction + mechanism]
    └── B is caused by: R [direction]
```

Mark any branch that includes EXTERNAL links. If a path is incomplete (a root cause is not found in the wiki), note the gap rather than fabricating an answer.

**Cyclic chains (feedback loops).** When traversing — in any of the three modes — and you reach a
node already on the current path (a loop-back edge, marked `↺` in the Links table), **stop
traversing that branch and report the cycle** instead of recursing forever. State the loop
explicitly: name the node where it closes, the direction, and whether it is **reinforcing**
(amplifies each pass) or **balancing** (settles toward equilibrium). In a cause tree, render the
closure as a leaf like `└── ↺ loops back to [[node]] (reinforcing) — see [[chain-name]]`. Every node
is visited at most once per path; the `↺` marker and the chain's `## Loop` section tell you where
cycles close.

### Handling gaps in causal chains

Source documents may not cover every link in a chain. When a link is not supported by any raw
source, the wiki may fill the gap using LLM general knowledge under these rules:

1. **Mark the link as EXTERNAL** in the chain with `· Source: EXTERNAL`.
2. **Cite a reputable source** in both the `external_knowledge` frontmatter field and the `## External knowledge used` section. A reputable source is a peer-reviewed paper, authoritative textbook, recognized clinical guideline, or well-established reference work. Include author, publication, year, and URL or DOI where available.
3. **Record the model and timestamp** for every external knowledge entry: the exact model name/version that supplied the knowledge (e.g. `claude-sonnet-4-6`) and the full datetime it was added. Different models have different knowledge cutoffs and reliability, so this provenance must be auditable later.
4. **Never blend** external knowledge silently with source-document knowledge. The seam must always be visible to the reader.
5. If the LLM cannot identify a specific reputable source for a bridging claim, mark the link as `EXTERNAL — unverified` and flag it for user review rather than presenting it as established fact. The model name and timestamp must still be recorded.
