# Greenfield discovery catalog

**Consumers:** `@architect` (Phase 0 — Discovery), gated on a greenfield signal (an explicit `--greenfield` flag or the empty-tree heuristic).

The discovery checklist for a from-scratch build. In a greenfield repo the "derive context by reading the repo" half of the ecosystem is empty — there is no `CLAUDE.md`, no manifest, no prior plan to read — so the entire burden falls on the asking half. This catalog is the guaranteed checklist that fills the gap: the foundational choices a new project needs (stack, deployment target, the MVP cut, the target user, non-functional requirements, scaffolding) are surfaced by a coverage rule rather than left to the model's general competence.

This is **instance #1** of the [interview-catalog pattern](README.md). It obeys all six invariants; in particular the **coverage rule** below is non-negotiable.

## Coverage rule

Every line below is either **asked** (via `AskUserQuestion`) or explicitly **marked `n/a — <reason>`** in the plan's `## Foundation` section. The consuming component must not silently skip a bucket. Buckets map cleanly onto `AskUserQuestion` calls (≤4 questions per call → ~2 calls for the four buckets).

## The four buckets

### Bucket 1 — Product framing

- **Target user** — who is this for (one persona is enough for v1)?
- **Core job** — the single thing v1 must do well (the thinnest viable slice)?
- **v1 success** — what "done" looks like for the first release (a demoable behavior, not a metric dashboard)?

### Bucket 2 — Technical foundation

- **Stack** — language(s) + framework + runtime. (The decision that is *assumed* in-project and *absent* in greenfield.)
- **Data** — persistence needed? none / file / SQL / NoSQL — and roughly what shape?
- **Identity** — auth needed? none / local sessions / OAuth / third-party IdP?

### Bucket 3 — Delivery & ops

- **Deployment target** — local CLI / library / container / serverless / PaaS / static host?
- **Scale & NFRs** — single-user toy vs multi-tenant; latency/throughput expectations; offline/availability needs?
- **Compliance** — any regulated/sensitive data (PII, payments, health)? A "yes" pre-flags `@security-reviewer` / `@security-mentor` and PCI/HIPAA criteria downstream.

### Bucket 4 — Constraints & scaffolding

- **Constraints** — must-use technologies, team familiarity, license, budget, deadlines?
- **Repo bootstrap** — init git? single package vs monorepo? scaffold via a framework CLI (e.g. `create-next-app`, `cargo new`) vs a hand-rolled skeleton?
- **v1 defer list** — what is explicitly OUT of the first cut (so scope is bounded from the start)?

## What the consumer does with the answers

The consuming component (`@architect`) writes the locked answers into a `## Foundation` section pinned to the top of the plan, plus a recommended minimal `CLAUDE.md` seed and a scaffold command — so once the first commit lands, the user runs `/agentic-onboard` to crystallize the context and every subsequent run is back in the cheap "context flows in" mode. Greenfield is the one case where the ecosystem **creates** the context it normally consumes; this catalog is the bootstrap step that closes that loop. The recommended scaffold command is never auto-executed — it rides the developer's normal commit/gate flow.
