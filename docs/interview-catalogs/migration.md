# Migration discovery catalog

**Consumers:** `/migration-planner` (front-loaded discovery, walked *before* the risk dossier is produced); also `@architect` when a plan includes a migration.

`/migration-planner` already emits a rich MIGRATION RISK DOSSIER, but a dossier is only as good as the facts it rests on. This catalog formalizes the front-loaded questions the planner should ask the user *first*, so the dossier is grounded in answers rather than assumptions — which change is proposed, how much data it touches, whether downtime is acceptable, how it rolls out and rolls back, and who else reads the affected schema.

This is **instance #2** of the [interview-catalog pattern](README.md). It obeys all six invariants; in particular the **coverage rule** below is non-negotiable.

## Coverage rule

Every line below is either **asked** (via `AskUserQuestion`, before the dossier) or explicitly **marked `n/a — <reason>`** (e.g. "n/a — additive nullable column, no data state to assess") in the dossier's context. The planner must not silently skip a bucket. Buckets map cleanly onto `AskUserQuestion` calls (≤4 questions per call).

## The six buckets

### Bucket 1 — Change shape

- **Operation** — add / drop / rename / type-change / constraint (NOT NULL, unique, FK)?
- **Reversibility** — is the change reversible or destructive?

### Bucket 2 — Data state

- **Row count** — approximate row count of the affected table(s)?
- **Existing data** — any existing data needing a backfill?
- **Current shape** — current nullability / defaults on the affected column(s)?

### Bucket 3 — Lock & downtime

- **Downtime budget** — is any downtime acceptable, and for how long?
- **Traffic constraints** — peak-traffic windows to avoid? (anchors the DB-specific lock profile the planner already detects.)

### Bucket 4 — Rollout

- **Strategy** — single migration, or expand/contract (parallel-change) for zero downtime?
- **Feature flags** — any feature-flag coupling the rollout depends on?

### Bucket 5 — Rollback

- **Undo shape** — what does "undo" look like — reverse migration, restore from snapshot, or forward-fix only?

### Bucket 6 — Blast radius

- **Readers & writers** — which code reads/writes the affected schema, and who owns it?

## What the consumer does with the answers

The answers ground the dossier the planner already produces: the **Change shape** + **Data state** answers feed AFFECTED SCHEMA + RISK CLASSIFICATION; **Lock & downtime** feeds the engine-specific LOCK / DOWNTIME analysis; **Rollout** feeds the EXPAND / CONTRACT plan; **Rollback** feeds the ROLLBACK PLAN; **Blast radius** seeds (but does not replace) the BLAST RADIUS grep. The planner remains read-only and human-gated throughout — this catalog adds questions, it does not change the dossier's output format or the HANDOFF GATE.
