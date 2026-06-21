# Overnight bug backlog
**Last updated: 2026-06-21** — swept against `main` @ `4315db7`

A rolling, human-triaged backlog produced by the overnight `/bug-catcher --global`
sweep. Each entry is one confirmed bug (a candidate that survived an adversarial
refutation pass). It is a **diagnosis only** — nothing here has been fixed, and the
sweep never edits code, commits a fix, or merges. Triage in the morning; route each
item through `/orchestrator` or `/chore` under the normal gates.

Ordered **SEV1 → SEV4**. Every still-present bug keeps its original `First seen`
date as the reference; a bug that no longer reproduces is flipped to
`Status: resolved (<date>)` rather than deleted.

**Tonight: 4 new · 4 open · 0 resolved.**

> Method note: this is the repo's own methodology turned on itself. The conductor
> played both `@bug-catcher-rick` (diagnose: symptom → root cause → evidence @
> file:line → fix direction → blast radius) and `@bug-catcher-adversary` (cold
> re-derivation that tries to *disprove* each candidate) per finding, since
> subagents can't be spawned from this run. All three test suites were run green
> first (`test_router.py` 253/253 · `test_pretooluse_guard.py` 60/60 ·
> `translator_eval/eval.py` 420/420), so these are bugs the existing gates do
> **not** catch.

---

## SEV3 — the pre-commit guard's force-push deny is bypassed by bundled short flags

- **First seen:** 2026-06-21
- **Status:** open
- **Files:** `hooks/pretooluse-guard.sh:235`, `:257` (force-flag regex, used by
  `force_push_denies`); test gap in `tests/test_pretooluse_guard.py`
- **Component:** `pretooluse-guard.sh` (the shipped PreToolUse/Bash guard)

**Symptom.** The guard is supposed to structurally DENY `git push --force` (cardinal
rule: use `--force-with-lease`). It does deny the standalone forms `git push -f`,
`git push --force`, and even `git push -f -v`. But it **allows** the same force-push
when `-f` is bundled with another short flag: `git push -fv`, `git push -vf`,
`git push -fu`, `git push -uf` all pass through with **no deny**.

**Reproduction** (verified tonight against the shipped hook):
```
printf '%s' 'git push -fv origin main' \
  | jq -Rn '{tool_name:"Bash",tool_input:{command:input}}' \
  | bash hooks/pretooluse-guard.sh
# → no output (ALLOW).  'git push -f' / 'git push --force' → deny as expected.
```

**Root cause [CONFIDENT].** The force-flag detector is
`(--force([[:space:]=;|&)<>]|$)|[[:space:]]-f([[:space:]=;|&)<>]|$))`
(`hooks/pretooluse-guard.sh:235`, duplicated verbatim at `:257`). The `-f` alternative
requires `-f` to be a **standalone token**: a space immediately before it and a
terminator (`[[:space:]=;|&)<>]` or end-of-string) immediately after. Git's
`parse-options`, however, accepts **combined short flags** — `git push -fv` is a valid
invocation meaning `--force --verbose` and really does force-push. In `-fv` the char
after `-f` is `v` (not a terminator), and in `-uf` the `-f` is not preceded by a space,
so neither matches. The whole-string pre-filter at `:234`–`:235` already fails to fire,
so `force_push_denies` returns "no force push" before the segment split is even reached.

**Evidence chain.**
- `hooks/pretooluse-guard.sh:235` — pre-filter force-flag regex; `[[:space:]]-f(...)`
  demands a lone `-f`. → `:234` requires `git…push`; both must hold or the function
  returns 1 (allow).
- `hooks/pretooluse-guard.sh:257` — the per-segment check uses the **same** regex, so
  the gap is not recovered after the top-level split.
- `tests/test_pretooluse_guard.py` — grep for `-fv|-vf|-fu|-uf|bundl|combin` → **no
  matches**; the 60-case corpus never exercises a bundled force flag, which is why CI
  stays green over the hole.

**Adversarial check (tried to refute, could not).** Is `-fv` actually a force push, or
would git reject it? Git's option parser supports sticky/combined short options
(`-f` = `--force`, `-v` = `--verbose`), so `git push -fv` parses and forces — this is
not a contrived string, it's a form a non-evading agent might naturally type. Could the
neutralizer or another rule still catch it? No: the deny tier has only this one
force-push rule, the input is unquoted (no neutralization), and the empirical run above
confirms ALLOW. The competing theory "git rejects combined flags here" is killed by
git's documented parse-options behavior. Holds.

