# `/wiki-generator` — design deep-dive

A design doc for the wiki side-flow: `/wiki-generator` (the conductor skill),
`@wiki-writer` (the per-page author), and `@wiki-auditor` (the fresh-eyes drift
detector). For the one-line summaries of each component, see
[`components.md`](components.md); for the scheduled self-maintenance variant, see
[`scheduling.md`](scheduling.md). This document explains *why* the system is
shaped the way it is and how the three pieces fit together.

The wiki side-flow is orthogonal to the main plan → build → review → wrap-up
pipeline. It does not open PRs, write code, or gate merges. Its single job is to
produce and continuously re-sync a near-100%-coverage technical wiki for whatever
codebase it is pointed at, as plain Markdown under `docs/wiki/`.

---

## 1. The problem: docs rot, and manual upkeep is bureaucratic

Hand-written documentation has two failure modes, and they compound.

**Docs rot.** A wiki page is a snapshot of the code at the moment someone wrote
it. The code keeps moving; the page does not. Within a few sprints the page is
*confidently wrong* — which is strictly worse than no page at all, because a
reader trusts it. The lie is invisible: nothing in the page tells you it was
written against a schema, an endpoint, or a flow that no longer exists. The
reader (human or agent) acts on stale facts and the error surfaces somewhere
downstream, far from the page that caused it.

**Manual upkeep is bureaucratic.** The usual remedy is process: a "docs" checkbox
on every PR, a quarterly documentation sweep, a wiki-gardener rotation. This
works on paper and fails in practice. Updating prose by hand is slow, nobody's
priority, and impossible to verify — a reviewer can't tell whether the "update
the wiki" box was checked because the wiki was updated or because the box was in
the way. The cost is paid up front on every change; the benefit is diffuse and
deferred; so the work gets skipped, and the rot is back.

The wiki side-flow attacks both at once:

- **Generation is mechanical, not manual.** Pages are authored from the *actual
  code* by an agent (`@wiki-writer`), not typed up from memory by a human. The
  marginal cost of a page approaches zero, so near-100% coverage becomes
  affordable instead of aspirational.
- **Rot is detectable, not invisible.** Every page is stamped with the commit
  SHA it was verified against (§6). A second agent (`@wiki-auditor`) can diff the
  current code against that stamp and mechanically decide whether the page is
  still true. Drift stops being a thing you hope someone notices and becomes a
  thing the system reports.
- **Upkeep is incremental, not a sweep.** The `--update` mode (§3) re-authors
  *only* the pages the auditor flagged as drifted, so maintenance cost scales
  with how much actually changed, not with the size of the wiki. Put it on a
  schedule (see [`scheduling.md`](scheduling.md)) and the wiki maintains itself.

The design goal in one sentence: **make a correct page cheap to produce and make
an incorrect page impossible to hide.**

---

## 2. Roles and boundaries

Three components, mirroring the conductor + paired-agents shape of the bug
side-flow (`/bug-catcher` with `@bug-catcher-rick` and `@bug-catcher-adversary`).
The conductor sequences; the agents do the work in their own context windows.

| Component | Kind | Writes | Reads | Job |
| --- | --- | --- | --- | --- |
| `/wiki-generator` | skill (conductor) | nothing itself — orchestrates | the codebase shape, the existing wiki | Plans the page set, fans out to writers, runs the auditor in update mode, assembles the coverage report. Never authors a page itself. |
| `@wiki-writer` | agent | **exactly one** wiki page (`.md`) | the real code for that page's slice | Authors or re-authors one page from source. Read-only on code; the only thing it writes is its own page. |
| `@wiki-auditor` | agent | **nothing** | one existing page + the current code | Fresh-eyes drift detection. Compares a page against current code and returns a verdict + delta list. Writes nothing — not even the page it's judging. |

Three boundaries make the system trustworthy, and they are non-negotiable:

1. **The conductor never authors.** Just as `/orchestrator` never writes code,
   `/wiki-generator` never writes a page. If it could, the per-page contract
   (§5) and the one-page-per-writer isolation would erode. It plans, delegates,
   and assembles.
