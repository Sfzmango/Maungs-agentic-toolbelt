> Example `/migration-planner` output for the fictional **ExampleApp**. Frozen sample — the same MIGRATION RISK DOSSIER format the live skill emits.

---

# Sample migration risk dossier — `members.joined_via` NOT NULL + `create_invitations`

> Pre-flight analysis for the EX-218 "Team invitations" schema work, run against **ExampleApp** — a
> multi-tenant B2B SaaS helpdesk (Organizations → Members [owner/agent/viewer] → Tickets → Billing).
> Stack: Ruby on Rails (ActiveRecord) + PostgreSQL + a React front-end. Cardinal rule under test:
> every record is scoped to an organization; cross-tenant access must 404.
>
> This file shows the full dossier the `/migration-planner` skill emits **before** any migration is
> written or run. The skill is read-only: it produces this analysis, a human decides, and a downstream
> agent implements behind a gate. The `file:line` and row-count references point at the fictional
> ExampleApp source, not at this repo. Every unmeasured number is marked **"verify against prod-like
> data"** with the exact query that would measure it — none are invented.

---

## Invocation

> `/migration-planner the invitations work needs a new invitations table plus a not-null joined_via column on members ('seed' | 'invitation' | 'manual') so we can tell where each member came from`

---

## 1. CHANGE SUMMARY

The EX-218 invitations work proposes **two** schema changes that ship together, with very different
risk profiles:

- **(A) `create_invitations`** — a brand-new `invitations` table belonging to `organizations`, carrying
  the invitee email, role, a digested token, status, expiry, and acceptance/auditing columns. This is
  the table the feature plan (`docs/plans/218_team-invitations.md`, commit `7f3c9a2`) describes. It is
  **additive and low-risk** — a new table holds zero existing rows, so there is no backfill, no
  constraint-over-existing-data, and no table-rewrite lock.

- **(B) `add joined_via to members`** — a **NOT NULL** `joined_via` string column (`'seed'` |
  `'invitation'` | `'manual'`) added to the **existing, populated, hot** `members` table so the product
  can report how each member arrived (seeded fixtures vs. an accepted invitation vs. the legacy manual
  DB insert). This is the **risky companion**: a NOT NULL constraint on a table that already has rows
  forces a backfill and, done naively, takes a table-rewriting lock on a table every authenticated
  request reads.

Echoing the parsed target so a wrong table/column is caught early: **new table `invitations`**, and
**new column `members.joined_via` (string, NOT NULL, one of `seed`/`invitation`/`manual`)**. If the
intent was actually a nullable provenance column, or a column on a different table, stop here — the
NOT NULL on the populated `members` table is the entire reason this dossier is non-trivial.

The two changes are analyzed together because they ship in the same EX-218 vicinity, but they are
**separable** and the dossier recommends shipping them as **separate migrations** (see §8): the
additive table can land in one shot; the NOT NULL column must go through EXPAND/CONTRACT.

## 2. DETECTED CONTEXT

- **Migration system + ORM:** ActiveRecord (Rails). Detected from `Gemfile` (`gem "rails"`),
  `db/migrate/*.rb`, and `db/schema.rb` as the schema source of truth. Recent migrations under
  `db/migrate/` were read to match cadence/style. **No `strong_migrations` gem is present** — meaning
  there is no automated guard that would reject the naive NOT NULL/`add_column ... null: false` at
  migrate time; the safety has to come from the phased plan below, not from tooling. (Adopting
  `strong_migrations` is noted in §11 as a worthwhile follow-up, but is out of scope for EX-218.)
- **Database engine + version:** **PostgreSQL** — detected from `config/database.yml`
  (`adapter: postgresql`) and the `docker-compose.yml` `db` service image. The lock analysis below is
  Postgres-specific. **Confirm the major version** (the `ADD COLUMN ... DEFAULT <constant>` fast-path
  and the behavior of `NOT NULL` validation differ by version) — see §11; the dossier assumes
  Postgres 11+ for the constant-default fast path and calls out the boundary inline.
- **Schema source of truth:** `db/schema.rb` (Rails schema dump). Current `members` columns, types,
  nullability, indexes, and FKs were read from it. If `db/schema.rb` is stale relative to migrations,
  the `members` facts in §3 must be re-confirmed against the live schema.
