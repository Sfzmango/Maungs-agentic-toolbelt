# Design philosophy

This pipeline is **15 agents + 8 skills (23 components)** that take a fuzzy ask all the way to a merged PR — plus side-flows for bug diagnosis, chores, handoffs, and a self-maintaining codebase wiki. Agents are invoked with `@name` and run with a scoped toolset; skills are invoked with `/name` and act as conductors that delegate to agents.

What makes it a *system* rather than a bag of prompts is that the same seven design principles recur in every component. They were not retrofitted into a style guide after the fact — each one is a response to a specific, observed failure mode of LLM-driven development (context contamination, scope creep, silent quality regression, runaway token spend, an agent quietly committing on your behalf). This document states each principle, the failure it defends against, and points at the concrete place in the components where it is enforced.

A note on enforcement style: across the pipeline these principles are written as **refusals, not suggestions**. The developer agent's rules are headed "Cardinal rules (NOT guidance — refusals)"; the reviewers' are headed "Cardinal rules (refuse to violate)." That framing is itself a design decision — a soft "please prefer X" gets optimized away under pressure; a refusal does not.

---

## 1. Project-agnostic auto-detection

**The principle.** No component hardcodes a stack. Every agent and skill opens with an "Auto-detect project conventions" phase that runs *before any real work*, deriving language, framework, test runner, lint command, build step, pre-commit hook system, CI, plan-file location, and the project's own cardinal rules from files that are actually present. The same `@developer` that ships a Rails feature ships a Go or Rust one, because it reads the manifest instead of assuming one.

**The failure it defends against.** A pipeline that bakes in `bundle exec rspec` is a Rails toy. The moment it is pointed at a Node repo it either silently does nothing or confidently runs the wrong command. Auto-detection is what makes "project-agnostic" a real claim instead of a tagline.

**Concrete examples.**

- **`@developer` detects the toolchain instead of assuming it.** Its auto-detect step enumerates the mapping explicitly: test runner is "`bundle exec rspec` (Ruby), `npm test` / `yarn test` (Node), `pytest` (Python), `cargo test` (Rust), `go test ./...` (Go)"; lint is "`rubocop` / `eslint` / `ruff` / `clippy` / `golangci-lint`." It then reads the pre-commit hook config "to confirm the gate composition before you commit" — so the gate it runs is the gate the project actually defined, not a guessed one.
- **`@security-reviewer` detects the *security* toolchain the same way.** From the manifest it picks the right scanners: "`Gemfile` → Brakeman, bundle-audit; `package.json` → npm audit, eslint security plugins; `pyproject.toml`/`requirements.txt` → pip-audit, bandit; `go.mod` → govulncheck, gosec; `Cargo.toml` → cargo audit; `pom.xml`/`build.gradle` → OWASP dependency-check." Same auto-detection mechanism, specialized to a different concern.
- **`/orchestrator` detects the *workflow* conventions:** roadmap file (`DEVELOPMENT_PLAN.md` / `ROADMAP.md` / `ARCHITECTURE.md`), plan-file convention (`docs/plans/<id>_<slug>.md` vs `docs/proposals/<slug>.md` vs `RFCs/`), pre-commit system (`lefthook.yml` / `.pre-commit-config.yaml` / `.husky/`), CI, and deployment target (`Procfile` / `Dockerfile` / `fly.toml` / `vercel.json`).
- **Degrades honestly when there is nothing to detect.** Auto-detection is paired with an explicit fallback rather than a crash: `/orchestrator` says "If the project lacks agent-context discipline (no CLAUDE.md, no plan files, no roadmap), surface this to the user before starting + offer to either (a) bootstrap minimal context first, or (b) proceed with defaults." The `@pr-reviewer` carries the same discipline as a circuit-breaker — "No `CLAUDE.md`, no plan file, and no PR body → Surface the gap in the review body; review the code regardless using language defaults."

The detected `CLAUDE.md` / `CLAUDE.local.md` rules are always treated as **additive and non-removable**: "Project rules ADD to these, never remove them." A project can make the pipeline stricter; it can never use auto-detection to opt out of a cardinal rule.

---

## 2. Least-privilege tool scoping

**The principle.** Each agent's frontmatter `tools:` list is the minimum set required to do its job and nothing more. The capability boundary is enforced by the *toolset*, not merely by instructions in the prose — an agent that is told "do not commit" and is *also* not given a write-capable git path cannot commit even if a prompt-injection or a reasoning slip tells it to.

