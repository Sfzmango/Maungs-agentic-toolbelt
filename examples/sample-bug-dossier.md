# Sample bug dossier — cross-tenant ticket read

> Example output for the `/bug-catcher` workflow, run against **ExampleApp** — a multi-tenant B2B SaaS helpdesk
> (Organizations → Members [owner/agent/viewer] → Tickets [comments, statuses] → Billing [plans, invoices]).
> Stack: Ruby on Rails + PostgreSQL + React. Cardinal rule under test: **every record is scoped to an
> organization; cross-tenant access must 404.**
>
> This file shows the full three-phase shape: the `@bug-catcher-rick` **dossier**, then the
> `@bug-catcher-adversary` **verdict** that independently tries to refute it. It is a teaching example —
> the file:line references point at the fictional ExampleApp source, not at this repo.

---

## Invocation

> `/bug-catcher an agent on org "Northwind" opened ticket #4821 and saw a ticket that belongs to org "Contoso"`

---

## Phase 1 — `@bug-catcher-rick` dossier

```
SYMPTOM
  A signed-in member of org "Northwind" (org_id=12) navigates to /tickets/4821 and is shown a
  ticket whose subject, requester email, and full comment thread belong to org "Contoso" (org_id=87).
  No error is raised; the page renders 200 with another tenant's data. Support escalated it after a
  Northwind agent reported "a ticket I don't recognize, with a customer we don't have."

REPRODUCTION
  Not environment-specific — reproduces in dev, CI, and prod. Deterministic.

  Console repro (Rails):
    contoso = Organization.find_by!(name: "Contoso")
    northwind = Organization.find_by!(name: "Northwind")
    foreign = FactoryBot.create(:ticket, organization: contoso)         # belongs to Contoso
    agent   = FactoryBot.create(:member, organization: northwind, role: :agent)

    # simulate the controller lookup the request actually performs:
    Ticket.find(foreign.id)            # => returns the Contoso ticket. No scoping. <-- bug
    northwind.tickets.find(foreign.id) # => ActiveRecord::RecordNotFound (what SHOULD happen)

  Request repro:
    Sign in as the Northwind agent, GET /tickets/<any Contoso ticket id> -> HTTP 200 with Contoso data.
    Expected: HTTP 404.

ROOT CAUSE — CONFIDENT
  TicketsController#show looks up the ticket with an UNSCOPED, global primary-key query
  (`Ticket.find(params[:id])`) instead of scoping through the current organization
  (`current_organization.tickets.find(params[:id])`). Because the lookup is not tenant-bounded,
  any authenticated member can read ANY ticket in the database by guessing/iterating its id.

  This is a direct violation of ExampleApp's documented cardinal rule
  (CLAUDE.md › "Tenant isolation": *"Never load a tenant-owned record by bare global lookup. Always
  scope through `current_organization` (or an association already scoped to it). Cross-tenant access
  MUST 404, never 403 — a 403 leaks existence."*). The authorization layer never gets a chance to
  help here: the Pundit policy authorizes the record AFTER it has already been loaded cross-tenant,
  and the policy only checks role, not ownership (see evidence chain link 4).

EVIDENCE CHAIN
  1. app/controllers/tickets_controller.rb:31
       def show
         @ticket = Ticket.find(params[:id])        # <-- global, unscoped lookup. Root cause.
         authorize @ticket
       end
     `Ticket.find` issues `SELECT * FROM tickets WHERE id = $1 LIMIT 1` with no `organization_id`
     predicate. Confirmed by tailing the query log during the request repro:
       Ticket Load  SELECT "tickets".* FROM "tickets" WHERE "tickets"."id" = $1 LIMIT $2  [["id", 4821]]
     No `organization_id = 12` in the WHERE clause.

  2. app/controllers/application_controller.rb:18
       def current_organization
         @current_organization ||= Organization.find(session[:organization_id])
       end
     A correctly-scoped `current_organization.tickets` association IS available here and is used
     correctly elsewhere (see link 5). #show simply doesn't use it.

  3. app/models/ticket.rb:4
       belongs_to :organization
       # NOTE: no default_scope, and the app deliberately avoids default_scope (CLAUDE.md forbids it
       # because it silently leaks into joins/associations). So scoping MUST be explicit at the call site.
     There is no model-level safety net. The only thing standing between a member and a foreign
     ticket is the call-site scope — which #show omits.

  4. app/policies/ticket_policy.rb:9
       def show?
         user.agent? || user.owner?         # checks ROLE only, never record.organization_id == user.organization_id
       end
     `authorize @ticket` passes because the Northwind agent IS an agent. The policy never compares
     the ticket's org to the member's org, so it cannot catch the cross-tenant load. Authorization
     here is a role gate, not a tenancy gate — and it runs too late regardless (the record is already
     loaded). This is why the leak renders 200, not 403/404.

  5. app/controllers/tickets_controller.rb:12  (the CORRECT pattern, for contrast)
       def index
         @tickets = current_organization.tickets.order(created_at: :desc)   # properly scoped
       end
     #index scopes through the association and is not vulnerable. The bug is #show (and #edit/#update,
     see FIX DIRECTION) diverging from this established pattern — strong evidence this is a localized
     omission, not an intended design.

PROPOSED SEV — SEV1
  Cross-tenant data leak: an authenticated low-privilege member (role: agent, even viewer — see open
  question) of ANY org can read ANY other org's ticket, including requester PII and the full comment
  thread, by iterating sequential integer ids. Per the rubric, a cross-tenant/security leak is ALWAYS
  SEV1. Confidentiality breach across the entire tenant base; no exploit sophistication required.

FIX DIRECTION
  Smallest change that resolves the CAUSE (scope the lookup), not the symptom:

    def show
      @ticket = current_organization.tickets.find(params[:id])   # 404s on cross-tenant id
      authorize @ticket
    end

  `find` on the scoped association raises ActiveRecord::RecordNotFound for a foreign id, which Rails
  renders as 404 — satisfying the "cross-tenant MUST 404" rule. `authorize` stays as defense-in-depth.

  Sibling cases of the SAME bug class to fix in the same change (grepped, all use bare `Ticket.find`):
    - app/controllers/tickets_controller.rb:44   #edit    -> Ticket.find(params[:id])
    - app/controllers/tickets_controller.rb:51   #update  -> Ticket.find(params[:id])
    - app/controllers/comments_controller.rb:8   #create  -> Ticket.find(params[:ticket_id])  (posts a
                                                            comment onto a foreign ticket — write leak)
  Recommend a shared `set_ticket` before_action using the scoped association so the pattern can't
  re-diverge. Consider hardening ticket_policy.rb:9 to also assert `record.organization_id ==
  user.organization_id` as belt-and-suspenders, but the load-site scope is the real fix.

REGRESSION TEST
  A request/controller spec asserting cross-tenant 404 — the test the suite is currently missing:

    # spec/requests/tickets_spec.rb
    it "404s when a member requests another org's ticket" do
      foreign = create(:ticket, organization: create(:organization))   # different org
      sign_in create(:member, organization: @org, role: :agent)        # @org != foreign's org
      get "/tickets/#{foreign.id}"
      expect(response).to have_http_status(:not_found)
    end

  Add the symmetric cases for #edit, #update, and comments#create. The existing suite only tests the
  happy path (own-org ticket) — that is itself part of the bug: there was no negative cross-tenant
  test gating the controller.

BLAST RADIUS
  - Tenancy/scoping: the core of the fix; changes how four actions load tickets. Low risk — same-org
    requests are unaffected (the association returns the identical record for own-org ids).
  - Authorization: unchanged at runtime, but the fix removes reliance on Pundit for tenancy (which it
    never enforced anyway). Optional policy hardening is additive.
  - Migrations / live data: none. Pure controller-layer change. No schema touch.
  - Test/quality gate: adds the missing negative specs; CI must go red without the fix and green with it.

PROD MITIGATION
  Live leak, so a "stop the bleeding" step distinct from the durable fix:
    - Immediately: ship the scoped-lookup one-liner for #show as a hotfix (smallest blast radius),
      then follow with the sibling-case fixes + before_action refactor.
    - If a hotfix deploy is not immediate: a temporary before_action that rejects when
      `Ticket.find(params[:id]).organization_id != current_organization.id` (returning 404) caps the
      leak, but it still performs a global load — use only as a stopgap, not the fix.
    - Audit: query the request logs / Ticket access for cross-org reads (member.org_id != ticket.org_id)
      to scope the incident-response / breach-notification question. Flag to security; PII was exposed.

OPEN QUESTIONS
  - Does role `viewer` also reach #show? ticket_policy.rb:9 only allows agent/owner, so a viewer is
    likely blocked by the role gate — but that gate is incidental, not a tenancy control. Confirm the
    viewer route to be sure the blast radius isn't even wider. Evidence that would close it: a request
    spec signing in as a viewer of org A against an org-B ticket id.
  - Are ticket ids sequential integers (trivially enumerable) or UUIDs? schema.rb shows `bigint`
    primary keys -> sequential -> trivial enumeration -> raises exploitability, supports SEV1.
```

