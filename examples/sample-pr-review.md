> Example `@pr-reviewer` output for the fictional **ExampleApp** (PR #218). Frozen sample — the verdict + inline findings the agent emits.

# PR #218 — Team invitations (`@pr-reviewer`)

**PR:** #218 — Team invitations &nbsp;·&nbsp; **Branch:** `ex218-team-invitations` &nbsp;·&nbsp; **Reviewed commit:** `b8e41d6`
**Plan:** [`docs/plans/218_team-invitations.md`](./sample-plan.md) &nbsp;·&nbsp; **Issue:** EX-218

This is a fresh-eyes review — no prior review threads on this PR were read. ExampleApp is a multi-tenant
helpdesk (Organization → Member → Ticket → Billing); every record is org-scoped and **cross-tenant access
must return 404, not 403**. Per the rubric, multi-tenant isolation is the #1 thing to break here, since this PR
adds the feature's only unauthenticated route.

---

## Inline findings

Findings are line comments on the PR, grouped by severity. Each carries a rubric tag (PASS / CONCERN / FAIL).

### 🔴 FAIL — blocking

**`app/controllers/settings/invitations_controller.rb:24` · Multi-tenant safety (rubric #4)**

> The pending-invites list query reaches across the tenant boundary:
>
> ```ruby
> @invitations = Invitation.where(organization_id: current_organization.id, status: :pending)
> ```
>
> This *happens* to filter by the right org today, but it bypasses the project's load-bearing scoping funnel.
> The plan is explicit (Architecture §Multi-tenancy): "Invitations are created and listed strictly through
> `current_organization.invitations`, never `Invitation.find`." A bare `Invitation.where(...)` on a tenant-scoped
> table in a request path is exactly the catastrophic bug class CLAUDE.md flags — the next refactor that drops or
> mistypes the `organization_id:` predicate silently lists every org's invitations. Funnel it through the
> association so the scope can't be forgotten:
>
> ```ruby
> @invitations = current_organization.invitations.pending
> ```
>
> Same fix applies to `destroy` (revoke) and `resend` below — see the next finding.

**`app/controllers/settings/invitations_controller.rb:41` · Multi-tenant safety (rubric #4)**

> `revoke`/`resend` load the target invitation with an unscoped finder:
>
> ```ruby
> @invitation = Invitation.find(params[:id])
> ```
>
> An owner of Org A can revoke or resend Org B's invitation by guessing/iterating the id — the id is sequential and
> the lookup never checks tenancy. This must 404 on a cross-tenant id, not act on it. Route it through the scope so
> a foreign id raises `RecordNotFound` (→ 404), which is also what the plan's acceptance criterion requires
> ("an owner of one organization gets 404 trying to act on another org's invitation"):
>
> ```ruby
> @invitation = current_organization.invitations.find(params[:id])
> ```

**`spec/requests/settings/invitations_spec.rb` · Tests (rubric #5)**

> There is no cross-tenant request spec for `revoke`/`resend`. The plan's Test plan lists it verbatim
> ("**cross-tenant:** owner of Org A cannot revoke/resend an invite belonging to Org B → 404") and the rubric
> treats an acceptance criterion with no test as a FAIL. Add a spec that signs in as Org A's owner, targets an
> invitation belonging to Org B, and asserts **404** (and that Org B's invitation is unchanged). Without it the
> two findings above could regress unnoticed. This is the single most important missing test in the PR.

### 🟠 CONCERN — fix before merge

**`app/controllers/settings/invitations_controller.rb:55` · Correctness / Blast radius (rubric #2, #6)**

> `resend` re-enqueues `InvitationMailerJob` with no rate limit. The accept link is reusable until it expires, so a
> caller (or a stuck retry loop in the UI) can hammer **Resend** and turn ExampleApp into an email relay against the
> invitee's inbox — a deliverability and abuse-reporting risk. `create` is naturally bounded by the partial-unique
> "one pending invite per email per org" index, but `resend` has no such gate. Add a throttle (e.g. cap resends per
> invitation per hour, or debounce on `updated_at`) before this ships.

**`spec/requests/invitation_acceptances_spec.rb` · Tests (rubric #5)**

> The accept flow's idempotency is in the plan ("Acceptance is idempotent at the boundary — a second click on an
> already-accepted link routes the now-authenticated member straight to their dashboard") but there's no spec for
> the **second-click-while-signed-in** path. Only the first-accept happy path is covered. Add: accept once, then hit
> the same link again as the now-signed-in member → expect a redirect to the dashboard and **no duplicate Member
> row** (assert `Member.count` unchanged). The duplicate-member guard is precisely the kind of thing that rots
> without a test pinning it.

**`app/frontend/pages/settings/Members.tsx:38` · Correctness / Blast radius (rubric #2, #6)**

> The members list renders `invitation.invited_by.name` per row, and `invited_by` isn't preloaded — this is an N+1
> against `members` as the pending list grows (one query per invite to resolve the inviter). It won't show on a
> two-row dev org but will on a real customer's. Preload it on the controller query
> (`current_organization.invitations.pending.includes(:invited_by)`) so the list stays one query.

**`db/migrate/<ts>_create_invitations.rb:18` · Correctness (rubric #2)**

> The `revoke`/`resend`/list queries filter on `status` and `organization_id`, and the lookups will hit
> `token_digest`. The migration adds the unique index on `token_digest` and the partial-unique
> `(organization_id, email) WHERE status = 'pending'` (good — matches the plan), but there's no plain index backing
> the **list** query's `organization_id` filter that the plan's Migrations section calls for ("plain index on
> `organization_id` for the list query"). On Postgres the partial index won't serve the non-pending list reads.
> Confirm the plain `organization_id` index is present — it's named in the plan but I don't see it in the diff.

### 🟢 PASS / positive notes

**`app/models/invitation.rb:14` · Security (rubric #3) — PASS**

> Token handling is exactly right and worth calling out: `SecureRandom` generates the raw token, only the
> `Digest::SHA256` **digest** is persisted, and lookups hash the incoming token to match on the digest column. The
> raw value is never written to the database, and `invitation_mailer_spec.rb` asserts the email carries the raw
> link while the digest stays out of it. A DB leak yields no usable invite link. This matches the plan's
> "email the raw value, persist only the digest" convention precisely — good, and a clean precedent for future
> token features.

**`app/controllers/invitation_acceptances_controller.rb:21` · Multi-tenant safety (rubric #4) — PASS**

> The accept route derives the organization *from the invitation* (`@invitation.organization`) and never reads an
> org id from a request param. That's the correct shape for the one unauthenticated surface in the feature — there's
> no parameter an attacker could supply to point acceptance at another tenant. The unknown-token path returns 404
> (not 401), so it doesn't leak whether a token "almost" matched. Both behave as the plan specifies.

**`app/policies/member_policy.rb:9` · Security (rubric #3) — PASS**

> `create`/`revoke`/`resend` are gated to `owner` only, and the invite role param is constrained to
> `agent`/`viewer` so the form can't mint an `owner` by tampering with the role field. Authorization matches the
> plan's owner-only intent.

---

## Verdict — SHIP WITH FIXES

The feature is well-architected and the security-sensitive parts that are easy to get wrong — digest-at-rest token
handling and deriving the accept org from the invitation rather than a request param — are done correctly. But the
list/revoke/resend controller actions bypass the tenant-scoping funnel the project treats as a cardinal rule, and
the cross-tenant-404 spec that would catch that is missing. Those are blocking; the rest are pre-merge tidy-ups.

**Punch list (blocking first):**

1. **FAIL** — `settings/invitations_controller.rb`: route the list query and the `revoke`/`resend` finders through
   `current_organization.invitations` (`.pending` / `.find`) instead of `Invitation.where` / `Invitation.find`, so
   cross-tenant access 404s.
2. **FAIL** — add the cross-tenant request spec (Org A owner acting on Org B's invitation → 404, Org B's row
   unchanged).
3. **CONCERN** — rate-limit / debounce `resend` to prevent inbox flooding.
4. **CONCERN** — add the idempotent second-click accept spec (no duplicate Member).
5. **CONCERN** — preload `invited_by` to kill the N+1 on the members list.
6. **CONCERN** — confirm the plain `organization_id` index from the plan is in the migration.

Re-request review once 1–2 land; 3–6 can ride the same revision.
