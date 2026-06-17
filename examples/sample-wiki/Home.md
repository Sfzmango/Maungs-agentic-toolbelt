# ExampleApp Wiki

> Illustrative example of a `/wiki-generator`-produced wiki **Home / index** page. The fictional app is **ExampleApp**, a multi-tenant B2B SaaS helpdesk (Organizations → Members → Tickets → Billing). Everything below demonstrates the page contract: navigation grouped by taxonomy, onboarding learning paths, the wiki-wide `Last synced` SHA, and a no-gaps-hidden COVERAGE REPORT.

ExampleApp is a helpdesk that lets a business run its customer support inside its own private workspace. Each customer company (an "organization") gets an isolated space where its people — owners, agents, and viewers — handle support requests ("tickets") and pay for the product through plans and invoices. This wiki is the durable reference for that system: a new hire can read it to learn how ExampleApp works without opening the source, and a future agent can use it to orient in any module before making a change. Every page opens in plain business language, then goes deep technically, carries at least one diagram, links back to the real source files, and records the exact commit it was verified against so you can tell how stale it might be.

## Start here (learning paths)

**New hire, day one — read in this order:**
1. [Architecture overview](./architecture-overview.md) — what ExampleApp is and how its pieces fit together.
2. [Billing module](./module-billing.md) — a worked example of one domain module end to end.

**Fresh-context agent — orient before editing:**
- Skim [Architecture overview](./architecture-overview.md) for the tenant-isolation rule (every record is scoped to an organization; cross-tenant access returns 404).
- Open the module page closest to your change for its Related-files index back into source.

## Navigation

### Foundations
- [Architecture overview](./architecture-overview.md) — system context + high-level component/data flow.

### Domain modules
- [Billing](./module-billing.md) — plans, invoices, and how an organization pays for ExampleApp.

> The remaining taxonomy slots (data-model pages, the Organizations / Members / Tickets module pages, the API reference, per-flow sequence pages, UI screen-flows, glossary, onboarding, and external-dependencies) are **not present in this sample wiki** — see the COVERAGE REPORT below. They are listed so the gap reads as a deliberate choice, not a silent omission.

## Coverage report

This wiki never hides a gap. Every detected code area appears below with its page status. `COVERED` = a page exists and met the contract. `NOT BUILT (sample)` = the area exists in ExampleApp but was intentionally left out of this illustrative sample. `NEEDS SME REVIEW` = a page exists but flags an unresolved question for a subject-matter expert.

| Code area | Detected source root | Page | Status |
|---|---|---|---|
| System context & overview | (cross-cutting) | [architecture-overview](./architecture-overview.md) | COVERED |
| Billing module | `app/models/billing/`, `app/controllers/billing/` | [module-billing](./module-billing.md) | COVERED |
| Organizations module | `app/models/organization.rb`, `app/controllers/organizations_controller.rb` | — | NOT BUILT (sample) |
| Members & roles module | `app/models/membership.rb`, `app/controllers/members_controller.rb` | — | NOT BUILT (sample) |
| Tickets module | `app/models/ticket.rb`, `app/models/comment.rb`, `app/controllers/tickets_controller.rb` | — | NOT BUILT (sample) |
| Data model (full ER) | `db/schema.rb` | — | NOT BUILT (sample) |
| API / routes reference | `config/routes.rb`, `app/controllers/` | — | NOT BUILT (sample) |
| Key flows (signup, invite, checkout) | `app/services/` | — | NOT BUILT (sample) |
| UI screen-flows | `app/frontend/` (React) | — | NOT BUILT (sample) |
| Glossary | `CLAUDE.md`, code | — | NOT BUILT (sample) |
| Onboarding "start here" | (cross-cutting) | partial — see "Start here" above | NOT BUILT (sample) |
| External dependencies | `Gemfile`, `Dockerfile`, CI | — | NOT BUILT (sample) |

**Open gaps:** 10 taxonomy slots are NOT BUILT in this sample. None are hidden; a full `/wiki-generator` run against the real repo would fan out a `@wiki-writer` page for each and flip these rows to COVERED (or NEEDS SME REVIEW where a purpose is undeterminable from code + docs).

---
_Last synced: `a1b9f3c`._