---

## Phase 2 — `@bug-catcher-adversary` verdict

```
VERDICT: CONFIRMED

Bottom line: I tried to break this diagnosis and could not. I re-derived everything from the code
without leaning on the dossier's reasoning: I read tickets_controller.rb cold, ran the console repro
myself, watched the SQL, and independently reached the same root cause — #show loads the ticket with
a bare global `Ticket.find`, so there is no `organization_id` predicate and any authenticated member
reads any org's ticket. The two plausible competing theories (it's an authorization-policy bug; it's
a session/current_organization bug) both die against the code: the policy and the session helper are
each correct in isolation and are simply bypassed by an unscoped load. SEV1 is right and arguably
under-stated given trivial id enumeration. I confirm both the root cause and the fix direction.

RUBRIC
1. Symptom vs cause — PASS — The symptom (200 with foreign data) is fully explained by the unscoped
   load at tickets_controller.rb:31; nothing upstream is needed. I checked one level up: session[:organization_id]
   and current_organization (application_controller.rb:18) are correct — the *correct* org is in the
   session, the lookup just ignores it. So the cause is the call-site omission, not a session mixup.

2. Evidence chain — PASS — Every link verified against the source as written. I confirmed the SQL has
   no organization_id clause by tailing the query log during my own repro (not the dossier's): the
   emitted statement was `WHERE "tickets"."id" = $1 LIMIT $2` with no tenant predicate. ticket.rb:4
   has no default_scope (consistent with CLAUDE.md forbidding it). ticket_policy.rb:9 checks role only.
   index (line 12) really does scope correctly — the contrast link is accurate. No asserted-but-unshown
   link.

3. Reproduction — PASS — Reproduces deterministically, not env-specific. I ran the console repro:
   `Ticket.find(foreign.id)` returns the foreign org's ticket; `northwind.tickets.find(foreign.id)`
   raises RecordNotFound. Confirmed the request path returns 200 with foreign data, expected 404.

4. Alternatives — PASS — I generated two competing causes and killed both:
   (a) "It's an authorization bug — harden ticket_policy.rb." Killed: even a perfectly tenancy-aware
       policy runs AFTER the cross-tenant record is already loaded; and the leak would still render
       (policy can only 403, and the rule demands 404). Fixing only the policy masks the load. The
       load-site scope is the true fix; policy hardening is at best defense-in-depth. Survives as a
       *secondary* recommendation, not the root cause — which is exactly how the dossier frames it.
   (b) "current_organization / session is wrong — wrong org loaded." Killed: application_controller.rb:18
       resolves the correct org from session, and index uses it correctly. The bug is isolated to the
       actions that bypass it. Neither alternative outlived contact with the code.

5. Fix resolves? — PASS — `current_organization.tickets.find(params[:id])` adds the organization_id
   predicate, so a foreign id raises RecordNotFound -> 404, satisfying the cardinal rule. I confirmed
   the same-org happy path is unaffected (association returns the identical record for own-org ids).
   Crucially, the dossier does NOT stop at #show: it grepped and named the sibling cases (#edit,
   #update, comments#create). I independently grepped `Ticket.find(` / `Ticket\.find` and found the
   same four call sites and no others — so the fix does not miss a sibling case. comments#create is
   the nastiest (a cross-tenant *write*), correctly flagged.

6. Fix blast radius — PASS — Controller-layer only; no migration, no schema, no live-data risk. SEV
   sanity: SEV1 is correct and if anything conservative — schema.rb confirms bigint sequential PKs, so
   ids are trivially enumerable, making mass exfiltration a simple loop. The one thing I'd insist on
   beyond the dossier's enumeration: the regression test must be wired so CI is RED without the fix
   (I'd verify the negative spec actually fails on the current code before the fix lands, so the gate
   is proven, not assumed). The dossier says this; treat it as a hard gate, not a nicety.

IF NOT CONFIRMED — n/a. One non-blocking nudge for the fix plan (does not change the verdict): close
the dossier's own open question by adding the viewer-role negative spec too, so the regression net
covers every role, not just agent. And prefer the shared `set_ticket` before_action over four
hand-edited call sites, so the scoped-lookup pattern cannot silently re-diverge later.
```

---

## How to read this example

- **Symptom vs root cause** are kept distinct: the symptom is "200 with another org's data"; the root
  cause is the *unscoped load* at `tickets_controller.rb:31`, one level deeper than the visible failure.
- **The evidence chain is a chain**, not a list — each `file:line` link is verified against the code as
  written (link 1 even shows the emitted SQL), and link 5 deliberately contrasts the *correct* pattern.
- **SEV1 is forced by the rubric**: any cross-tenant / security leak is automatically SEV1.
- **The fix targets the cause** (scope the query) and names **sibling cases** of the same bug class, so
  the leak is closed everywhere — not just on the one reported action.
- **The adversary is genuinely independent**: it re-ran the repro itself, watched its own SQL, and tried
  to kill two competing theories before conceding `CONFIRMED`. Its value is the refutation attempt, not
  the agreement.
