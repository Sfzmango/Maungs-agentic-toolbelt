# Sample release notes — `/release-notes` output

> Example `/release-notes` output for the fictional **ExampleApp**. Frozen sample — text-only output the skill emits (it never tags, commits, or pushes).

---

**Range:** since last tag `v1.4.0` → `HEAD` (auto-detected — no deploy marker found, so the most recent SemVer tag wins). Resolved `v1.4.0..HEAD`.

**Sources:** git log over the range + the merged PRs in it (GitHub MCP available), classified by conventional-commit prefix + PR labels + path heuristics.

---

## Summary

Adds owner-driven team invitations (invite a teammate by email at the `agent` or `viewer` role), fixes a pending-invitations list query that leaked across organizations, and documents the invite-by-email flow. One DB migration (`invitations`) plus a `members.joined_via` backfill; one new unauthenticated route and one new outbound email.

## ✨ Features

- Organization owners can invite a teammate by email and assign them an `agent` or `viewer` role; the invitee gets a single-use, 7-day link that creates their member record in the inviting org on accept (#218) [members]

## 🐛 Fixes

- The pending-invitations list no longer surfaces invites from other organizations — the list query was missing the org scope, so an owner could see another tenant's pending invites; it is now scoped through `current_organization` (#219) [members]

## 📝 Docs

- Documents the invite-by-email flow end to end — how an owner sends an invite, the single-use/expiring link, and the public accept screen — in the Members section of the architecture docs (#220) [docs]

## SemVer bump recommendation

Recommend **minor**: `1.4.0` → `1.5.0`.

Reasoning: the release adds a new user-facing capability (team invitations, #218) with no breaking change to any existing API, route, or behavior — a new feature with backward-compatible changes is a MINOR bump under SemVer. The fix (#219) and the docs change (#220) would each only justify a PATCH on their own; the feature is what lifts the recommendation to MINOR.

> ### 🚀 Deploy checklist
>
> This release ships a schema migration, a data backfill, a new unauthenticated route, and a new outbound email — review before promoting.
>
> - [ ] **Run the `invitations` migration** — creates the `invitations` table (`token_digest`, `status`, `expires_at`, `invited_by_id`, the unique index on `token_digest`, and the partial-unique index on `(organization_id, email) WHERE status = 'pending'`). The accept-link lookup matches on the SHA-256 `token_digest`; the raw token is never stored. (#218)
> - [ ] **Backfill `members.joined_via`** — sets `joined_via` on existing member rows (existing members → the pre-invitation default; new members created through acceptance are stamped `invitation`). Confirm the backfill completed before the new members list relies on the column. (#218)
> - [ ] **New unauthenticated route** — `/invitations/accept` is the feature's only route reachable without a session (it is token-scoped, not session-scoped, because the invitee has no account yet). Confirm it is exposed at the edge and that create/list/revoke/resend remain owner-only and authenticated. (#218)
> - [ ] **New outbound invitation email** — a new `InvitationMailer` sends the accept link via the existing mail provider. Confirm mail credentials/sender are configured in the target environment before promoting, or invites will queue as `pending` with no email delivered (Resend is the recovery path). (#218)
> - [ ] **Watch for** — cross-tenant access on the members/invitations surfaces (a miss must 404, not 403) and acceptance binding to the invitation's own org rather than any request param, immediately after deploy.

---

_Output is text only. This skill never tags, commits, pushes, or posts — turning these notes into a git tag, a CHANGELOG entry, a GitHub Release, or a deployment comment is a separate, human- or CI-gated step._