**Proposed SEV: 3.** A defense-in-depth safety guard fails to block exactly the
destructive operation it exists to block, for a valid and common flag form. Not SEV2
(no workflow is broken for all users; the bare/separated forms are still caught and the
guard is fail-open by design), but more than cosmetic — the cardinal rule it enforces
has a real hole.

**Fix direction.** Make the `-f` detector tolerate a short-flag cluster instead of a
lone token — match `-f` (or `-f`/`-F`) appearing anywhere inside a `-[a-zA-Z]*` cluster
that follows a space, e.g. an alternative like `[[:space:]]-[a-zA-Z]*f` (guarding the
`--force-with-lease` long form, which must still be exempt — it already is, via the
`--force-with-lease` continue at `:258`). Apply the identical change to both `:235` and
`:257` (single root cause, two call sites). **Add bundled-flag cases** (`-fv`, `-vf`,
`-uf`, `-fu`, and a `-fv --force-with-lease`-style exemption case) to
`tests/test_pretooluse_guard.py` — the missing coverage is part of the bug.

**Regression test.** `git push -fv origin main` → DENY; `git push -uf` → DENY;
`git push -fv --force-with-lease` *(if anyone bundles them)* → still consider lease
semantics; `git push -v` / `git push -u origin main` → still ALLOW (no false positive).

**Blast radius.** Only the force-push deny rule. The other deny rules (`git add -A/.`,
`--no-verify`, catastrophic `rm -rf`, AI-attribution) use unrelated patterns and are not
affected. Touching the regex risks new false positives on flag clusters that merely
*contain* an `f` (e.g. a hypothetical `-vf` that isn't force on some other git
subcommand) — but this rule is already gated behind `git…push`, where `-f` is force, so
the risk is contained. PR #18 recently reworked this same rule (segment-scoping), so the
area is fresh and a fix lands cleanly.

---

## SEV3 — `AGENTS.md` carries a stale **and internally contradictory** component count

- **First seen:** 2026-06-21
- **Status:** open
- **File:** `AGENTS.md:7`, `:27`, `:60`
- **Component:** `AGENTS.md` (one of the two authoritative agent-context files)

**Symptom.** `AGENTS.md` states the component count **three** times and disagrees with
both reality and itself: line 7 says "**16 agents + 10 skills (26 components)**", line 27
says "**9 skill conductors**", and line 60 says strict semver "currently `0.4.0`". The
filesystem has **16 agents + 11 skills = 27 components** (`ls agents/*.md` → 16;
`ls -d skills/*/` → 11) and `.claude-plugin/plugin.json` is at **`0.5.0`**.

