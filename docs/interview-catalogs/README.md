# Interview catalogs

An **interview catalog** is a named, declarative markdown checklist of the questions a consuming agent or skill must surface — *before* its main work — so that the foundational answers it needs are produced by a guaranteed coverage rule instead of being left to the model's improvisation.

Catalogs are the constructive half of a decision already taken: a centralized runtime **"interviewer middleware"** was evaluated and **declined**, and the kernel worth keeping from it — *consistent interview coverage* — is delivered declaratively here instead. See "Why a catalog, not middleware" below for the full rationale, mirrored in [`../design-philosophy.md`](../design-philosophy.md) as a first-class design principle.

This directory is the one home for catalogs: this README defines the pattern + indexes the catalogs, and each catalog lives in its own file.

## The six invariants

Every catalog in this directory obeys all six:

1. **Declarative** — it is data (bucketed questions), not code. No runtime, no interception, no shared state. A catalog is a markdown file; nothing executes it.
2. **Bucketed** — questions are grouped so one `AskUserQuestion` call maps cleanly onto one or two buckets (the harness caps a call at ~4 questions, so a 3-question bucket is one call).
3. **Coverage rule** — every line is either asked or explicitly marked `n/a — <reason>`; a consuming component may **not** silently skip a bucket. The mark is the audit trail that the question was considered, not forgotten.
4. **Front-loaded** — the consuming component walks the catalog *before* its main deliverable (the architect's plan body, the migration planner's risk dossier). This generalizes the architect's standing lesson that a mid-build pivot costs roughly 10× the same question asked during planning.
5. **Referenced, not centralized** — one or more components consume a catalog by **embedding its buckets** at the relevant phase (so the component is self-contained at runtime) **and** pointing at the canonical file here. Nothing sits between the agent and the user; the harness's native `AskUserQuestion` remains the only questioning UI.
6. **Drift-guarded** — a CI check asserts each catalog's bucket headers appear in its declared consuming component(s). A catalog with no consumer, or a consumer missing a bucket, fails CI — the same family as the existing component-count drift guards.

## Why a catalog, not middleware

A middleware would intercept all agent↔user questioning, own a shared interview state, and route answers to whichever agent needs them. It was rejected for four reasons, by weight:

- **No clean interception point.** Subagents run in isolated contexts via the Task tool — there is no shared message bus to sit "between" them and the user, and the harness's `AskUserQuestion` is already the native, uniform questioning UI. A middleware would reimplement it with less integration.
- **It fights fresh-eyes.** The reviewers (`@pr-reviewer`, `@security-reviewer`, `@plan-reviewer`, `@bug-catcher-adversary`, `@wiki-auditor`, `@context-auditor`) are deliberately blind to prior context. A shared interview-state store is exactly the cross-agent context channel that risks leaking into agents that must stay blind.
- **It centralizes what the architecture distributes.** Least-privilege and per-agent ownership of gates are core house style; a middleware re-couples them.
- **The cross-agent dedup it would buy already exists.** The orchestrator carries answered decisions forward through the plan file + issue body, and agents re-read those at their phase boundary, so an agent doesn't re-ask what an upstream agent already settled.

The declarative catalog keeps the one thing the middleware got right — guaranteed coverage — and discards the coupling.

## How a component consumes a catalog

1. **Embed the buckets** at the component's discovery phase, so the component is fully self-contained when it runs (an agent in an isolated Task context cannot read this directory at runtime — it carries the buckets in its own body).
2. **Point at the canonical file** here for the rationale + the coverage/drift rules.
3. The drift guard keeps the embedded copy and the canonical file in sync: every bucket header in the catalog must appear in each declared consumer.

## Adding a new catalog

A catalog must **earn its keep** — add one only when a real, observed coverage gap justifies it. To add one:

1. Write `docs/interview-catalogs/<name>.md` with bucketed questions, a `**Consumers:**` line naming the component(s) that walk it, and the coverage rule restated.
2. Embed its buckets in each consuming component and add the canonical-file pointer.
3. Add a row to the index below.
4. Add the catalog + its consumer(s) to the CI drift check (`.github/workflows/validate.yml`) so the bucket headers stay in sync.

## Index

| Catalog | File | Consumer(s) | Buckets |
| --- | --- | --- | --- |
| Greenfield discovery | [`greenfield.md`](greenfield.md) | `@architect` (Phase 0 — Discovery) | Product framing · Technical foundation · Delivery & ops · Constraints & scaffolding |
| Migration discovery | [`migration.md`](migration.md) | `/migration-planner` (front-loaded discovery, before the risk dossier) | Change shape · Data state · Lock & downtime · Rollout · Rollback · Blast radius |

**Future instances (not built — listed to show the pattern is open-ended):** a bug-repro catalog for `/bug-catcher`, a security-scoping catalog for `@security-reviewer`. Add only when a real coverage gap is observed.