2. **The writer writes one page, from code, and nothing else.** One page per
   writer invocation keeps each authoring task small enough to do *thoroughly*
   from real source, and keeps a bad page blast-radius-limited to itself. The
   writer is read-only on code precisely so "documenting" can never mutate what
   it documents.
3. **The auditor writes nothing — including the page.** This is the fresh-eyes
   rule the pipeline applies everywhere (`@pr-reviewer` never reads prior
   reviews; `@bug-catcher-adversary` never sees Rick's reasoning chain). If the
   same agent both judged a page stale *and* rewrote it, "is this page correct?"
   and "did I write a correct page?" would collapse into one self-graded
   question. Separating detection from authorship keeps the audit honest: the
   auditor only ever produces a verdict and a delta list; a *fresh* `@wiki-writer`
   acts on it.

---

## 3. Two modes: full build vs incremental `--update`

`/wiki-generator` has exactly two operating modes, selected by the presence of
the `--update` flag in `$ARGUMENTS`.

### Full build (default) — `/wiki-generator`

Build the wiki from nothing (or rebuild it from scratch). Used on first
adoption, after a large refactor that reshapes the module map, or any time you
want a clean slate.

1. **Survey** the codebase to derive the page taxonomy (§4) — modules, data
   stores, request flows, public surfaces, cross-cutting concerns.
2. **Plan the page set**: one page per taxonomy node, plus the index, glossary,
   and onboarding pages. Present the planned set and rough count to the user
   before fanning out (a large repo is a large fan-out — no surprise token bills,
   same courtesy `/bug-catcher --global` extends).
3. **Fan out** to `@wiki-writer`, one invocation per page (§7). Each writer
   authors its page from real code and stamps it with the verified-against commit
   SHA (§6).
4. **Assemble** the index and glossary from the writers' returns and emit the
   **coverage report** (§8).

No auditor pass in a pure full build — every page is being written fresh against
current code, so it's verified-current by construction.

### Incremental update — `/wiki-generator --update`

Re-sync an existing wiki to the current code, touching only what drifted. This is
the steady-state mode and the one the scheduler invokes.

1. **Survey** the current code and **diff against the existing wiki** to find:
   - **new** taxonomy nodes (code exists, no page) → pages to add;
   - **removed** nodes (page exists, code gone) → pages to retire/mark orphaned;
   - **existing** nodes → candidates for an audit.
2. **Audit** every existing page with `@wiki-auditor` (§5–6). The auditor returns
   `CURRENT` / `STALE` / `INCORRECT` / `ORPHANED` plus a delta list.
3. **Re-author only the drifted pages.** `CURRENT` pages are left untouched
   (their stamp is bumped only if re-verified — see §6). `STALE` / `INCORRECT`
   pages, plus any new nodes, are handed to a fresh `@wiki-writer` along with the
   auditor's delta list as a focused work order. `ORPHANED` pages are retired or
   flagged per the orphan policy (§5).
4. **Re-emit** the coverage report, now including a **drift summary**: how many
   pages were audited, the verdict distribution, and which pages were rewritten.

The cost asymmetry is the whole point: a full build is `O(pages)` writer
invocations; an update is `O(pages)` *cheap* auditor reads plus only
`O(drifted pages)` expensive writer invocations. On a quiet week the update is
almost all `CURRENT` verdicts and rewrites nothing. That cheapness is what makes
putting it on a cron schedule sane — see [`scheduling.md`](scheduling.md).

---

## 4. The page taxonomy

Coverage is only meaningful against a definition of "everything." The taxonomy is
that definition: a mapping from the codebase to a set of pages such that every
significant unit of the system has exactly one home. It is **derived from the
code on each run**, not hardcoded, so it adapts to the project's actual shape
(the same auto-detection discipline every component in the pipeline follows).

Page types, derived per run:

- **Index / home** — the entry point: what the system is, the module map, and
  links to every other page. The one page guaranteed to exist.
- **Module / package pages** — one per significant module, service, or package.
  The backbone of the wiki and the bulk of the page count. Each pairs a
  *business* summary ("what this is for, in the domain's language") with a
  *technical* deep-dive ("how it actually works"). This dual register is what
  serves both audiences (§9).
- **Data-model / schema pages** — one per significant table, collection, or core
  entity: fields, types, relationships, invariants, and the migrations that
  shaped it. Rendered as a schema block plus an ER-style mermaid diagram.
- **Flow / sequence pages** — one per important end-to-end path (signup, checkout,
  a background job, an auth handshake). Rendered as a mermaid sequence or flow
  diagram tracing the real call path across modules.
- **Interface / API-surface pages** — one per public surface: HTTP endpoints,
  CLI commands, exported library API, message contracts.
- **UI pages** — for user-facing surfaces, the screen flow and low-fi mocks
  (consistent with the UI/UX artifacts `@product-owner` and `@architect`
  already emit), tied back to the components that render them.
- **Cross-cutting concern pages** — auth/authz model, multi-tenancy and isolation
  boundaries, configuration, observability, deployment. The things that don't
  live in one module but that a newcomer must understand.
- **Glossary** — one page; every domain term used across the wiki, defined once,
  linked from everywhere. The shared vocabulary that lets the business summaries
  stay in the domain's language without re-defining terms on every page.
- **Onboarding** — a guided reading order through the above for a brand-new
  contributor (the new-hire audience, §9): set up, run it, here's the spine of
  the system, here's where to start reading.

**One node, one page.** Every taxonomy node maps to exactly one page and every
page maps back to exactly one node. This bijection is what makes "coverage" and
"orphaned" *computable*: a node with no page is a coverage gap; a page with no
node is an orphan. Both are reported, not guessed at.

---

## 5. The per-page contract

Every authored page — regardless of type — conforms to a fixed contract. A
uniform shape is what lets `@wiki-auditor` audit *any* page mechanically and lets
a reader trust that the same information lives in the same place on every page.

A page MUST contain, in order:

1. **Title + node identity** — what this page documents and which taxonomy node
   it is (so the auditor can re-derive the node and detect orphaning).
2. **Business summary** — what this unit is *for*, in the domain's language. No
   jargon a new hire couldn't follow. This is the layer that serves onboarding.
3. **Technical deep-dive** — how it actually works: responsibilities, key types
   and functions, control flow, important invariants, gotchas. This is the layer
   that serves a future agent or an engineer in the code.
4. **Diagram(s)** — at least one mermaid diagram appropriate to the page type
   (ER for schema pages, sequence/flow for flow pages, a component sketch for
   module pages). Diagrams are code-derived, not decorative.
5. **Schema / signature block** — where applicable: the table schema, the type
   definitions, the endpoint signatures — transcribed from source, not
   paraphrased, so drift against them is detectable.
6. **Related files** — a list of the real source files this page is grounded in,
   each as a repo-relative path (`related files@path`). This is load-bearing in
   two directions: it's the reader's jump-to-source list, *and* it's the exact
   set of files the auditor re-reads to check the page for drift (§6).
7. **Verified-against stamp** — the commit SHA the page was last verified true
   against, plus the date (§6). The single most important line on the page.

The contract also defines the **drift verdict vocabulary** the auditor emits per
page (§6), and the **orphan policy**: an `ORPHANED` page (its node no longer
exists in the code) is not silently deleted — it is flagged in the coverage
report and either retired or kept with a prominent "this documents removed code"
banner, the user's call. Silent deletion would let real history vanish without a
trace; the bug side-flow's "no silent truncation" instinct applies here too.

---

## 6. Drift detection via per-page "verified against commit" SHA

This is the mechanism that turns "is the wiki still true?" from a judgment call
into a computation.

### The stamp

When `@wiki-writer` authors a page, it records the **commit SHA of the code it
read** as the page's verified-against stamp, alongside the related-files list
(§5, items 6–7). The semantics are precise: *as of commit `<sha>`, the related
files said what this page says they said.* The stamp is a claim about a specific
point in history, not a vague "last updated" date.

### How the auditor uses it

In `--update` and scheduled mode, `@wiki-auditor` is handed one existing page and
does a fresh-eyes comparison against the **current** code:

1. Read the page's stamp (`<sha>`) and its related-files list.
2. Compute what changed in those files between `<sha>` and `HEAD` (a scoped diff,
   not a whole-repo diff — the related-files list is what makes the audit cheap).
3. Read the *current* state of those files cold, without trusting the page's
   claims, and decide whether the page's business summary, deep-dive, diagrams,
   and schema block still match reality.

It returns exactly one verdict per page, plus a **delta list** — the specific
discrepancies, each tied to a file and what changed — for a downstream
`@wiki-writer` to fix:

| Verdict | Meaning | Conductor action |
| --- | --- | --- |
| **CURRENT** | The page still matches the code. No relevant change since the stamp, or changes that don't affect what the page claims. | Leave the page. Re-stamp to `HEAD` only if the auditor positively re-verified it. |
| **STALE** | The code moved in a way the page doesn't reflect — additions/changes the page is now missing, but nothing it says is outright false. | Hand the page + delta list to a fresh `@wiki-writer` to update. |
| **INCORRECT** | The page now asserts something the code contradicts — a wrong schema, a renamed function, a flow that no longer happens. Actively misleading. | Same as STALE, prioritized — an INCORRECT page is the dangerous case (§1). |
| **ORPHANED** | The page's taxonomy node no longer exists — the module/table/endpoint was removed. | Apply the orphan policy (§5): retire or banner. Do not silently delete. |

The verdict drives the conductor's action automatically, exactly the way SEV
drives `/bug-catcher`'s routing. Only `STALE`/`INCORRECT`/`ORPHANED` cost a
writer invocation or a decision; `CURRENT` costs only the cheap audit read. That
is the economic engine behind the incremental mode.

### Why scope the diff to related files

Auditing a page against the *entire* repo diff would be expensive and noisy. The
related-files list (§5) is the contract that makes the audit both cheap and
precise: the page declares what it's grounded in, and the auditor checks exactly
that ground. The flip side is a discipline on the writer: if a page's claims
depend on a file, that file MUST be in the related-files list, or drift in it
will be invisible to the auditor. Completeness of the related-files list is the
property the whole drift-detection scheme rests on.

---

## 7. Fan-out to `@wiki-writer`

The conductor never authors. It fans out — one `@wiki-writer` invocation per page
— and each writer owns its page end to end in its own context window.

- **Full build:** one writer per planned taxonomy node. These are independent
  (each reads a different code slice and writes a different file), so they
  parallelize cleanly. The conductor warns on large fan-outs before launching.
- **Update:** one writer per drifted page only. Each is invoked *with the
  auditor's delta list for that page*, so the writer isn't re-deriving the whole
  page from scratch — it's applying a focused set of corrections against current
  code and re-stamping to `HEAD`. New nodes get a full authoring pass like a
  build.

The writer's invariants (read-only on code, writes exactly its own page, stamps
the verified-against SHA) are what make the fan-out safe to parallelize:
disjoint write targets, no shared mutable state, no writer able to corrupt
another's page or the code. The conductor collects each writer's return (page
path, node, verdict-of-record, stamp) and threads them into the index, glossary
cross-links, and coverage report.

