# Sample tests — `@test-author` output

> Illustrative RSpec specs the `@test-author` agent would write for ExampleApp's EX-218 "Team invitations" — negative-path-first, not wired to run here.

These three spec files are frozen sample artifacts: representative output of the
[`@test-author`](../../agents/test-author.md) agent, the focused negative-path
test-deepening agent that closes the "missing test" gap a reviewer flags. They
cover the **EX-218 Team invitations** feature whose issue, plan, and acceptance
criteria live in [`../sample-issue.md`](../sample-issue.md) and
[`../sample-plan.md`](../sample-plan.md). They map directly to that plan's
**Test plan** section.

The app under test is the fictional **ExampleApp** — a multi-tenant B2B SaaS
helpdesk (Organization → Member [owner/agent/viewer] → Ticket → Billing) on
Rails + PostgreSQL + React, tested with RSpec + FactoryBot. Its load-bearing
rule is that **every record is org-scoped and cross-tenant access returns 404,
not 403**. See [`../README.md`](../README.md) for the full ExampleApp domain.

## What's here

| File | Layer | Pins |
| --- | --- | --- |
| [`invitation_spec.rb`](./invitation_spec.rb) | model | raw token never persisted (digest only); `expired?` boundary; `pending` scope exclusions; the partial-unique index (one open invite per email per org); the same email free across two orgs. |
| [`invitations_request_spec.rb`](./invitations_request_spec.rb) | request | owner create → 201 + mailer enqueued; agent/viewer create → 403; existing-member invite → 422, no row; re-invite reuses the row + resends; revoke flips status and kills the link; **cross-tenant → 404**. |
| [`invitation_acceptances_request_spec.rb`](./invitation_acceptances_request_spec.rb) | request | the only unauthenticated surface — unknown token → 404 (no shape leak); expired token → no member; double-accept → redirect, no duplicate; acceptance ignores any org param and binds to the invitation's org. |

## How to read them

`@test-author` **leads with the negative-path catalog** — authorization denial,
cross-tenant isolation, validation failures, expiry/lifecycle edges, and
idempotency under retry come first; the single confirming happy-path example is
asserted last in each file. That ordering is deliberate: the negative paths are
the value, and the happy path is table stakes. Each `describe`/`context`/`it`
names the behavior it pins, so no test exists just to inflate a coverage number.

These are **documentation, not a runnable suite** — there is no ExampleApp app,
schema, factories, or `rails_helper` in this repo, so they will not execute
here. In a live run the agent would write the equivalent specs into the target
repo's `spec/` tree, run them against the real runner, and report honest
green/pending results before handing back for a human-gated commit. They use
only idiomatic RSpec + FactoryBot (`describe`/`context`/`it`, `let`, factories,
`enqueued_jobs`) so they read like real output of that run.
