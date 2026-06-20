# tests

Structured tests for the toolbelt's deterministic pieces (the hooks). Agents and
skills are model-driven and aren't unit-tested here; the hooks are plain scripts
and *are*.

## `test_router.py` — prompt-router routing test

Drives the real `hooks/toolbelt-router.sh` with 220+ labeled prompts and asserts each
routes to the intended component (or stays silent). It feeds each prompt to the hook
exactly as Claude Code would (a `UserPromptSubmit` JSON event on stdin) and maps the
emitted `additionalContext` back to the intent block that fired.

```bash
python3 tests/test_router.py        # prints a summary + any failures; exits 1 on failure
```

The corpus covers every intent block (greenfield, onboard, migration, security, review,
bug, tests, handoff, release, chore, document, plan, meta, build), plus three classes of
hard case the router must get right:

- **Mis-routes** — e.g. `add error handling` must NOT route to bug; `add a column to the
  data grid` must NOT route to migration; `set up a new project` must route to greenfield,
  not onboard (which is for existing repos).
- **Priority** — first-match-wins ordering (e.g. `review this PR for security issues`
  resolves to security, the higher-priority block).
- **Negatives** — ~25 unrelated prompts ("what's the weather", "tell me a joke") that must
  stay **silent** so the router doesn't nag on off-topic requests.

`expected` is a single label or a set of acceptable labels; `SILENT` means the router emits
nothing. Most cases are template-expanded so the label is correct by construction; the edge,
priority, and negative cases are hand-authored.

### Adding cases

Append to the corpus in `test_router.py` (`add(label, [...])` for a category, or
`cases.append((prompt, expected))` for a one-off). When you change a router pattern, run
this test — a green run means existing intents still route correctly and no negative started
firing.

## `test_pretooluse_guard.py` — guard-precision test

Drives the real `hooks/pretooluse-guard.sh` with a labeled corpus of shell commands and
asserts each yields the intended permission decision (`deny` / `ask` / `allow`). It feeds
each command to the hook exactly as Claude Code would (a `Bash` `PreToolUse` JSON event on
stdin) and maps the emitted `permissionDecision` back to the decision (no output → `allow`).

```bash
python3 tests/test_pretooluse_guard.py        # prints a per-block summary + any failures; exits 1 on failure
```

The corpus locks BOTH directions of the guard's precision contract, in six blocks:

- **A — quoted-argument false-positives → allow.** A banned token *mentioned* inside a quoted
  argument (a PR body or commit message) is documentation, not an invocation, and is allowed.
- **B — real invocations → STILL deny (the security invariant, #1 priority).** Every real
  dangerous command — bulk `git add`, the hook-bypass flag, a real force-push, catastrophic
  `rm -rf`, an AI-attribution trailer — must still deny. A weakening regression fails here.
- **C — allowed-by-design** (the `--force-with-lease` form, ordinary staged paths).
- **D — chaining / substitution / here-doc fail-closed.** A real invocation after `&&`/`;`, a
  danger token inside `$( … )`/backticks/a here-doc body, and ambiguous (unbalanced) quoting
  all still deny — the matcher scans the raw command when it cannot confidently neutralize.
- **E — ask-tier preserved** (destructive SQL, `reset --hard`, infra destruction still ask;
  the same SQL quoted as an argument now allows).
- **F — cross-segment force-flag false-positives → allow.** A force flag (`-f`/`--force`)
  belonging to an *unrelated* command segment (e.g. a real push refspec `;` `rm -f /tmp/x`)
  no longer trips the force-push rule, while a real `git push --force` co-located in the
  push's own segment still denies.

It also checks the **fail-OPEN contract** (a non-Bash tool, `MAUNGS_TOOLBELT_GUARD=off`, and
empty input all pass through).

> **Meta-footgun (read before editing):** the toolbelt ships this guard as a live
> `PreToolUse` hook, so a *literal* banned token (`git add -A`, the bypass flag, a real
> force-push, an AI co-author trailer) appearing in this test's **source** — or on the
> harness's own shell command line — would be DENIED, blocking the very `Bash` call that runs
> the suite. The test therefore **assembles every banned token at runtime** from harmless
> fragments and feeds each command to the guard via **stdin only** (never a shell arg). Keep
> both defenses; do not reintroduce a literal.

### Adding cases

Append to the corpus in `test_pretooluse_guard.py` via `add(block, [(command, expected), …])`.
Build any banned token from runtime fragments (see the fragment constants at the top of the
file) — never write a literal. When you change the guard, run this test: a green run means the
security invariant (block B) holds and no false-positive crept back in.