State passes between conductor and agents the same way it does in
`/orchestrator`: via **file artifacts** (the pages themselves, the existing wiki)
and **invocation messages** (the conductor's per-page work order — for an update,
that work order *is* the auditor's delta list). The conductor doesn't dump a
page's full context inline; the writer re-reads its code slice at its own phase
boundary.

---

## 8. The coverage report

Every run ends with a coverage report — the artifact that makes "near-100%
coverage" a measured claim instead of a slogan. It answers, in one place: *what
does the wiki cover, what does it miss, and how fresh is it?*

It reports:

- **Coverage** — taxonomy nodes with a page vs. total nodes, with the gaps named.
  A node with no page is a hole; the report points right at it rather than
  letting it hide.
- **Freshness** — per page, the verified-against SHA and how far behind `HEAD` it
  is. The wiki's overall "as-of" honesty, at a glance.
- **Drift summary** (`--update`/scheduled runs) — the auditor verdict
  distribution: how many `CURRENT` / `STALE` / `INCORRECT` / `ORPHANED`, and
  which pages were rewritten this run. This is the headline the scheduled variant
  surfaces (see [`scheduling.md`](scheduling.md)) — a quiet run is all `CURRENT`;
  a noisy one tells you exactly where the code outran the docs.
- **Orphans** — pages whose node is gone, awaiting the retire/banner decision.

The report is the system's self-assessment and the human's dashboard. In the
scheduled mode it's the thing worth notifying on: if a run comes back with
`INCORRECT` pages or a coverage drop, that's a signal the wiki needs a human
glance; an all-`CURRENT` run is a no-op you never have to think about.

---

## 9. Dual audience: future agents *and* new hires

Every page is written for two readers at once, which is why the per-page
contract (§5) deliberately separates a **business summary** from a **technical
deep-dive**.

- **Future agents.** A zero-context agent — a fresh `@architect` planning in this
  module, a `@bug-catcher-rick` hunting a root cause, a `/handoff` recipient
  resuming cold — can read the relevant page and acquire grounded, *current*
  context (current because of the drift machinery) without re-deriving the
  system from raw source every time. The related-files list gives the agent its
  exact jump-to-source points; the verified-against stamp tells it how much to
  trust the page versus re-reading. In effect the wiki is a durable, queryable,
  self-checking memory layer for the agent fleet — distinct from per-project
  auto-memory, which captures decisions and feedback rather than a structural map
  of the code.
- **New-hire onboarding & reference.** A human joining the project reads the
  onboarding page for a guided path, leans on the business summaries to learn
  *what* things are for in the domain's language, drops into the technical
  deep-dives as a reference when working in a module, and uses the glossary to
  decode the team's vocabulary. Because the same pages serve both audiences, the
  onboarding material can't rot independently of the code — it rides the same
  drift detection as everything else.

Serving both from one artifact is deliberate. Documentation written only for
humans tends to omit the precise file/line grounding agents need; documentation
written only for agents tends to skip the domain "why" a human needs. The
two-register page gives each reader its layer, and the single drift-detection
mechanism keeps *both* layers honest at once — fixing the rot problem (§1) for
the onboarding docs and the agent context simultaneously.

---

## 10. Output: Markdown at `docs/wiki/`

The wiki is plain Markdown under `docs/wiki/` — one `.md` per taxonomy node, with
`index.md` as the home page, plus `glossary.md` and `onboarding.md`. This
location is the documented default and is configurable via the skill definition
(per [`CONTRIBUTING.md`](../CONTRIBUTING.md)).

Markdown-on-disk is a deliberate choice, not a placeholder:

- **It lives with the code, versioned in git.** The wiki is reviewable in PRs,
  diffable across commits, and — crucially — the verified-against stamps point at
  the *same* git history the pages live in. Drift detection is just `git` math
  over files in the same repo.
- **It renders everywhere.** GitHub, the editor, any static-site generator,
  and any agent reading the raw file all get the same content. The mermaid
  diagrams render in-place on GitHub and most viewers.
- **It's agent-native.** A file an `@wiki-writer` writes and an `@wiki-auditor`
  reads is the same artifact a `@bug-catcher-rick` or `@architect` reads later.
  No database, no export step, no extra surface to keep in sync — the
  documentation format and the agent-context format are one and the same.

The wiki side-flow writes only inside `docs/wiki/` (plus the coverage report).
It never touches source, never opens a PR, and never merges anything — keeping it
cleanly orthogonal to the main pipeline, exactly as a self-maintaining
documentation layer should be.

---

## See also

- [`components.md`](components.md) — one-line reference for all 25 components.
- [`scheduling.md`](scheduling.md) — the scheduled self-maintenance variant: how
  to run `/wiki-generator --update` on a cron so the wiki keeps itself current.
- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — where the `docs/wiki/` location and
  other defaults are configured.
