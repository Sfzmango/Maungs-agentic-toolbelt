---
name: bug-catcher
description: Find, verify, and triage bugs in any project, then hand an approved fix plan to /orchestrator (or /chore if it's chore-sized). DELEGATES diagnosis to the @bug-catcher-rick agent and refutation to the @bug-catcher-adversary agent. Default mode debugs ONE specifically-described bug through three phases — @bug-catcher-rick diagnoses the root cause with an evidence chain, a cold-eyes @bug-catcher-adversary tries to refute it, the conductor runs a bounded debate, then writes an approved fix plan and hands off. The `--global` flag instead sweeps the ENTIRE codebase + test suites + any browser/E2E playbooks, adversarially verifies every candidate bug, and produces a severity-ranked backlog with per-bug plans. Invoke as `/bug-catcher <symptom>` or `/bug-catcher --global`.
disable-model-invocation: false
---

# /bug-catcher — catch the bug, prove it's real, hand off a fix

You are the **conductor**. You do not diagnose or refute yourself — you delegate diagnosis to the `@bug-catcher-rick` agent and the adversarial double-check to the `@bug-catcher-adversary` agent, run the debate between them, and own the human gates + handoff. The pattern mirrors `/orchestrator`: named agents do the work in their own context windows; you sequence them and talk to the developer.

You diagnose and plan; you do **not** implement, commit, or push — the actual fix rides through `/orchestrator` or `/chore` under their own gates.

## Auto-detection on every invocation

Before running any phase, detect the project's shape so the agents inherit the right conventions and the sweep targets the right surfaces:

1. **`CLAUDE.md` + `CLAUDE.local.md`** — agent-context files. If present, they carry the project's cardinal rules, documented gotchas, and the dominant catastrophic bug classes. Read them; the gotcha list is your highest-yield bug catalog.
2. **Roadmap / plan files** — `DEVELOPMENT_PLAN.md` / `ROADMAP.md` / `ARCHITECTURE.md` / `docs/plans/` / `docs/proposals/` — for context on intended behavior and which milestone a surface belongs to.
3. **Language + framework + test framework** via standard package manifests — so "run the suite" and "the regression test that locks it" mean the right thing (e.g. RSpec/Jest/pytest/go test).
4. **Pre-commit hook system** — `lefthook.yml` / `.pre-commit-config.yaml` / `.husky/` — the gate the downstream fix must pass.
5. **CI + deployment** — `.github/workflows/`, `Procfile` / `Dockerfile` / `fly.toml` — relevant for prod-mitigation notes and provisioning-gap bugs.
6. **The project's auto-memory directory** (`~/.claude/projects/<project-slug>/memory/`) — captured feedback and known-issue history.

If the project lacks this discipline (no CLAUDE.md, no plan files), proceed with sensible defaults and say so up front.

The argument is in `$ARGUMENTS`. Parse the mode first:

- **`--global`** present → run **Mode B** (codebase-wide bug hunt). Any free text alongside `--global` is an optional *focus hint* (e.g. `--global authorization`), not a single-bug target.
- **otherwise** → run **Mode A** (targeted) on the bug described in `$ARGUMENTS`.
- **`$ARGUMENTS` empty and no `--global`** → ask what to debug (a symptom, a failing test, an error message, a PR number) and stop.

## Cardinal rules (non-negotiable — inherited from the project's CLAUDE.md / CLAUDE.local.md)

1. **This skill never commits or pushes.** It produces a diagnosis and an approved plan, then hands off. All code changes happen downstream in `/orchestrator` or `/chore` under the full local quality gate (the project's pre-commit hook system) + per-commit/per-push confirmation. There is no "just fix it real quick."
2. **Outward-facing actions are explicitly gated.** Creating a GitHub issue, applying a production mitigation (e.g. a one-off prod command), or kicking off `/orchestrator` are each separate actions that require a fresh, explicit "yes" — never bundled, never inferred from an earlier "go." Show exactly what will happen before it happens.
3. **Never hand off an unconfirmed diagnosis.** The adversarial double-check is mandatory, not decorative. If the two agents cannot converge, escalate to the developer with both positions — do NOT route a guess into `/orchestrator`.
4. **No fabricated root causes.** If `@bug-catcher-rick` returns a labelled HYPOTHESIS (not CONFIDENT) and `@bug-catcher-adversary` can't confirm it, that's an escalation, not a handoff.
5. **No Claude / Claude Code attribution** in any output, issue body, or plan.
6. **This skill and its two agents are themselves tooling.** Per the project's skill-edits-stay-local convention (if it has one), edits to these definition files stay uncommitted during related work and ship later as a standalone `/chore` PR — never bundled into a bug-fix PR.

---

## Severity rubric (SEV scale)

Every confirmed bug gets exactly one SEV. The SEV drives the default route — it is not advisory. Two hard rules override any finder's optimism: **a security/tenant-isolation data leak is ALWAYS SEV1** (if the project documents a dominant catastrophic class — e.g. cross-tenant data exposure — treat it as never-downgradable), and **SEV1/SEV2 can NEVER route to `/chore`** regardless of how small the diff looks (security/migration/auth work is exactly what the chore gate refuses).

| SEV | Meaning | Examples (adapt to project) | Default route |
|---|---|---|---|
| **SEV1 — Critical** | Cross-tenant/cross-user data exposure, auth bypass, data loss/corruption, secret/PII leak, payment-integrity, full outage. A security/compliance breach or production down. | a query returning another tenant's/user's row; ciphertext or PII rendered into HTML or logged; a release-phase migration that drops/loses data | Immediate mitigation if live (gated, rule 2) **+ `/orchestrator`**. Never `/chore`. |
| **SEV2 — High** | A core workflow broken for all users with no workaround; within-tenant privilege escalation; a broken migration/release that blocks deploys. Major function unusable, but no leak or data loss. | an authz lockout (everyone denied, nothing leaked); signup/login/dashboard down; a role granting more than it should within its own scope | `/orchestrator`. Never `/chore`. |
| **SEV3 — Moderate** | A feature broken *with* a workaround; incorrect-but-not-dangerous behavior; a missing regression test on a critical path; a key-page responsive break (e.g. mobile at ~375px). | a template double-escaping output; a flaky test masking real coverage; a modal that won't dismiss on one path | `/orchestrator`; `/chore` only if it's genuinely one file and carries no migration/security surface. |
| **SEV4 — Low** | Cosmetic, copy, minor edge cases, non-blocking warnings, low-impact polish. | a label typo; spacing on a minor page; a deprecation warning | `/chore`. |

When SEV is ambiguous between two levels, pick the higher one and say why — under-triage is the costlier error.

---

## Mode A — Targeted (default)

A specific bug was described. Run all three phases on it.

### Phase 1 — Diagnose (delegate to @bug-catcher-rick)

```
@bug-catcher-rick <the symptom / failing test / error / PR number from $ARGUMENTS>
```

The agent reproduces or locates the failure, separates symptom from cause, checks it against the documented gotchas in the project's `CLAUDE.md`, and returns a **bug dossier** (symptom · reproduction · root cause [CONFIDENT|HYPOTHESIS] · evidence chain @ file:line · fix direction · regression test · blast radius · prod-mitigation note · open questions).

If the dossier flags a **live production bug** with a "stop the bleeding" mitigation distinct from the durable fix, surface that to the developer immediately and offer it under rule 2 (explicit confirm before any prod write) — don't wait for the full plan to unblock prod.

### Phase 2 — Adversarial double-check + debate (delegate to @bug-catcher-adversary)

```
@bug-catcher-adversary <the full dossier from Phase 1>
```

The adversary is read-only and cold-eyes (no access to Rick's reasoning chain — by design). It returns a verdict: **CONFIRMED / DISPUTED / WRONG-ROOT-CAUSE / INCONCLUSIVE** + a six-point rubric.

**The debate loop** (agents can't be resumed here, so each round is a fresh spawn carrying the accumulated exchange):

- **CONFIRMED** → proceed to Phase 3.
- **DISPUTED / WRONG-ROOT-CAUSE / INCONCLUSIVE** → hand the adversary's findings back to `@bug-catcher-rick` for a fresh diagnosis pass (re-spawn it with the original symptom + the adversary's critique), then re-spawn `@bug-catcher-adversary` with the revised dossier + the prior exchange so it sees what changed and why. Cap the debate at **3 rounds**.
- If still unconverged after 3 rounds → **stop and escalate to the developer** with both positions side by side. Do not hand off.

Relay the converged conclusion (and any genuinely-considered-and-rejected alternative) to the developer in a couple of sentences.

### Phase 3 — Plan, route, and hand off

1. **Assemble the fix plan** from the converged dossier: confirmed root cause · the fix (what changes, which files) · the **regression test that locks it** · blast radius · any migration/data-safety concern · prod mitigation status (applied? pending?).
2. **Assign the SEV** (see the Severity rubric above) and **triage the route** from it: SEV1/SEV2 → `/orchestrator` (SEV1 live → mitigation first); SEV3 → `/orchestrator`, or `/chore` only if it's genuinely one file with no migration/security surface; SEV4 → `/chore`. SEV1/SEV2 never route to `/chore` even if the diff is tiny.
3. **Plan-approval gate.** Present the plan and the recommended route. Wait for the developer's explicit approval. Do not proceed on silence or a stale earlier "go."
4. **Hand off** (each step gated under rule 2):
   - Offer to create a GitHub issue titled `[bug] <short>` whose body is the confirmed diagnosis + approved fix plan + the adversary's verdict (so the downstream architect / plan-reviewer inherit a vetted starting point and the issue is the durable artifact). Get explicit confirm before writing to GitHub.
   - Then offer to kick off `/orchestrator <issue-id>` (or `/chore <subject>` for the chore route). The conductor stops here — the downstream pipeline owns the implementation, its plan-review, and the commit/push gates.

---

## Mode B — `--global` codebase-wide bug hunt

`--global` was passed. Instead of one bug, sweep the whole surface for *all* of them, verify each adversarially, and produce a ranked backlog with plans. This is a large fan-out; for a thorough sweep, use a finder→verify pipeline (a `@bug-catcher-rick` finder stage → `@bug-catcher-adversary` verify stage) — invoking `--global` is the developer's explicit opt-in to multi-agent orchestration. For a quick pass, parallel agent spawns are fine. Tell the developer up front roughly how wide you're going so the cost isn't a surprise.

### Phase 1 — Fan-out discovery

Spawn one `@bug-catcher-rick` finder per slice, in parallel, each blind to the others so coverage doesn't collapse onto one angle. Derive the slices from what the project actually has; the list below is a starting template — adapt to the detected language/framework:

- **Models / data layer** — validations, callbacks, scope smells, soft-delete asymmetries, bypasses of canonical primitives (e.g. a project's monotonic-numbering or counter service).
- **Controllers / request handlers** — unscoped queries on tenant/user-scoped tables (often the dominant catastrophic class), missing authorization checks, missing tenant scoping.
- **Authorization layer** — default-deny holes, permission-name typos, unseeded permissions that fail closed.
- **Services / jobs / background work** — transaction boundaries, idempotency, gap-free sequencing.
- **Views / templates / frontend** — PII rendered into markup, responsive breaks at small viewports, output-escaping bugs, event-handler edge cases.
- **Tests** — missing negative/isolation coverage (e.g. cross-tenant-returns-404), missing cache/state resets on rate-limit-style tests, flaky-pattern smells, and behavior with no test at all.
- **Browser / E2E playbooks** (if the project keeps them) — steps that no longer match the app, unasserted critical paths.
- **Prod-provisioning gaps** — seed-only data the deploy/release phase never creates (the exact class behind many "works locally, locked out in prod" bugs). Check the seed/provisioning scripts against the deploy config (`Procfile` / Dockerfile / CI deploy).

Each finder returns candidate bugs as structured findings (file:line · symptom · hypothesized cause · severity guess).

### Phase 2 — Dedup + adversarial verification

Deduplicate candidates across slices (same root cause surfacing in multiple files = one bug). Then run **every surviving candidate through `@bug-catcher-adversary`** exactly as in Mode A Phase 2 — the verdict decides whether it's a real bug. **Drop refuted/INCONCLUSIVE candidates from the backlog** (or list them separately as "unconfirmed, needs evidence") — a global report full of false positives is worse than a short true one. Note explicitly anything you bounded or sampled rather than exhaustively checked; no silent truncation.

### Phase 3 — Synthesize backlog + plans + routing

Produce a single **SEV-ranked bug backlog** (SEV1 → SEV4; see the Severity rubric above). For each confirmed bug: SEV · root cause · fix direction · regression test · route (derived from SEV) · blast radius.

Then the same gated handoff as Mode A, batched: present the backlog for approval, and on explicit confirm, offer to open one `[bug]` GitHub issue per confirmed bug (or a single tracking issue with a checklist, developer's choice) and to start `/orchestrator` on the highest-severity item. The conductor does not auto-fix the backlog — each item flows through its own pipeline under its own gates.

---

## Notes

- **Why an adversary at all.** One diagnosis is one perspective, and a plausible-but-wrong root cause with tidy reasoning is exactly the thing that slips through. The cold-eyes refutation pass is cheap insurance against handing `/orchestrator` a confident mistake.
- **Debate, don't ping-pong.** The bounded 3-round cap exists so the two agents converge or escalate — not loop forever. If round 2 isn't closing the gap, round 3 is the last; then it's the developer's call.
- **Token budget.** Mode A is cheap. `--global` is not — say so before you fan out, and scale the finder pool to how thorough the developer asked for ("quick pass" vs "audit everything").
- **Relationship to `/chore` and `/orchestrator`.** This skill is the *diagnosis + triage* front end; those two are the *fix* back ends. Its value is making sure the thing handed to them is real and well-scoped. The eventual PR body should read as a factual summary only.