**Root cause [CONFIDENT].** Doc drift. The `/todo` skill (merged in #22, commit
`4315db7`) made skills 11, and `/overnight` (#8) preceded it; the six **CI-checked**
files were updated (CI check #5 derives counts from the filesystem and asserts them in
`README.md`, `docs/components.md`, `docs/architecture.md`, `docs/design-philosophy.md`,
`.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` — all read 27 tonight),
but `AGENTS.md` is **not** in that asserted set, so its counts were never forced into
sync and rotted independently. Line 27's "9" is even older than line 7's "10" — the file
was partially updated at least once and left self-contradictory.

**Evidence chain.**
- `AGENTS.md:7` — "16 agents + 10 skills (26 components)" (wrong: should be 27/11).
- `AGENTS.md:27` — "**9 skill conductors**" (wrong *and* inconsistent with its own line 7).
- `AGENTS.md:60` — "strict semver (currently `0.4.0`)"; `.claude-plugin/plugin.json:4` is
  `"version": "0.5.0"`.
- `.github/workflows/validate.yml:139`–`:146` — the count-string assertions; `AGENTS.md`
  is absent from the list, so CI cannot catch this.

**Adversarial check.** Could CI actually be asserting `AGENTS.md` indirectly? No — the
`chk` calls at `:139`–`:146` enumerate exactly six files and `AGENTS.md` is not among
them; the frontmatter and leak-grep checks don't touch counts. Is 11 really the skill
count (not 10)? `skills/` holds agentic-onboard, bug-catcher, chore, handoff,
migration-planner, orchestrator, overnight, release-notes, todo, toolbelt,
wiki-generator = 11. Confirmed. Not refuted.

**Proposed SEV: 3.** Picked over SEV4 deliberately: `AGENTS.md` is one of the two files
agents read as ground truth, and it is *self-contradictory* (9 vs 10) — an agent
trusting it gets conflicting facts, and one acting on the "26/10" figure could "correct"
the six CI-checked files back to 26 and **break the build** (the exact load-bearing
invariant CLAUDE.md warns about). An adversary could reasonably argue SEV4 (docs-only, no
runtime/CI effect *today*); under-triage being the costlier error, it sits at SEV3.

**Fix direction.** Update `AGENTS.md` line 7 → "16 agents + 11 skills (27 components)",
line 27 → "11 skill conductors", line 60 → the current `plugin.json` version (`0.5.0`).
Note: `AGENTS.md` (and `CLAUDE.md`) being CI-unchecked is the deeper cause — a follow-up
could add them to the validate.yml count assertions so this can't recur, but that is a
separate enhancement, not part of this fix.

**Regression test.** None automated today (the file is outside CI's count check); adding
`AGENTS.md` + `CLAUDE.md` to the `chk` list in `validate.yml:139`–`:146` would be the
durable guard. Manual: re-grep the count strings after any agent/skill add.

**Blast radius.** Documentation only; no code path, no test, no CI assertion changes.

---

## SEV3 — `CLAUDE.md` component count is stale and its module map omits `/todo`

- **First seen:** 2026-06-21
- **Status:** open
- **File:** `CLAUDE.md:7`, `:43`, `:81`
- **Component:** `CLAUDE.md` (the primary agent-context file)

**Symptom.** `CLAUDE.md` says "**16 agents + 10 skills (26 components)**" at line 7 and
again at line 81, and its `skills/` module-map entry (line 43) reads "**10 skill
conductors** … Includes `overnight`" but never mentions `/todo`. Reality is **16 agents
+ 11 skills = 27 components**, and `/todo` is a shipped skill (`skills/todo/SKILL.md`,
wired into the prompt-router block `0c` and the `SessionStart` loader). The same file's
Gotchas also implies `plugin.json` is `0.4.0`-era guidance, while it is now `0.5.0`.

**Root cause [CONFIDENT].** Same drift class as the `AGENTS.md` entry above but a
distinct file with distinct specifics: the `/todo` (#22) and `/overnight` (#8) additions
updated the six CI-asserted files but not `CLAUDE.md`. Unlike `AGENTS.md`, `CLAUDE.md` is
internally consistent (it says 10/26 everywhere) — it is simply uniformly stale, and its
module map is missing the `/todo` line that `docs/components.md:92` and
`docs/architecture.md:39` already carry.

**Evidence chain.**
- `CLAUDE.md:7` and `:81` — "16 agents + 10 skills (26 components)" / "= 26 components".
- `CLAUDE.md:43` — "10 skill conductors … Includes `overnight`"; no `/todo`.
- `skills/todo/SKILL.md:1`–`5` — `/todo` exists with valid frontmatter; it is the 11th
  skill. `hooks/toolbelt-router.sh:102`–`107` routes it; `docs/components.md:92` /
  `docs/architecture.md:39` document it — confirming the omission is in `CLAUDE.md`, not
  reality.
- `.github/workflows/validate.yml:139`–`:146` — `CLAUDE.md` is not among the six
  asserted files, so CI can't catch it.

**Adversarial check.** Is `CLAUDE.md` perhaps intentionally counting only "stable"
skills and excluding `/todo`? No — line 43 explicitly *includes* `/overnight` (also a
recent, utility-tier skill) and the count "10" exactly equals "pre-`/todo`", so this is
omission-by-staleness, not a deliberate scoping. The "26" is wrong against every
CI-checked file. Not refuted.

**Proposed SEV: 3.** Same reasoning as the `AGENTS.md` entry: this is the file every
agent reads first, and its Gotchas section *instructs* agents that counts are
"load-bearing (CI hard-fail)" and must stay in sync — while stating the wrong count.
An agent that trusts CLAUDE.md's "26" and reconciles the six CI files toward it would
turn this doc bug into a red build. Adversary's SEV4 case (docs-only) is noted; held at
SEV3 to avoid under-triage.

**Fix direction.** Update `CLAUDE.md` lines 7, 43 (count + add a `/todo` clause to the
`skills/` entry), and 81 to "16 agents + 11 skills = 27 components"; refresh the
`0.4.0` → `0.5.0` semver mention in Gotchas. Keep this change **separate** from any
bug-fix PR (the bug-catcher cardinal rule: tooling/context edits ship as their own
`/chore`).

**Regression test.** None today; the durable guard is the same as the `AGENTS.md` entry
— add both agent-context files to the `validate.yml` count assertions.

**Blast radius.** Documentation only.

---

## SEV4 — `/todo` skill misdescribes the `SessionStart` loader's actual output line

- **First seen:** 2026-06-21
- **Status:** open
- **File:** `skills/todo/SKILL.md:80` vs `hooks/sessionstart-loader.sh:42`
- **Component:** `/todo` skill ↔ `sessionstart-loader.sh` (cross-component doc mismatch)

**Symptom.** `skills/todo/SKILL.md:80` claims the loader hook "adds a one-line
`📋 N open todos — /todo to view` to the project snapshot." The loader actually emits
`- Open todos: ${topen} (private backlog — /todo to view)` — no `📋`, different wording.
The described string never appears at runtime.

**Root cause [CONFIDENT].** The skill doc describes a sibling component's output from an
earlier (or aspirational) wording that the loader implementation doesn't match. The two
were not kept in lockstep.

**Evidence chain.**
- `skills/todo/SKILL.md:80` — "adds a one-line `📋 N open todos — /todo to view`".
- `hooks/sessionstart-loader.sh:42` — `add "- Open todos: ${topen} (private backlog — /todo to view)"`.

**Adversarial check.** Is the `📋` line emitted somewhere else (so the doc is correct for
a different path)? Grep of `sessionstart-loader.sh` shows the single open-todo emit at
`:42` with no emoji; no other component prints an open-todo line. So the doc is simply
inaccurate. The **behavior is otherwise correct** — the loader's slug
(`sessionstart-loader.sh:39`) and open-item grep (`^- \[ \] `, `:41`) match the skill's
canonical slug (`skills/todo/SKILL.md:32`) and item format (`- [ ] (tN) …`,
`skills/todo/SKILL.md:50`), so the **count is right**; only the *prose describing the
line* is wrong. Confirmed, narrow.

**Proposed SEV: 4.** Pure documentation cosmetics; no behavioral impact (the count and
file path are correct). Not eligible for the cosmetic-docs auto-remediation fast-path —
it touches an **agent/skill definition file** (explicitly excluded) and the "right" fix
has two options (correct the skill's prose, or change the loader to emit the documented
`📋` line), so it is *not unambiguous*. Route through the normal gate.

**Fix direction.** Either align `skills/todo/SKILL.md:80` to the loader's actual string,
or change `sessionstart-loader.sh:42` to match the documented `📋 N open todos` wording —
maintainer's call which is canonical. One-line change either way.

**Blast radius.** Documentation / one cosmetic output string. No logic, no test.

---

## Unconfirmed — looked at, dropped (no confirmed bug)

These were examined and **could not be confirmed** as bugs after refutation; recorded so
the next sweep doesn't re-chase them.

- **`/todo` slug ↔ loader divergence** — *refuted.* The skill (`SKILL.md:32`) and loader
  (`sessionstart-loader.sh:39`) compute the slug with the identical
  `sed 's#[^A-Za-z0-9]#-#g'` over the git root; the not-in-repo fallback differs (skill →
  `$PWD`; loader → exits early) but they only need to agree *inside* a repo, where they do.
  No bug.
- **Loader open-todo undercount** — *refuted.* `grep -c '^- \[ \] '`
  (`sessionstart-loader.sh:41`) matches the skill's `- [ ] (tN) …` open-item shape
  (`SKILL.md:50`); the count is accurate.
- **Catastrophic-`rm` deny coverage** (`pretooluse-guard.sh:299`–`303`) — *refuted.*
  Spot-checked `rm -rf /`, `rm -rf /*`, `rm -rf ~/`; all still DENY via the third
  alternative (`-[rRfF]+[[:space:]]+(/|~|\*)`). No gap found in the sampled forms.
- **Other deny rules** (`git add -A/.`, `--no-verify`, AI-attribution) — *spot-checked,
  no gap.* `git add -A` denies, `git add -p` allows, `--no-verify` denies. The
  AI-attribution rule could not be exercised cleanly tonight because the local probe
  harness (`jq -Rn input`) reads only the first line of a multi-line commit message — a
  **harness** limitation, not evidence of a guard defect; the CI corpus
  (`test_pretooluse_guard.py`, 60/60) covers it. Left unflagged.
- **Router intent coverage** — *sampled, no bug.* All 11 skills + agent intents have
  router blocks; `test_router.py` passes 253/253. Not exhaustively re-derived per intent.

> Scope note: this sweep **sampled** the guard's regex edge cases and the router corpus
> rather than exhaustively enumerating every shell-command shape; the translator
> `reference/` solutions and `examples/**` were not deeply audited (eval is green and
> they are illustrative, not load-bearing). Said plainly so the next pass knows what was
> and wasn't covered.

---

## Revision log

- 2026-06-21: +4 new · 4 open · 0 resolved — first sweep; created the dossier. New:
  guard force-push bundled-flag bypass (SEV3), `AGENTS.md` stale/contradictory counts
  (SEV3), `CLAUDE.md` stale count + missing `/todo` (SEV3), `/todo` skill misdescribes
  the loader output line (SEV4).