**The failure it defends against.** A reviewer that *can* edit the code it is reviewing will, eventually, "just fix this one thing" — and now the independent review signal is gone because the reviewer is also an author. Capability scoping makes whole classes of mistake structurally impossible rather than merely discouraged.

**Concrete examples.**

- **The read-only critics literally cannot write.** `@plan-reviewer`'s entire toolset is `Read, Bash, Grep, WebFetch, mcp__github__issue_read`. There is no `Edit`, no `Write`, no PR-write, no git-push path. The prose says "You critique it; the architect revises it" — but the toolset is what *guarantees* it. `@bug-catcher-adversary` is scoped identically (read-only + read-only GitHub): "Read-only against the codebase, git history, and (read-only) GitHub."
- **Reviewers get *write-only-to-GitHub-comments*, never to code.** `@pr-reviewer`, `@security-reviewer`, and `@security-mentor` each get `pull_request_review_write` and `add_comment_to_pending_review` but no `Edit`/`Write` and no `update_pull_request`. The boundary is stated as a precise capability sentence: "Read-only against the codebase; write-only against GitHub PR review comments." A reviewer can post a finding; it cannot touch the diff.
- **The architect can plan but not implement.** `@architect` has `Edit`/`Write` (it authors the plan file) and `create_pull_request` (it opens the PR with commit #1) — but the very first cardinal rule scopes that write power: "DO NOT touch application code. You write the project's plan file and plan-adjacent docs only." Conversely `@developer` carries the heavy toolset (Edit, Write, Bash, the full Playwright browser-driving set) because implementation genuinely needs it — and pays for that power with the strictest gates in the system (see §4).
- **The issue-shaper touches issues, not code.** `@product-owner` gets `issue_read`/`issue_write`/`list_issues`/`search_issues` and `AskUserQuestion`, but no `Edit`, no `Write`, no `Bash`. "You do NOT write code, edit application files, or touch the working tree" is backed by the absence of any tool that could.
- **The wrap-up agent's tools encode its narrow mandate.** `@resolution` gets `update_pull_request` (to flip checkboxes) and `add_issue_comment` (to reply/summarize) but deliberately *not* `pull_request_review_write` — it is not allowed to post a new review, only to resolve existing threads. The wiki agents follow the same shape: `@wiki-writer` is read-only on code and "writes only its page"; `@wiki-auditor` "writes nothing."

The pattern across the inventory: **the more an agent can do, the more gates and refusals it carries.** Capability and constraint scale together.

---

## 3. The deliberate fresh-eyes vs read-history split

**The principle.** Some roles are spawned *blind on purpose* — they are forbidden from reading any prior reasoning or prior review of the artifact they are evaluating. Exactly one role is the inverse: its entire job *is* reading the review history. This split is the single most load-bearing idea in the pipeline, so it is worth being precise about which side each component sits on.

**Fresh-eyes (context-blind) roles:** `@pr-reviewer`, `@plan-reviewer`, `@bug-catcher-adversary`, `@wiki-auditor` (and the security reviewers).
**Read-history role:** `@resolution`.

**The failure it defends against.** If the second reviewer reads the first review (or the author's own rationale), its "independent" signal collapses into agreement — it anchors on what it just read and rubber-stamps. The whole *point* of a second pass is to catch what the first pass missed, which is only possible if the second pass genuinely doesn't know what the first pass concluded. Independence is a property you have to actively protect; left alone, context leaks and the signal degrades to consensus.

**Concrete examples — fresh-eyes.**

- **`@pr-reviewer` refuses to read prior reviews as cardinal rule #1:** "Do NOT read prior PR review threads on the same PR before submitting your own review. Fresh eyes give an independent signal — the orchestrating workflow relies on this. If you accidentally fetch them, discard." Its workflow step 1 is literally "Refuse to read prior reviews. The workflow spawns you fresh exactly to avoid review-thread contamination."
- **`@plan-reviewer` is spawned blind between the architect's draft and the first commit:** "You have NO prior context from the planning conversation, the architect's reasoning, or any earlier review of this plan. That blindness is deliberate — you are the independent second opinion on a plan that exactly one agent has seen so far."
- **`@bug-catcher-adversary` re-derives the diagnosis from scratch:** "You have NO access to Rick's reasoning chain beyond the dossier you're handed, and you do not want it... a confirmation that comes from re-reading Rick's own logic is worthless. **Re-derive everything from the code** — the fresh-eyes rule is the whole point of this stage." Its verdicts (`CONFIRMED / DISPUTED / WRONG-ROOT-CAUSE / INCONCLUSIVE`) are only meaningful *because* it tried to kill the theory without having seen how the theory was built.
- **`@wiki-auditor` is the fresh-eyes drift detector for the wiki side-flow:** it compares an existing page against current code with no memory of why the page was written that way, and returns `CURRENT / STALE / INCORRECT / ORPHANED` plus a delta list. A drift detector that trusted the page's own claims couldn't detect drift.

**Concrete example — read-history (the deliberate inverse).**

- **`@resolution` is the exact mirror image, and its own docs say so.** Its description: "Unlike pr-reviewer, this agent IS told to read prior review history — that's its job." Cardinal rule: "DO read prior review history — that's the WHOLE POINT. The fresh-eyes constraint only applies to `pr-reviewer`. You need full context to know which threads are now resolved." It walks every thread, buckets each as resolved / acknowledged-open / stale, and replies citing the fixing commit (`git log --oneline --all -S '<distinctive snippet>'` finds the commit that fixed it). You cannot do that job blind — you need the whole history.

The two sides are not in tension; they are two different jobs that *require opposite information diets*, and the pipeline assigns each its correct diet. The reviewers' independence is what makes their verdict worth something; resolution's full context is what lets it close the loop without re-litigating it.

---

## 4. Human-in-the-loop commit / push gates

**The principle.** No agent ever commits or pushes on its own authority. Every commit and every push is a **separate, explicit human confirmation** — never bundled, never inferred from an earlier "go," never satisfied by silence. Amends and force-pushes count as their own gates.

**The failure it defends against.** An autonomous agent that commits and pushes on its own is one hallucinated diff away from polluting your history or your remote. Worse is the subtle version: an agent that interprets a casual "sounds good" three turns ago as standing approval to push five commits. The gate design closes that gap by demanding a *fresh, specific* affirmation at each irreversible step.

**Concrete examples.**

- **The gate shape is specified down to the affirmation token.** `@developer` cardinal rule #2: "Show the commit gate (`git status` + `git diff --stat` + commit message + target branch + `AskUserQuestion`) before EVERY commit. Show the push gate (`git log -1 --stat` + remote/branch + `AskUserQuestion`) SEPARATELY, AFTER the commit lands. Never bundle the two. Never interpret 'ok' / 'go' / 'proceed' / silence as approval — require explicit 'yes commit' then later 'yes push' for each."
- **Safety rails on the git commands themselves.** Adjacent cardinal rules forbid the footguns: "No `git add .` or `git add -A` — stage explicit paths only" and "No `--force`. Use `--force-with-lease`." So even an approved push cannot clobber a teammate's work, and a commit cannot sweep in unrelated working-tree changes.
- **Every component in the write path inherits the gates — including the lightweight ones.** `/chore` exists specifically to be the *fast* path, yet it keeps the same gates verbatim: "'lightweight' never means 'skip the gates.'" Its steps 4 and 5 are a commit gate ("Wait for explicit **'yes commit.'**") and a separately-shown push gate ("Wait for explicit **'yes push.'**"). The gates are non-negotiable regardless of how small the change is.
- **The conductor owns the *human* decision gates; the agents own the *git* gates.** `/orchestrator` step 11 is a human review gate it runs itself ("Ship as-is" / "Apply punch list" / "Abort"), and step 11b is a separate ready-to-merge sub-gate. And it never merges for you — the workflow ends with: "I won't merge — that's your call."
- **Even the dry-run respects the principle vacuously.** `/orchestrator --experiment` makes zero commits and zero pushes, so cardinal rules 1–2 "are satisfied vacuously (nothing commits/pushes)." The principle isn't bypassed in experiment mode — there is simply nothing irreversible to gate.

---

## 5. Quality-degradation circuit breakers

**The principle.** When a fix loop makes things *worse* — iteration N+1 surfaces more failures than iteration N — the pipeline does not push on. It **hard-halts**, writes a handoff, and recommends a fresh-context agent pick up. Iterating into a hole is treated as a first-class, named failure mode, not an edge case.

**The failure it defends against.** This is described in the components as "a real, recurring failure mode": round 1 finds a handful of FAILs, round 2 finds more, and an agent — having spent its context on the tangle it created — keeps going and makes it worse. Each iteration burns context and digs deeper. The right move when an iteration regresses is to *stop and hand off to fresh context*, and the only way to do that reliably is to count failures per round and trip a breaker on regression.

**Concrete examples.**

- **`@developer` counts FAILs per round and trips on regression.** "Quality degradation detection (HARD ESCALATE): If fix-loop iteration N+1's adversarial review finds MORE issues than iteration N, halt immediately. Do NOT attempt iteration N+2." It then writes a handoff capturing what's done, what's broken, both rounds' findings, and where the regression came from. The mechanism is explicit: "count FAIL findings per round; round N+1 FAILs > round N FAILs → STOP."
- **`/orchestrator` enforces the same check at the conductor level.** Step 10: "Quality degradation check: if iteration N+1 has more FAILs than iteration N → HARD HALT. Do NOT continue. Surface regression. Recommend handoff to a fresh-context agent." Its failure-escalation table makes it a hard rule: "pr-reviewer: round N+1 FAILs > round N → HARD HALT. Recommend handoff."
- **An absolute iteration ceiling backs up the regression breaker.** Even when each round *improves*, there is a hard cap: "Max 3 fix-loop iterations exhausted → Escalate with handoff, even if iteration 3 looks better than iteration 2." Two independent breakers — one on *trend* (regression) and one on *count* (3 rounds) — so neither a slow grind nor a sudden regression can run unbounded.
- **The breaker feeds a real escape hatch.** The recommended action is always "hand off to a fresh-context agent," which is exactly what the `/handoff` skill produces — "a self-contained, drift-aware brief so a zero-context agent (or future self) can resume work cold." The circuit breaker and the handoff skill are two halves of one mechanism: detect the spiral, then cleanly transfer the work to someone who hasn't been spiraling.

---

## 6. Token budgets with 60% / 80% checkpoints

**The principle.** Every agent declares a self-imposed soft token budget and two checkpoints: at **60%** it shifts into conservative mode (finish the load-bearing work, drop the nice-to-haves); at **80%** it halts, writes a progress summary, and hands off. The budgets are sized per role and treated as a planning discipline, not a hard harness limit.

**The failure it defends against.** A long-context agent that runs until it falls over produces no usable artifact and no clean resumption point — the work is stranded mid-thought. Self-budgeting turns "ran out of room" from a crash into a *managed handoff*: the agent always leaves behind a coherent partial result plus instructions to continue.

**Concrete examples.**

- **Budgets are sized to the role's actual reading load.** `@developer` ("The heaviest reader of all agents — codebase + plan + memory + diff context") and `@architect` and the reviewers each carry a **100k** soft budget; `@resolution` ("Moderate reader — mostly API responses + small code checks") carries **60k**; `@plan-reviewer` carries **80k**. The conductor `/orchestrator` deliberately runs *small* — **60k** — because it is "a lightweight router; heavy lifting in agents." The number reflects the job.
- **60% means "triage to the high-value work," and each agent knows its own priority order.** `@architect` at 60%: "Conservative mode: finalize the most-critical sections; skip the UI/UX ASCII mockups + extra examples; keep the core Mermaid flow diagram." `@pr-reviewer` at 60%: "Skip rubric items 6 (Blast radius) + 7 (Style fit); complete the 5 higher-priority items." `@bug-catcher-adversary` at 60%: "finish the six rubric items on the load-bearing evidence; drop deep sibling-case spelunking." The agent sheds the *least* important work first, on purpose.
- **80% means "stop and leave a clean handoff," never "stop mid-sentence."** `@pr-reviewer` at 80%: "Submit what's reviewed so far. Add 'Review incomplete — token cap reached on rubric item X of 7' to the body." `@developer` at 80%: "Halt; write a 1-2 paragraph progress summary + recommended next-agent invocation + surface to user." The artifact is always coherent and labeled with what's missing.
- **There's even an intermediate checkpoint for the agent that holds in-flight code.** Because `@developer` is the only agent with un-committed work in hand at the breaker point, its 60% rule is stronger than "be conservative": "Silently checkpoint: commit in-flight work to a `wip/<branch>-checkpoint` scratch branch (NOT the PR branch) + note progress to caller." It protects the work-in-progress *off* the PR branch so nothing is lost and the PR branch stays clean.
- **The conductor accounts for the whole lifecycle, not just itself.** `/orchestrator` notes the total budget across a full cycle "can be 200k+ — each agent self-manages within its own cap." Budgeting is per-agent precisely so the *sum* stays survivable.

---

## 7. Conductor-never-codes orchestration

**The principle.** The conducting skills — `/orchestrator`, `/bug-catcher`, `/wiki-generator` — delegate every phase to the specialized agent that owns it and **never do the engineering work themselves**. The conductor's job is routing, gating, state-passing, and circuit-breaking; the moment it is tempted to "just do this one bit," that is a signal to extend an agent, not to reach in.

**The failure it defends against.** A conductor that also codes loses every benefit of the rest of the system at once: the fresh-eyes split collapses (the conductor has seen everything), least-privilege evaporates (the conductor needs every tool), and the token budget blows (the router is now also the heaviest worker). Keeping the conductor thin is what keeps all the other principles intact.

**Concrete examples.**

- **`/orchestrator` states it in its first sentence and enforces it as an anti-pattern.** "You are the conductor. You do NOT do engineering work yourself — you delegate each phase to the named agent that owns it." Its 13-step flow is *all delegation*: `@architect plan issue <num>` → `@developer implement plan <path>` → `@pr-reviewer PR <num>` → `@resolution PR <num>`. And the temptation is named explicitly in "When something goes wrong": "Tempted to do agent work yourself: don't. Capture gap as `feedback` memory + suggest extending the agent."
- **The conductor enforces the *structure* the agents fill in.** `/orchestrator` owns the mandatory 3-commit PR shape — "Commit #1: plan file only (architect); Commit #2: implementation (developer, amend-friendly); Commit #3: plan-sync (optional)" — and the human gates, the degradation halt, and the `--experiment` dry-run. It dictates the shape; the agents produce the content.
- **State passes through artifacts, not through the conductor's head.** "State passes via file artifacts (plan files, GitHub issue body, PR body) and invocation messages... Agents re-read the plan + memory at their phase boundary; the orchestrator doesn't dump implementation context inline." The conductor stays thin precisely *because* it refuses to carry the work-context — which is also what keeps its 60k budget realistic.
- **The bug and wiki side-flows are the same pattern, specialized.** `/bug-catcher` is a "diagnose-and-prove conductor" that "DELEGATES diagnosis to the `@bug-catcher-rick` agent and refutation to the `@bug-catcher-adversary` agent," runs a bounded debate between them, and then hands the verified fix plan *off* to `/orchestrator` or `/chore` — it never fixes the bug itself. `/wiki-generator` is a conductor that delegates page authoring to `@wiki-writer` and drift detection to `@wiki-auditor`. Three conductors, one rule: **route and gate, never code.**
- **A conductor that finds its work is too big re-routes instead of growing.** `/chore` is the smallest workflow, and even it knows its own boundary: "A chore that grows mid-flight should be re-routed, not forced through" — stop and recommend `/orchestrator`. Right-sizing the conductor to the work is itself part of the discipline.

---

## How the principles reinforce each other

These are not seven independent rules; they interlock, and that interlock is the actual engineering argument:

- **Least-privilege (§2) is what makes fresh-eyes (§3) trustworthy.** A reviewer that *cannot* edit code stays a reviewer. Remove the tool boundary and "fresh eyes" becomes a promise the prose makes and the tools can't keep.
- **The circuit breaker (§5) and the token budget (§6) both terminate in the same place: a clean handoff** (the `/handoff` skill). One trips on quality regression, the other on context exhaustion, but both refuse to grind on and both leave a resumable brief. Detecting that you should stop is only useful if stopping is graceful.
- **Conductor-never-codes (§7) is what keeps every other budget and boundary honest.** The thin router is why the 60k orchestrator budget holds, why no single component needs every tool, and why the fresh-eyes agents can stay blind — the conductor never accumulates the global context that would contaminate them.
- **Auto-detection (§1) is the substrate the rest stand on.** The gates run the *project's* hook; the reviewers check the *project's* cardinal rules; the developer runs the *project's* test command. Every other principle is parameterized by what auto-detection found, which is what lets one pipeline serve any repo without being rewritten per stack.

The throughline: **make the safe thing structural, not optional.** Wherever a principle could have been "the agent should remember to…", it is instead enforced by a tool boundary, a refusal, a separate confirmation gate, or a counted threshold — so that getting it right does not depend on the model staying disciplined under load.
