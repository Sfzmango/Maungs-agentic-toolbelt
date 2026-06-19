> Example `/handoff` output for the fictional **ExampleApp** — a resume-from-cold brief for the in-flight EX-218 work.

# Handoff — EX-218 Team invitations (resume from cold)

EX-218 lets an organization **owner** invite a teammate by email at the `agent` or `viewer` role: the invitee gets a single-use, 7-day link, and accepting it mints a `Member` scoped to the inviting org. The architecture is settled, the migration and both controller surfaces are written, and the implementation is **open as PR #218 and in review** — `@pr-reviewer` returned **SHIP WITH FIXES** with a six-item punch list (two blocking). This handoff exists so a fresh agent can pick up at exactly that point: the design is not in question, the remaining work is the punch list. Do **not** re-plan the feature, re-derive the token scheme, or reopen scoped-out decisions; read the plan + the review, then drive the open PR to merge-ready.

**Entry point — run this first:**

```text
/orchestrator 218
```

`/orchestrator 218` re-enters the open PR at the review-resolution phase: `@developer` addresses the punch list as an amended commit on the existing branch, `@pr-reviewer` re-checks the blocking items, and `@resolution` resolves the fixed threads and flips the acceptance-criteria checkboxes — all under the normal commit/push gates. If you only want the code change without the full cycle, the punch list below is self-contained enough to hand to `@developer implement` directly.

---

## Read these first — in order

1. **`examples/sample-plan.md`** — the architect's plan (lands in the repo as `docs/plans/218_team-invitations.md`). The canonical design: `Invitation` model, the `pending → accepted/revoked/expired` lifecycle, digest-at-rest token handling, the single unauthenticated accept route, and the multi-tenancy contract. This is the source of truth for *what* the feature is.
2. **`examples/sample-issue.md`** — the product issue (EX-218) with the business-language acceptance criteria. Use it to confirm scope and the ship-conditions checklist.
3. **`examples/sample-pr-review.md`** — the `@pr-reviewer` SHIP-WITH-FIXES verdict on commit `b8e41d6`. This is the live punch list you are resuming against; its findings cite exact `file:line`.
4. The project's `CLAUDE.md` / `AGENTS.md` (whichever the target repo uses) for the cardinal rules — test gate, commit/push confirmation, no-attribution policy. Every fresh agent obeys these.

---

## Pre-flight checks

- **Confirm the PR is still open and at `b8e41d6`.** The review was written against implementation commit `b8e41d6` on branch `ex218-team-invitations`. If `git log` shows commits beyond `b8e41d6`, someone has already started addressing the punch list — diff against `b8e41d6` before assuming nothing has landed.
- **Confirm the plan commit is present.** The architect's plan landed as commit `7f3c9a2` (`docs/plans/218_team-invitations.md`) and is PR commit #1. If that file is missing, the branch is not what this handoff describes.
- **GitHub MCP (or `gh`) connectivity.** Resolving review threads and flipping acceptance checkboxes needs issue/PR access. With neither connected, `@resolution` degrades to the `gh` CLI; confirm `gh auth status` is green.
- **Branch / identifiers (fixed):** issue & PR **#218** · branch **`ex218-team-invitations`** · plan commit **`7f3c9a2`** · implementation commit **`b8e41d6`**.

---

## What's already done — do NOT redo

The architecture is decided and committed (`7f3c9a2`) and the first implementation pass is committed (`b8e41d6`) and in review. In place and reviewed-as-correct:

- **`db/migrate/<ts>_create_invitations.rb`** — the `invitations` table with the unique `token_digest` index and the partial-unique `(organization_id, email) WHERE status = 'pending'` index (at most one open invite per email per org). *(One open question against the migration — see punch-list item 6.)*
- **`app/models/invitation.rb`** — model, token generation, the lifecycle, and the digest-at-rest scheme. Reviewer **PASS**: `SecureRandom` generates the raw token, only the `Digest::SHA256` digest is persisted, lookups hash the incoming token to match the digest. Don't touch this — it's the precedent for future token features.
- **`app/controllers/invitation_acceptances_controller.rb`** — the public, token-scoped accept surface. Reviewer **PASS**: derives the org *from the invitation* (`@invitation.organization`), never from a request param; unknown token → **404** (not 401). The unauthenticated-route shape is correct.
- **`app/policies/member_policy.rb`** — create/revoke/resend gated to `owner`; the role param is constrained to `agent`/`viewer` so the form can't mint an `owner`. Reviewer **PASS**.
- **`app/mailers/invitation_mailer.rb`** + **`app/jobs/invitation_mailer_job.rb`** — async invite delivery; the mailer carries the raw token link, never the digest.
- **`app/frontend/pages/settings/{Members,InviteTeammateDialog}.tsx`** and **`app/frontend/pages/invitations/Accept.tsx`** — the owner-facing invite modal + pending list and the public accept screen.

The settled scope and the parts deliberately **out of scope** (owner-role invites, bulk/CSV, seat-count enforcement under EX-231, reminder cadence) are in the plan's *Out of scope* section. Don't expand into them.

---

## What's left — the SHIP-WITH-FIXES punch list

