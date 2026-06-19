> Example `@security-reviewer` output for the fictional **ExampleApp** (PR #218). Frozen sample — compliance-mapped findings + verdict the agent emits.

This is a frozen, representative example of the cold security + compliance gate
`@security-reviewer` runs against a pull request. The live agent posts the
line-level findings as inline GitHub review comments and the body below as the
review summary; here they are collected into one document so the format is
readable end to end. The subject is **ExampleApp** — a fictional multi-tenant
B2B SaaS helpdesk (Organizations → Members → Tickets → Billing; every record
org-scoped, cross-tenant access must 404) — reviewing **PR #218**, the
"Team invitations" feature planned in [`sample-plan.md`](./sample-plan.md) and
scoped in [`sample-issue.md`](./sample-issue.md).

- **PR:** #218 — Team invitations
- **Branch:** `ex218-team-invitations`
- **Implementation commit:** `b8e41d6`
- **Plan reviewed:** `docs/plans/218_team-invitations.md`

---

## Inline findings

Each finding is what the agent posts as a single inline PR review comment on the
named `file:line`: a severity tag, the framework mapping, and a one-line
what / control / fix body. Cold and terse — no threat-model walkthroughs (that is
`@security-mentor`'s job).

### F1 — `app/controllers/invitation_acceptances_controller.rb:18`

- **Severity:** FAIL
- **Mapping:** OWASP A04 (brute-force) · A07 · SOC 2 CC7.2 · CWE-307 · NIST 800-63B §5.2.2
- **Finding:** The public `accept` route (`show`/`update`) is the feature's only
  unauthenticated surface and has **no rate limiting**. A token is a 256-bit
  SecureRandom value, so online guessing is not a realistic break — but an
  un-throttled unauthenticated endpoint is still an abuse and resource-exhaustion
  surface, and NIST 800-63B §5.2.2 expects throttling on a verifier that accepts
  a secret. **Fix:** add a per-IP `rate_limit` (e.g. 10/min) on both `show` and
  `update`, backed by a real cache store (not the null store), with a cache reset
  in the request specs that exercise it.

### F2 — `app/controllers/settings/invitations_controller.rb:34`

- **Severity:** FAIL
- **Mapping:** OWASP A04 · SOC 2 CC7.2 · CWE-307
- **Finding:** `resend` re-enqueues the invitation mailer with no throttle. It is
  owner-authenticated (good — not a public surface like F1), but an owner can
  loop **Resend** to drive outbound mail at the invitee's address — an
  email-bombing / cost-abuse vector against a third party who has not consented.
  **Fix:** rate-limit `resend` per invitation (e.g. one send per N minutes) and
  cap the lifetime resend count; return a friendly "try again shortly" rather
  than silently re-sending.

### F3 — `app/controllers/settings/invitations_controller.rb:21`

- **Severity:** CONCERN
- **Mapping:** OWASP A01 · SOC 2 CC6.1 · PII (email)
- **Finding:** `create` returns a distinct inline error ("That person is already
  on your team") when the invited email already maps to a member, versus the
  success path when it does not. An authenticated owner can therefore use the
  invite form as a **membership-enumeration oracle** for arbitrary email
  addresses scoped to their own org. Lower severity than the unauthenticated
  enumeration defenses (the actor is already an authenticated owner of *this*
  org), but it still discloses whether a given email belongs to the org. **Fix:**
  keep the inline UX but treat it as accepted product risk in the plan, or
  collapse the "already a member" and "invite sent" responses to a uniform
  confirmation if email-membership privacy is in scope.

### F4 — `app/models/invitation.rb:27`

- **Severity:** CONCERN
- **Mapping:** SOC 2 CC6.1 · OWASP A01 · CWE-639 · NIST 800-63B §4.1.3
- **Finding:** Expiry is enforced in the model `pending` scope / `expired?`
  predicate (read-side), and acceptance checks `pending? && !expired?` — correct.
  But there is **no background sweep** flipping stale `pending` rows to `expired`,
  so an un-accepted invitation row sits `pending` in the database past its
  `expires_at` indefinitely. The accept path is safe (it re-checks expiry at use),
  but the `(organization_id, email) WHERE status = 'pending'` partial-unique
  index then keeps blocking a fresh invite to that email until someone revokes the
  stale row. **Fix:** add a periodic job (or accept-time lazy transition) that
  marks elapsed `pending` invitations `expired`, so the lifecycle state in the DB
  matches the enforced semantics and the partial-unique slot frees up.

### F5 — `app/mailers/invitation_mailer.rb:12` / `app/views/invitation_mailer/invite.html.erb`

- **Severity:** CONCERN
- **Mapping:** SOC 2 CC4.1 · CC7.3 · OWASP A09 · NIST 800-63B §5.1.1.2 · PII (email)
- **Finding:** The invite email by design carries the **raw** token in the accept
  URL — that is correct and the only place the raw token may appear. Two adjacent
  checks need pinning: (a) confirm the param-filter / log-scrubbing list redacts
  `token` so the raw value is never written to application or job logs on enqueue
  / delivery, and (b) confirm the invitee **email address** (PII) is not emitted
  into job logs at `info` level by the mailer job. The static sweep did not flag a
  log line, but neither is there a `filter_parameter_logging` entry for `token` in
  the diff. **Fix:** add `token` to the filtered-parameters list and assert in the
  mailer spec that the rendered body contains the raw token link while the
  persisted row and the logs do not.

### F6 — `app/models/invitation.rb:9` *(SATISFIED control — recorded as evidence)*

- **Severity:** PASS
- **Mapping:** SOC 2 CC6.7 · CC6.1 · OWASP A02 · NIST 800-63B §5.1.1.2 · CWE-256
- **Finding:** **Digest-at-rest is implemented correctly and is the load-bearing
  secret control for this feature.** The token is generated with
  `SecureRandom.urlsafe_base64(32)` (≈256 bits of entropy — well past the
  NIST 800-63B threshold for a single-use, time-limited verifier), the **raw**
  value is emailed and never persisted, and only its **SHA-256 digest** is stored
  in `token_digest` (unique index). Lookups hash the inbound token and match on
  the digest, so a database disclosure yields no usable invite link. No fix —
  recorded as positive audit evidence for CC6.7 (data at rest).

### F7 — `app/controllers/invitation_acceptances_controller.rb:24` *(SATISFIED control — recorded as evidence)*

- **Severity:** PASS
- **Mapping:** SOC 2 CC6.1 · OWASP A01 · CWE-639 · CWE-203
- **Finding:** **Multi-tenant isolation is enforced correctly on the one
  unauthenticated path.** Acceptance derives the organization **from the
  invitation row** (`invitation.organization`), never from a request param, so an
  accepted token can only ever mint a `Member` in the issuing org — there is no
  parameter an attacker could set to redirect acceptance at another tenant. The
  authenticated `create` / `destroy` / `resend` actions scope strictly through
  `current_organization.invitations`, and the request specs assert an owner of
  Org A gets **404** acting on an Org B invitation. This is the highest-value
  control in the diff; it passes. No fix — recorded as positive evidence for
  CC6.1 (tenant isolation).

### F8 — `app/controllers/invitation_acceptances_controller.rb:14` *(SATISFIED control — recorded as evidence)*

- **Severity:** PASS
- **Mapping:** SOC 2 CC6.1 · OWASP A01 · CWE-203 (timing/oracle) · NIST 800-63B §5.2.2
- **Finding:** **Enumeration defense on the accept route is correct.** An unknown
  or non-matching token returns a uniform **404** with no signal that a token
  "almost" matched, and the lookup hashes-then-matches on the digest (constant
  shape regardless of input), so the response cannot be used as a
  token-existence oracle. Returning 404 rather than 403 is the right call — a 403
  would leak that *some* resource exists at that token. No fix — recorded as
  positive evidence for CC6.1. (Paired with F3: the unauthenticated surface does
  not leak; the authenticated invite form does, at lower severity.)

---

## Review body

```
## security-reviewer verdict: SHIP WITH FIXES

Stack detected: Ruby on Rails + PostgreSQL + React · Data sensitivity: PII (member + invitee email)

### Rubric
- AuthN — PASS — no password/credential change; token is 256-bit SecureRandom, single-use, 7-day expiry (NIST 800-63B-aligned).
- AuthZ — PASS — create/revoke/resend gated owner-only via MemberPolicy; non-owner → 403 is asserted in the request specs.
- Tenant isolation — PASS — accept derives org from the invitation row, never a param; authed actions scope through current_organization.invitations; cross-tenant → 404 tested (F7).
- Input validation + injection — PASS — digest lookup is parameterized; role allowlist excludes owner; status/token_digest excluded from strong params.
- CSRF / session / cookies — PASS — public accept route is GET-show + POST-update under the framework CSRF default; no new cookie, no CSRF skip introduced.
- Encryption + key management — PASS — digest-at-rest (SHA-256), raw token emailed only, never persisted (F6).
- Logging + audit evidence — CONCERN — token not confirmed in the param-filter list; invitee email (PII) log hygiene unverified on the mailer job (F5); no audit row recorded on accept/revoke (CC7.2/CC7.3 thin — flag for the M3 audit-log work, not a blocker here).
- Supply chain — PASS — no new dependencies; SecureRandom + Digest::SHA256 are stdlib; lockfile clean.
- Configuration + secrets — PASS — no new env var, no deploy-config or buildpack reorder, no secret in diff.
- Rate limiting — FAIL — public accept/show + update have no per-IP throttle (F1); authenticated resend has no per-invitation throttle (F2). New unauthenticated surface MUST be rate-limited.

### Static analysis sweep
- SAST (Brakeman): no new warnings vs origin/main.
- Dependency audit (bundle-audit): clean — no deps added or bumped.
- Lockfile drift: clean — Gemfile.lock unchanged.
- Secret-pattern grep: clean — no key/token literal in the diff (raw token is generated at runtime, never committed).
- PII log grep: clean on the obvious patterns; F5 flags an unconfirmed gap (no `token` in filter_parameters, mailer-job email logging unverified), not a confirmed leak.

### Tooling gaps
- None. Brakeman + bundle-audit ran against the branch; the audit-log rubric line (CC7.2/CC7.3) is evaluated as "deferred-on-purpose" per the plan's M3 audit-log scoping, not a missing control in this PR.

### Punch list (ordered by severity)
1. [FAIL] app/controllers/invitation_acceptances_controller.rb:18 — public accept show/update has no rate limit — add per-IP rate_limit (≈10/min) on a real cache store + reset in specs (OWASP A04 / CC7.2 / NIST 800-63B §5.2.2).
2. [FAIL] app/controllers/settings/invitations_controller.rb:34 — resend is un-throttled, enabling email-bombing of the invitee — rate-limit per invitation + cap lifetime resends (OWASP A04 / CC7.2).
3. [CONCERN] app/controllers/settings/invitations_controller.rb:21 — distinct "already a member" response is a membership-enumeration oracle for the authenticated owner — accept-as-product-risk in the plan or uniform the response (OWASP A01 / CC6.1 / PII).
4. [CONCERN] app/models/invitation.rb:27 — no sweep transitions stale pending → expired, so the partial-unique slot stays blocked — add a periodic/lazy expiry transition (CC6.1 / NIST 800-63B §4.1.3).
5. [CONCERN] app/mailers/invitation_mailer.rb:12 — `token` not in filter_parameters; invitee email (PII) log hygiene unverified on the mailer job — filter `token`, assert raw-token-in-body-only in the mailer spec (CC4.1 / OWASP A09 / PII).

### Recorded as satisfied (positive audit evidence — no action)
- F6 — digest-at-rest: raw token emailed, only SHA-256 digest persisted (CC6.7).
- F7 — tenant isolation: acceptance binds to the invitation's org, never a param; cross-tenant → 404 tested (CC6.1).
- F8 — enumeration defense: unknown token → uniform 404, no near-match signal, no token-existence oracle (CC6.1 / CWE-203).
```

---

## Verdict

**SHIP WITH FIXES.**

The security architecture of EX-218 is sound: the highest-value controls — the
digest-at-rest token (F6), multi-tenant isolation that binds acceptance to the
invitation's own org (F7), and the 404 enumeration defense on the only
unauthenticated route (F8) — are all implemented correctly and are recorded as
positive audit evidence. No compliance blocker is present and no secret leaked.

What holds back an outright SHIP is the **missing rate limiting** on the new
public accept endpoint (F1) and the authenticated resend endpoint (F2) — a new
unauthenticated write surface without a per-IP throttle is a standing rubric
FAIL regardless of how clean the surrounding code is — plus a small set of
hardening items: the membership-enumeration response (F3), the absent
stale-`pending` → `expired` sweep (F4), and the token / invitee-email log-hygiene
confirmation (F5). Land the two FAILs and the three CONCERNs and this ships.
