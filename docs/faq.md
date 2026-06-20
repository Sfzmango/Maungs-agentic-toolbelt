# FAQ

Frequently asked questions about how the toolbelt behaves. Each answer is grounded in the component definitions and cites where the behavior is specified; for the underlying design principles see [`design-philosophy.md`](design-philosophy.md).

## Do worker agents apply their own judgement to what their adversary counterpart raises, or do they just comply?

Several workers are paired with a deliberately adversarial counterpart:

- `@context-writer` ↔ `@context-auditor` (drift detector)
- `@architect` ↔ `@plan-reviewer` (cold plan review)
- `@developer` ↔ `@pr-reviewer` / `@security-reviewer` (cold PR gate)

**The short answer: neither.** A worker never silently complies with its adversary, and it never privately overrules it. The judgement deliberately lives in a third place — the **conductor skill** (`/agentic-onboard`, `/orchestrator`) and a **human gate** — not in a direct negotiation between the worker and its adversary.

**Why the worker is not the adjudicator.** The adversaries are spawned *fresh-eyes* on purpose: `@plan-reviewer`, `@pr-reviewer`, `@security-reviewer`, and `@context-auditor` never read prior reasoning or prior reviews of the artifact they evaluate (see [the fresh-eyes split, §3](design-philosophy.md)). That independence is the whole value of the second pass, so the system is biased toward *taking the adversary seriously*. But the step that converts findings into action is owned by the conductor and the human — not by the worker rubber-stamping or vetoing.

Within that frame, each worker keeps a **judgement floor** that stops it from being a pure rubber stamp:

**`@context-writer` — trusts *what* drifted, verifies *what's true*.** In STALE mode it applies **only** the auditor's delta list and does not re-litigate which sections were flagged (`agents/context-writer.md`). But it does not transcribe blindly: for each delta it independently re-verifies the new value against the repo and cites the source, and — per its accuracy-over-completeness cardinal rule — it refuses to write a claim it cannot verify even if a delta asks for it, marking it "needs confirmation" and reporting any unresolvable delta rather than inventing the section. It trusts the auditor on *which sections drifted* and exercises its own judgement on *what is actually true now*.

**`@architect` — the verdict routes to a human gate.** The architect definition contains no plan-reviewer handling; it does not auto-apply the verdict. The reviewer returns `SOLID / REVISE / RETHINK` plus findings, which surface at the architect's plan-approval gate (`agents/architect.md`, Phase 4), where a human decides what to accept. A revision re-spawns the architect to re-draft against the accepted subset. The architect neither obeys nor overrules — it re-plans against the human-accepted findings.

**`@developer` — a fix loop with a circuit breaker against blind compliance.** A reviewer's verdict and punch list go to the orchestrator's human review gate first (`skills/orchestrator/SKILL.md`, Step 11); only if the human chooses "apply punch list" does it loop back to the developer's fix loop (`agents/developer.md`, Phase 5). And the developer will stop complying when compliance is backfiring: its quality-degradation breaker hard-halts the moment a fix round produces *more* findings than the previous one, and hands off instead of grinding further (see [quality-degradation circuit breakers, §5](design-philosophy.md)). This is the clearest case of a worker exercising judgement *against* simply doing what it is told.

**The one real debate.** The exception is a pair not in the list above: `@bug-catcher-rick` ↔ `@bug-catcher-adversary`. The `/bug-catcher` conductor runs an actual **bounded debate** — it re-spawns Rick with the adversary's critique, re-runs the adversary on the revised dossier, and caps the exchange at **3 rounds** to force convergence or escalation (`skills/bug-catcher/SKILL.md`). Even there, the conductor runs the debate and the human makes the final call; the two agents do not settle it between themselves.

**The pattern, in one line.** Adversaries carry independent weight; conductors and humans adjudicate; workers re-execute and retain only a hard floor — verify-don't-fabricate, stop-if-regressing — that prevents pure compliance. This is the [conductor-never-codes split, §7](design-philosophy.md) applied to review feedback: the worker does the work, the conductor and the human own the decision.