- **Governing `CLAUDE.md` migration rules honored:** every record is org-scoped and cross-tenant
  access must **404, not 403**; the new `invitations` table therefore carries `organization_id` and the
  feature reads it strictly through `current_organization.invitations`. The accept route is the feature's
  only unauthenticated surface and derives the org **from the invitation**, never from a request param.
  This dossier inherits those rules; the migration itself does not bypass them (it adds the scoping
  column and indexes that make them enforceable).

## 3. AFFECTED SCHEMA

### (A) New table — `invitations` (additive)

No existing rows; created empty. Proposed shape (from the EX-218 plan, commit `7f3c9a2`):

| Column            | Type       | Null     | Default     | Notes                                                |
| ----------------- | ---------- | -------- | ----------- | ---------------------------------------------------- |
| `id`              | bigint     | not null | identity    | PK                                                   |
| `organization_id` | bigint     | not null | —           | FK → `organizations`; tenant scope                   |
| `email`           | citext     | not null | —           | case-insensitive invitee email                       |
| `role`            | string     | not null | —           | `agent` \| `viewer` (never `owner`)                  |
| `token_digest`    | string     | not null | —           | SHA-256 digest; **raw token is emailed, never stored** |
| `status`          | string     | not null | `'pending'` | `pending` → `accepted`/`revoked`/`expired`           |
| `expires_at`      | datetime   | not null | —           | 7-day window                                         |
| `accepted_at`     | datetime   | null     | —           | set on acceptance                                    |
| `invited_by_id`   | bigint     | not null | —           | FK → `members`                                       |
| `created_at`      | datetime   | not null | —           | timestamps                                           |
| `updated_at`      | datetime   | not null | —           | timestamps                                           |

Indexes on the new table:
- `unique (token_digest)` — single-use lookup by digest.
- `unique partial (organization_id, email) WHERE status = 'pending'` — at most one open invite per
  email per org; two different orgs may each hold a pending invite for the same email.
- `index (organization_id)` — the list query.

Because the table is empty at create time, **all three indexes build instantly** — there are no rows to
scan, so `CREATE INDEX` vs `CREATE INDEX CONCURRENTLY` is immaterial *for the create-table migration*.
The partial-unique-index concurrency caveat in §6 applies only if this index is ever added to an
**already-populated** table (it is not, here) — it is documented so the pattern isn't misapplied later.

### (B) Existing table — `members` (the risky target)

Current shape relevant to the change (from `db/schema.rb`):

| Column            | Type     | Null     | Default | Notes                          |
| ----------------- | -------- | -------- | ------- | ------------------------------ |
| `id`              | bigint   | not null | —       | PK                             |
| `organization_id` | bigint   | not null | —       | FK → `organizations`           |
| `user_id`         | bigint   | not null | —       | FK → `users`                   |
| `role`            | string   | not null | —       | `owner` \| `agent` \| `viewer` |
| `created_at`      | datetime | not null | —       | —                              |
| `updated_at`      | datetime | not null | —       | —                              |

Proposed addition: **`joined_via` (string, NOT NULL, one of `seed`/`invitation`/`manual`)**.

