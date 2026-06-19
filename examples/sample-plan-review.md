> Example `@plan-reviewer` output for the fictional **ExampleApp** — a cold, context-blind review of the EX-218 plan (`docs/plans/218_team-invitations.md`).

---

This is a frozen sample of what `@plan-reviewer` returns to the caller (the
conductor relays it to the architect). The agent reviews the plan file BEFORE it
is committed, with **no** access to the planning conversation or the architect's
reasoning — a deliberately independent second opinion. It reads `CLAUDE.md`, the
plan in full, the GitHub issue, and the touched code, then scores against an
8-point rubric and returns a verdict plus a findings list.

The review below is **of** [`sample-plan.md`](./sample-plan.md) (the EX-218
"Team invitations" plan, file `docs/plans/218_team-invitations.md`, plan commit
`7f3c9a2`). The verdict is **SOLID** — the plan is strong; the findings are
minor and don't block the commit.

---

```
VERDICT: SOLID
FAIL count: 0   CONCERN count: 4

Findings:

1. [CONCERN] Blast radius / Architecture — The public accept route
   (`GET /invitations/accept`) and the owner-triggered `resend` are a
   brute-force surface, but the plan names rate-limiting only obliquely: the
   Blast-radius section lists "token guessing" as a risk and leans entirely on
   the digest-at-rest lookup + expiry + single-use status to mitigate it. Those
   controls make a *single* guess useless; they do nothing to throttle a
   high-volume guessing loop against `/invitations/accept`, and `resend` is an
   un-throttled email-amplification lever (an attacker who knows a target email
   can spam invite mail). Add an explicit rate-limit control on both the public
   accept route and `resend` — per-IP on accept, per-(actor, invitation) on
   resend — and write it into the plan as a named mitigation plus a request-spec
   assertion, not an implied property of the token scheme.

2. [CONCERN] Migrations — The partial unique index on
   `(organization_id, email) WHERE status = 'pending'` is correct and exactly
   the right shape for "at most one open invite per email per org," but the
   migration doesn't state how it's built. On PostgreSQL a plain `CREATE INDEX`
   takes an `ACCESS EXCLUSIVE`-adjacent lock; the zero-downtime form is
   `CREATE INDEX CONCURRENTLY` (which in Rails means `disable_ddl_transaction!`
   + `algorithm: :concurrently`). For THIS migration the table is brand-new and
   empty, so the lock is instantaneous and the omission is harmless today — but
   the plan should still call out the `CONCURRENTLY` build explicitly so the
   pattern is right by construction and isn't copy-pasted later onto a populated
   table where it WOULD cause a write-stall. Minor: state the build method.

3. [CONCERN] Architecture / Test plan — `status = 'expired'` appears in the
   lifecycle state machine and the `pending` scope is said to "exclude expired,"
   but nothing in the plan transitions a row INTO `expired`. Acceptance leans on
   `expires_at` being in the past (a computed check), so the `expired` status
   value may never actually be written — meaning the state diagram advertises a
   transition the implementation doesn't perform, and the "expired screen" path
   is really "pending row whose `expires_at` has passed." Clarify whether
   `expired` is a stored status (needs a sweep job / lazy write — neither is
   planned) or purely derived; if derived, drop it from the persisted status
   enum to avoid an unreachable state, and make the test assert which it is.

4. [CONCERN] Test plan — Acceptance criterion #5 in the issue covers an
   *already-registered* user accepting an invite (added to the new org without
   losing their existing orgs). The plan's accept flow handles "signed in vs not
   signed in," but the request-spec list only spells out the brand-new-signup
   path and the second-click-while-signed-in redirect; there's no explicit test
   for "an existing authenticated user of Org X accepts an invite to Org Y and
   ends up a member of BOTH." Add that case so the multi-org-membership
   guarantee from the issue is pinned, not assumed.

What the plan does well (credited, not padding):
- **Token hygiene is right.** Raw token emailed, only the SHA-256 digest
  persisted, lookups hash-then-match — a DB leak yields no usable link. The test
  plan pins it ("raw never stored"; mailer "does not contain the digest").
- **Tenancy is the load-bearing constraint and the plan treats it as such.**
  Invitations are read strictly through `current_organization.invitations`, and
  the accept route derives the org FROM the invitation, so there is no request
  parameter that could point acceptance at another tenant. Cross-tenant coverage
  is strong: owner-of-A-cannot-revoke-B → 404, and acceptance "ignores any org
  param and binds to the invitation's org" are both explicit specs — matching
  ExampleApp's 404-not-403 cardinal rule.
- **The idempotent second-click case IS covered.** "Second click on an accepted
  link while signed in → redirect to dashboard, no duplicate member" is an
  explicit request spec — exactly the boundary that's easy to forget.
- **Scope discipline is honest.** The Out-of-scope list (owner-role invites,
  bulk/CSV, seat enforcement under EX-231, reminder cadence) is concrete and
  matches the issue's deferrals; nothing required to close EX-218 is quietly
  punted, and the deferred seat-count work is tracked to a real follow-up.
- **Unknown-token → 404 with no "almost matched" hint** is specified at both the
  flow-diagram and acceptance-criteria level — no token-shape enumeration oracle.

Summary: This is a well-formed plan — the security-sensitive core (digest-at-rest
tokens, org-derived-from-invitation acceptance, owner-only authorization,
404-on-cross-tenant) is correct and well-tested, and the scope is honest. The
single drafting pass left four minor, addressable gaps, none load-bearing: name
rate-limiting as an explicit control on the accept + resend surfaces (it's only
implied), state the `CONCURRENTLY` index build, resolve whether `expired` is a
stored or derived status, and add the existing-user-joins-a-second-org accept
test. Commit as-is or fold these in first — the architect's call; they don't
block.
```