From `examples/sample-pr-review.md`, blocking first. Items 1–2 must land before re-requesting review; 3–6 can ride the same revision.

1. **FAIL — tenant-scoping funnel (`app/controllers/settings/invitations_controller.rb`).** The pending-invites list query uses a bare `Invitation.where(organization_id: current_organization.id, status: :pending)` (line ~24) and `revoke`/`resend` load with an unscoped `Invitation.find(params[:id])` (line ~41). Both bypass the load-bearing scoping funnel. Route everything through the association: the list becomes `current_organization.invitations.pending`, the finders become `current_organization.invitations.find(params[:id])` — so a foreign id raises `RecordNotFound` → **404** instead of acting on another org's invitation.
2. **FAIL — cross-tenant request spec (`spec/requests/settings/invitations_spec.rb`).** No spec covers the cross-tenant case the plan lists verbatim. Add one: sign in as Org A's owner, target an invitation belonging to Org B, assert **404** and that Org B's invitation is unchanged. This is the single most important missing test — without it, item 1 can regress unnoticed.
3. **CONCERN — rate-limit/debounce `resend`** (`app/controllers/settings/invitations_controller.rb`, line ~55). `resend` re-enqueues `InvitationMailerJob` with no throttle, so repeated clicks (or a stuck retry loop) flood the invitee's inbox. `create` is bounded by the partial-unique index; `resend` has no such gate. Cap resends per invitation per hour, or debounce on `updated_at`. *(The accept/resend public-adjacent surfaces are the abuse-sensitive ones — rate-limiting them is the intent here.)*
4. **CONCERN — idempotent second-click accept spec** (`spec/requests/invitation_acceptances_spec.rb`). Only the first-accept happy path is covered. Add: accept once, then hit the same link again as the now-signed-in member → expect a redirect to the dashboard and **no duplicate Member row** (assert `Member.count` unchanged).
5. **CONCERN — N+1 on the members list** (`app/frontend/pages/settings/Members.tsx`, line ~38 / its backing controller query). `invitation.invited_by.name` renders per row without preloading. Preload it: `current_organization.invitations.pending.includes(:invited_by)`.
6. **CONCERN — confirm the plain `organization_id` index** (`db/migrate/<ts>_create_invitations.rb`, ~line 18). The plan's Migrations section calls for a plain index on `organization_id` for the list query; the reviewer couldn't see it in the diff. The partial index won't serve non-pending list reads on Postgres. Confirm it's present; add it if not.

---

## Workflow walkthrough

Drive this through the project's standard conductor — the `/orchestrator` 13-step cycle (see the orchestrator skill in the toolbelt). For a resume like this you re-enter mid-cycle rather than from issue-fetch:

- **`@developer`** addresses items 1–6 as a single amended commit on `ex218-team-invitations`, writing the two new specs (items 2 and 4) and verifying any UI-visible change. Commit and push are each human-gated.
- **`@pr-reviewer`** re-reviews with fresh eyes, confirming the two FAILs are resolved (it never reads its own prior thread — that's deliberate).
- **`@resolution`** walks the prior review threads, replies + resolves the fixed ones citing the fixing commit, and flips the acceptance-criteria checkboxes; it halts on anything still unaddressed.
- The conductor reports the PR is **ready for you to merge** — it never merges for you.

---

## Gotchas — surface these during execution

- **Cross-tenant access returns 404, NOT 403.** This is the top bug class for the app and the entire thrust of punch-list items 1–2. A 403 leaks that the resource exists; a cross-tenant id must read as "not found." Every org-scoped read/write goes through `current_organization.<association>` — a bare `Invitation.where(...)` / `Invitation.find(...)` on a tenant-scoped table in a request path is the exact catastrophic pattern being fixed here. The fix is incomplete until a cross-tenant spec asserts the 404.
- **The accept route is the only unauthenticated surface.** `app/controllers/invitation_acceptances_controller.rb` is token-scoped, not session-scoped — it must keep deriving the org from `@invitation.organization` and never from a request param, and keep returning **404** (not 401) on an unknown token so it leaks no near-match signal. It's reviewed as PASS; don't regress it while touching the sibling settings controller. Item 3's rate-limit is specifically to harden this public-adjacent surface against resend abuse.
- **Idempotency at the accept boundary.** A second click on an already-accepted link must route the signed-in member to their dashboard and create **no** duplicate `Member`. The behavior exists; item 4 only adds the spec that pins it.
- **No attribution in commits or PR bodies.** No `Co-Authored-By` / AI-generated footers. Commit/push are each their own explicit confirmation gate; don't bundle them.

---

## When this handoff is wrong

- If `git log` on `ex218-team-invitations` shows commits **beyond `b8e41d6`**, the punch list is partly addressed already — re-read the latest review state before acting.
- If `docs/plans/218_team-invitations.md` is **absent**, the plan commit `7f3c9a2` isn't on this branch and you're not looking at the branch this handoff describes.
- If `app/controllers/settings/invitations_controller.rb` already routes through `current_organization.invitations` and a cross-tenant spec exists, items 1–2 are done — start at item 3.

**Next action:** `/orchestrator 218`