**Row count / table size — "verify against prod-like data."** This is the load-bearing unknown: the
risk of a NOT NULL add scales with the live `members` row count, and no prod-like read source was
provided, so no number is invented here. `members` is a **hot** table (read on every authenticated
request to resolve the actor's org + role), which matters more for *lock contention* than raw size —
even a brief exclusive lock on `members` stalls every in-flight request. Measure before shipping:

```sql
SELECT count(*) FROM members;                         -- row count
SELECT pg_size_pretty(pg_total_relation_size('members'));  -- table + index + TOAST size
SELECT count(*) FROM members WHERE joined_via IS NULL;     -- (post-add) rows still needing backfill
```

## 4. RISK CLASSIFICATION

| Change                          | Classes                                                                 | One-line justification                                                                                  |
| ------------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| (A) `create_invitations`        | **(none — additive)**                                                    | New empty table; no existing rows to lock, lose, backfill, or violate a constraint.                    |
| (B) `members.joined_via`        | **LOCK / DOWNTIME** + **BACKFILL-required** + **CONSTRAINT-over-existing-data** | NOT NULL on a populated, hot table: it must be backfilled for every existing row, and the constraint must be validated over data already present. Done naively it takes a table-rewriting `ACCESS EXCLUSIVE` lock. |

Not DATA-LOSS: the change adds a column and never drops, narrows, or transforms existing data. The
risk is **availability** (locks/downtime on `members`), not destruction.

## 5. DATA-LOSS RISKS

**No data-loss risk.** Both changes are additive: `create_invitations` makes a new table, and
`joined_via` adds a column. Nothing is dropped, no type is narrowed, no existing value is overwritten,
and no unique constraint is added over `members` (the new uniqueness lives only on the empty
`invitations` table). The single subtlety is **correctness of the backfilled value**, not loss: if the
backfill mislabels existing members (e.g. tags every legacy row `'manual'` when some were truly seeded
fixtures), no data is *lost*, but the provenance column is *wrong* — handled in §7 by deriving the
backfill value from evidence (members linked to an accepted invitation → `'invitation'`; the seed
fixtures' known ids → `'seed'`; everything else → `'manual'`) rather than a blanket default.

## 6. LOCK / DOWNTIME RISKS — by database (PostgreSQL)

The detected engine is PostgreSQL; the analysis is engine-specific. The danger is entirely in change
**(B)**; change (A) on an empty table takes only a trivial metadata lock.

**The naive one-shot (what to AVOID):**

```ruby
add_column :members, :joined_via, :string, null: false, default: "manual"  # <-- the trap
```

What Postgres does with that, by version:
- **Postgres 11+** — adding a column with a **constant** default is a *metadata-only* change: Postgres
  stores the default in the catalog and does **not** rewrite existing rows. The `ALTER TABLE` still
  takes a brief **`ACCESS EXCLUSIVE`** lock (it blocks **reads and writes** for the moment it holds),
  but the lock is short and constant-time, not proportional to row count. The hazard is **lock-queue
  pileup**: an `ACCESS EXCLUSIVE` request queues *behind* any long-running query on `members` and, while
  it waits, every subsequent query on `members` queues *behind it* — so a brief exclusive lock landing
  behind one slow query can stall the whole hot table for the duration of that slow query. Mitigate with
  a short `lock_timeout` and a retry, off-peak timing, and killing long readers first.
- **Pre-Postgres 11** — a `DEFAULT` on `ADD COLUMN` forces a **full table rewrite** under
  `ACCESS EXCLUSIVE` for the entire rewrite: duration scales with table size, and `members` is locked
  for **reads and writes** the whole time. On a large hot table this is a multi-second-to-minutes
  outage. This is the version boundary that makes "confirm the Postgres major version" (§11) load-bearing.

Even on 11+, the constant-default one-shot is **still wrong for this feature** because a single blanket
default (`'manual'`) mislabels members who actually arrived via seed or invitation (§5/§7) — the
provenance is the point of the column. So the phased path isn't only about the lock; it's about
backfilling the *correct* value per row.

Other Postgres-specific lock facts that bound the safe path:
- **NOT NULL validation.** Flipping a column to `NOT NULL` via `ALTER TABLE ... ALTER COLUMN ... SET NOT
  NULL` scans the whole table under `ACCESS EXCLUSIVE` to prove no NULLs remain — duration scales with
  row count, locking reads+writes. The safe pattern (§8) adds a `CHECK (joined_via IS NOT NULL) NOT
  VALID` first (instant, no scan), then `VALIDATE CONSTRAINT` (scans under a weaker **`SHARE UPDATE
  EXCLUSIVE`** lock that does **not** block reads or writes), and only then sets the catalog `NOT NULL`
  cheaply (Postgres 12+ can use the validated CHECK to skip the full scan).
- **`CREATE INDEX` vs `CREATE INDEX CONCURRENTLY`.** Not needed for change (B) (no index added to
  `members`), but stated for completeness and because the **partial unique index** on `invitations`
  *would* be a hazard if that table were ever populated before the index existed: a plain `CREATE INDEX`
  takes a lock that **blocks writes** for the build (duration scales with row count), whereas
  `CREATE INDEX CONCURRENTLY` builds without blocking writes but **cannot run inside a transaction**
  (requires `disable_ddl_transaction!` in Rails) and can leave an `INVALID` index on failure that must
  be dropped and rebuilt. For EX-218 the `invitations` indexes build on an empty table, so this is
  informational — apply `CONCURRENTLY` only when indexing a populated table.

**Duration estimates — "verify against prod-like data."** No lock duration is asserted here. Measure on
a prod-sized staging copy:

```sql
EXPLAIN (ANALYZE, BUFFERS) ALTER TABLE members ADD COLUMN joined_via varchar;  -- shape, not a prod run
-- time the backfill batch and the VALIDATE CONSTRAINT scan on staging; record the longest readers on members
SELECT pid, now() - query_start AS runtime, query
FROM pg_stat_activity WHERE state = 'active' ORDER BY runtime DESC LIMIT 10;
```

## 7. BACKFILL STRATEGY

Required for change (B) only. The column is added **nullable first** (§8 Expand), then existing rows
are populated **outside the schema-change transaction**, in **batches**, with a **correct** per-row
value rather than a blanket default:

- **Derive, don't blanket.** For each existing member, set `joined_via` by evidence, in priority order:
  1. member is referenced by an `accepted` invitation (once `invitations` exists) → `'invitation'`;
  2. member id is in the known seed-fixture set → `'seed'`;
  3. otherwise (the legacy manual DB-insert path EX-218 is replacing) → `'manual'`.
- **Batched + throttled.** Update in id-ranged chunks (e.g. 5–10k rows per batch — tune against the
  measured row count from §3), with a short pause between batches, so no single transaction holds a long
  lock and replication/replica lag stays bounded. Run it as a one-off rake task or an idempotent job,
  **not** inside the migration transaction.
- **Idempotent + restart-safe.** Each batch updates only `WHERE joined_via IS NULL` (and id in range), so
  a re-run or a crash-resume never double-writes and never overwrites an already-correct value. The job
  can be killed and restarted at any point.
- **Verify completion before enforcing.** The NOT NULL constraint is flipped (§8 Enforce) **only after**
  `SELECT count(*) FROM members WHERE joined_via IS NULL;` returns **0**. New writes during the backfill
  window must already supply `joined_via` (the dual-write deploy in §8 guarantees this), so the
  "remaining NULLs" count converges to zero and stays there.

## 8. EXPAND / CONTRACT (parallel-change) ROLLOUT

Change **(A) `create_invitations`** needs no EXPAND/CONTRACT — it is additive and non-locking on an
empty table; ship it as a single migration (recommend `/chore`, see §12). The phased path below is for
change **(B) `members.joined_via`** only, and is what avoids the table-locking one-shot in §6.

**Naive one-shot (rejected):** `add_column :members, :joined_via, :string, null: false, default:
"manual"` — takes an `ACCESS EXCLUSIVE` lock on the hot `members` table (a full rewrite pre-PG11; a
lock-queue-pileup hazard even on 11+), **and** mislabels seed/invitation members with a blanket
`'manual'`. Rejected on both lock and correctness grounds.

**Phased path (zero downtime):**

1. **Expand (deploy 1, migration).** `add_column :members, :joined_via, :string` — **nullable, no
   default, no constraint.** On PG11+ this is a fast metadata-only change taking only a brief lock; no
   rewrite, no scan. App code still reads/writes the old shape (column ignored).
2. **Backfill (job/step, no deploy).** Run the batched, throttled, idempotent backfill from §7 to
   populate `joined_via` for all existing rows with the *derived* value. Runs outside any schema
   transaction; safe to pause/resume. Independently runnable and re-runnable.
3. **Migrate-the-code (deploy 2).** App now **writes `joined_via` on every new member**: the EX-218
   acceptance path sets `'invitation'`, the seed path sets `'seed'`, any remaining admin/manual path sets
   `'manual'`. This dual-guarantees no *new* NULLs are created while the backfill finishes the old ones.
   The app still tolerates the column being absent in reads (defensive) until enforced.
4. **Enforce (deploy 3, migration).** Only after the §7 verification shows **0** remaining NULLs:
   add `CHECK (joined_via IS NOT NULL) NOT VALID` (instant), `VALIDATE CONSTRAINT` (scans under
   `SHARE UPDATE EXCLUSIVE` — does **not** block reads/writes), then `change_column_null :members,
   :joined_via, false` (cheap on PG12+ given the validated CHECK). Optionally add a `CHECK (joined_via
   IN ('seed','invitation','manual'))` the same `NOT VALID` → `VALIDATE` way to pin the allowed set at
   the DB layer.
5. **Contract (deploy 4, optional bake).** There is no *old* column to drop here (this is an add, not a
   replace), so "Contract" is light: after a bake period confirming no NULLs and no constraint
   violations, remove any defensive "column may be absent" read-fallbacks added in step 3. If the
   redundant `NOT NULL`-mirroring CHECK was only scaffolding for the flip, it may be dropped once the
   catalog `NOT NULL` is in place.

**Independently deployable / gates:** steps 1, 3, 4 are separate migrations; step 2 is a job; step 3 is
the app deploy that closes the new-NULL hole. The hard gate sits **before step 4**: do not enforce NOT
NULL until both (a) the backfill verification returns 0 NULLs **and** (b) the dual-write deploy (step 3)
is live so nothing creates fresh NULLs. Skipping the gate reintroduces the full-scan-under-lock risk the
phasing exists to avoid.

## 9. ROLLBACK PLAN

Per phase, with an honest reversibility verdict.

- **(A) `create_invitations` — REVERSIBLE.** `drop_table :invitations`. The table is new and (pre-launch)
  empty or holds only invitation rows, which are feature-local; dropping it touches no `members` or other
  existing data. Standard Rails reversible migration.
- **(B) `members.joined_via`, per phase:**
  - **Expand (step 1) — REVERSIBLE.** `remove_column :members, :joined_via`. Drops the nullable column;
    no existing `members` data is altered by adding/removing it.
  - **Backfill (step 2) — REVERSIBLE-WITH-CAVEAT.** The backfill only writes a previously-NULL column;
    reverting means dropping the column (above), which discards the derived values. No *pre-existing*
    member data is mutated by the backfill, so nothing original is lost — only the newly-derived
    provenance, which is recomputable by re-running the job. No snapshot needed.
  - **Enforce (step 3/4) — REVERSIBLE.** Drop the `NOT NULL` (`change_column_null :members, :joined_via,
    true`) and drop the CHECK constraints. Cheap, no data change.

**Overall verdict: REVERSIBLE.** Nothing in this change destroys or narrows existing data, so there is no
irreversible step and no "reversibility theater" to flag — a genuine `down` exists for every phase. The
real recovery path is the ordinary migration `down` plus a standard pre-migration database snapshot kept
as defense-in-depth (recommended for any change touching a hot table, even a reversible one), **not**
because data would otherwise be unrecoverable.

## 10. BLAST RADIUS

Code that reads or writes the affected schema, and must move in lock-step with the EXPAND/CONTRACT
deploys. Grep was scoped to the ORM model/controller/serializer/test layers and bounded to the two
affected tables; references below are illustrative `file:line` against the fictional ExampleApp source
(not silently truncated — the grep patterns used are listed so the downstream implementer can re-run
them).

**Writers of `members.joined_via` (must set it once step 3 lands):**
- `app/controllers/invitation_acceptances_controller.rb:41` — `#update` creates the `Member` on
  acceptance; must set `joined_via: "invitation"`. (commit `b8e41d6` introduces this controller.)
- `db/seeds.rb` — seed members must set `joined_via: "seed"`.
- `app/controllers/settings/members_controller.rb` — any remaining admin/manual create path sets
  `joined_via: "manual"`.
- `spec/factories/members.rb` — the `:member` factory must default `joined_via` (e.g. `"seed"`) so every
  spec that builds a member satisfies the future NOT NULL.

**Readers of `members.joined_via` (the reason the column exists):**
- `app/models/member.rb` — model attribute; add the allowed-values validation mirroring the DB CHECK and
  any `scope :via_invitation`.
- `app/frontend/pages/settings/Members.tsx` — surfaces provenance in the members list (if shown).
- Any reporting/serializer that exposes member provenance.

**`members` table generally (verify the NOT NULL doesn't break a bulk-insert path):**
- `spec/factories/members.rb`, fixtures, and any `insert_all`/`upsert_all` on `members` — these bypass
  model defaults and will violate the new NOT NULL unless they supply `joined_via`. This is the easiest
  thing to miss.

**New `invitations` table consumers (additive, EX-218 plan):**
- `app/models/invitation.rb`, `app/controllers/settings/invitations_controller.rb`,
  `app/controllers/invitation_acceptances_controller.rb`, `app/mailers/invitation_mailer.rb`,
  `app/models/organization.rb` (`has_many :invitations`) — all new in commit `b8e41d6`; they read/write
  the new table but do not touch existing data.

**Grep patterns used (re-runnable by the implementer):**
```
grep -rn "joined_via" app/ lib/ db/ spec/
grep -rn "\.members\b\|:members\b\|create(:member\|build(:member" app/ lib/ db/ spec/
grep -rn "insert_all\|upsert_all" app/ lib/ | grep -i member
```

## 11. VERIFY-BEFORE-SHIP CHECKLIST

Run these read-only checks against prod-like data to turn every "verify against prod-like data" mark
into a real number, **before** committing to the phased plan:

1. **Confirm Postgres major version** — `SELECT version();`. This decides whether the constant-default
   add is metadata-only (11+) or a full rewrite (pre-11), and whether the validated-CHECK NOT NULL flip
   can skip the scan (12+). This is the single most important pre-flight fact.
2. **Measure `members`** — `SELECT count(*) FROM members;` and
   `SELECT pg_size_pretty(pg_total_relation_size('members'));`. Sizes the backfill batch count and the
   VALIDATE scan duration.
3. **Find long readers on `members`** — `SELECT pid, now() - query_start AS runtime, query FROM
   pg_stat_activity WHERE state = 'active' ORDER BY runtime DESC LIMIT 10;`. A brief `ACCESS EXCLUSIVE`
   behind one of these stalls the hot table (§6); schedule the `ALTER` when none are running and set a
   short `lock_timeout` with retry.
4. **Inventory NULL-violating write paths** — confirm no `insert_all`/`upsert_all`/`COPY` into `members`
   would violate the future NOT NULL (the blast-radius grep in §10).
5. **Staging dry-run** — apply the full phased sequence (Expand → backfill → dual-write → Enforce)
   against a prod-sized sanitized staging copy; **time** the backfill batches and the `VALIDATE
   CONSTRAINT` scan, and confirm reads/writes on `members` are not blocked during VALIDATE. Confirm
   `SELECT count(*) FROM members WHERE joined_via IS NULL;` reaches 0 before enforcing.
6. **(Recommended, not EX-218-scoped)** Consider adopting `strong_migrations` so the naive
   `add_column ... null: false` is rejected at migrate time and future contributors get the guardrail
   for free.

All of the above are read-only or staging-only. **No DDL/DML is run against production by this skill** —
the dry-run is the human's step.

## 12. RECOMMENDED HANDOFF

Two separable pieces, two recommendations:

- **(A) `create_invitations`** → **`/chore`-sized in isolation** (additive, no backfill, no lock,
  no constraint-over-existing-data). However, since it lands as part of the EX-218 feature PR alongside
  the model/controller/mailer work (commit `b8e41d6`), it rides the feature's normal pipeline rather than
  a standalone chore.
- **(B) `members.joined_via`** → **`@developer` (full pipeline).** It is a genuine multi-deploy
  EXPAND/CONTRACT (add nullable → batched backfill → dual-write deploy → enforce NOT NULL), touches a
  hot table, and requires the cross-deploy gate in §8. It must not be collapsed into a single migration.

**Recommended split:** ship `joined_via` as its **own** migration sequence, separate from the
`invitations` table migration, so the additive table is not held hostage to the phased NOT NULL rollout.

---

## HANDOFF GATE (human-in-the-loop)

This dossier is analysis only. The `/migration-planner` skill does **not** write or run either
migration. The next step is a human decision:

> **Hand this off to implement, or stop here?**
> - **Hand off to `@developer`** — for the phased `members.joined_via` EXPAND/CONTRACT rollout
>   (multi-deploy). The skill surfaces the recommended invocation string; it does not invoke it.
> - **Hand off to `/chore`** — for the additive `create_invitations` table, if shipped on its own.
> - **Stop here — I'll take it from the dossier.**

The skill never interprets "looks good" or silence as approval, and never writes or runs the migration
itself. Implementation — and its own commit/push gates — belongs to the downstream agent.

---

## How to read this example

- **Two changes, two risk profiles, one dossier:** the additive `create_invitations` table is honestly
  marked low-risk, while the NOT NULL `members.joined_via` companion is the reason the dossier exists —
  the skill does not manufacture risk for the safe change or hand-wave the dangerous one.
- **Numbers are never invented:** every row count and lock duration is marked **"verify against prod-like
  data"** with the exact `SELECT count(*)` / `pg_total_relation_size` / `EXPLAIN` query to measure it.
- **The lock analysis is engine- and version-specific:** Postgres `ACCESS EXCLUSIVE` behavior, the
  PG11 constant-default boundary, `VALIDATE CONSTRAINT` under `SHARE UPDATE EXCLUSIVE`, and
  `CREATE INDEX CONCURRENTLY` are all called out by version — because the safe path depends on them.
- **The safe path is always present:** the dossier rejects the naive one-shot and gives the full
  EXPAND/CONTRACT (add nullable → backfill → dual-write → enforce NOT NULL) with named deploy gates.
- **It stays read-only and human-gated:** it ends at a recommended handoff and a gate; it never writes
  or runs the migration.
