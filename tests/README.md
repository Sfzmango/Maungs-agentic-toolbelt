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
