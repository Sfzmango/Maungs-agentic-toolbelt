# Bug backlog — `/bug-catcher --global` (overnight)

> Rolling, human-triaged backlog produced by the overnight `/bug-catcher --global` routine.
> One entry per confirmed bug, ordered SEV1 → SEV4. Each was diagnosed (symptom → root
> cause → evidence @ file:line → fix direction → blast radius) and then adversarially
> re-derived from the code before being trusted. This file is **diagnosis only** — no code
> is fixed here; each item routes through its own gated pipeline (`/orchestrator` or `/chore`).
>
> Triage in the morning; split into per-bug issues/PRs as needed.

_Last sweep: 2026-06-20 · against `origin/main` @ `3b7574c`_

---

## Open

### SEV3 — AI-attribution commit guard is case-sensitive; the standard `Co-authored-by:` trailer bypasses it
- **File:** `hooks/pretooluse-guard.sh:68`
- **First seen:** 2026-06-20
- **Status:** open
- **Symptom:** A commit carrying the git/GitHub-canonical AI co-author trailer `Co-authored-by: Claude` (capital **C** only) — or any lowercase variant such as `generated with claude code` — is **allowed** through, even though the guard's stated job is to deny AI-attributed commits (a cardinal rule, `CLAUDE.md` "Commit & PR policy").
- **Root cause:** Rule 5 matches with `has` (`grep -qE`, **case-sensitive**) against the literal `Co-Authored-By:` / `Generated with .* Claude`. Git trailers are case-insensitive and the standard spelling is `Co-authored-by:` (capital C, lowercase rest), so the most common real form never matches. The sibling **ask-tier** rules (lines 79–106) deliberately use the case-insensitive helper `hasi` — rule 5 is the lone deny-tier rule that does not.
- **Evidence chain:** `hooks/pretooluse-guard.sh:38` (`has` = `grep -qE`, no `-i`) → `:39` (`hasi` = `grep -qiE`) → `:68` (rule 5 uses `has`). Live: `Co-Authored-By: Claude` → `deny`; `Co-authored-by: Claude` → **ALLOW**; `generated with claude code` → **ALLOW**.
- **Adversarial check:** Considered "exact-match is intentional (catch only Claude Code's literal output)." Rejected — the rule's documented purpose is *no AI attribution at all*, `Co-authored-by:` is the canonical git/GitHub spelling (a real, common input), and every neighbouring data-loss rule already uses `hasi`. The bypass reproduces on standard input.
- **Fix direction:** Match the attribution literals case-insensitively (use `hasi`, or fold case into the alternation) while keeping the `🤖` literal. Re-confirm the open guard-precision plan (`docs/plans/7_guard-quoted-arg-precision.md`, PR #12) preserves this once implemented — its test block B should assert the lowercase/standard-cased trailer also denies, not only `Co-Authored-By:`.
- **Regression test:** Add guard cases asserting `deny` for `Co-authored-by: …`, `co-authored-by: …`, and `generated with claude` (mixed case), alongside the existing `Co-Authored-By:` case.
- **Blast radius:** Single hook file; deny-tier only. No change to already-denied exact spelling; no other rule touched. It hardens the security-surface guard, so it warrants a review pass.
- **Suggested route:** `/orchestrator` (touches the structural security guard; SEV3).

### SEV4 — force-push guard misses combined short flags (`git push -fv` / `-vf` are allowed)
- **File:** `hooks/pretooluse-guard.sh:51`
- **First seen:** 2026-06-20
- **Status:** open
- **Symptom:** `git push -fv` (or `-vf`) force-pushes but is **allowed**, while the documented equivalents `git push -f` and `git push --force` are correctly denied.
- **Root cause:** The short-flag branch `[[:space:]]-f([[:space:]]|$)` only matches `-f` as a **standalone token**; a combined short-flag cluster like `-fv` puts a non-space character after `f`, so it never matches.
- **Evidence chain:** `hooks/pretooluse-guard.sh:51`. Live: `git push -f` → `deny`, `git push --force` → `deny`, `git push -fv` → **ALLOW**, `git push -vf` → **ALLOW**. `git push --force-with-lease` → `ALLOW` (correct, must stay).
- **Adversarial check:** Considered "`-fv` is exotic/unlikely." Rejected — combining short flags is standard git CLI usage and `-fv` genuinely force-pushes; live test confirms the bypass. The existing `! has 'force-with-lease'` clause keeps the lease form allowed even after broadening, so a fix is safe.
- **Fix direction:** Broaden the short-flag branch to match `f` anywhere in a short-flag cluster (e.g. a `-[a-zA-Z]*f`-style token bounded to a real flag group), keeping the `force-with-lease` exclusion that already guards the lease form.
- **Regression test:** Guard cases asserting `deny` for `git push -fv` and `git push -vf`, and `ALLOW` for `git push --force-with-lease` (no regression).
- **Blast radius:** Single hook file; deny-tier only.
- **Suggested route:** `/chore` (one file, no migration/security-data surface).

### SEV4 — `git add ./` bypasses the bulk-add guard
- **File:** `hooks/pretooluse-guard.sh:46`
- **First seen:** 2026-06-20
- **Status:** open
- **Symptom:** `git add ./` stages the entire working tree (the exact footgun the cardinal rule forbids) but is **allowed**, while `git add .` is correctly denied.
- **Root cause:** The "current dir" branch `\.([[:space:]]|$)` requires the `.` to be followed by whitespace or end-of-string. In `git add ./` the `.` is followed by `/`, so the pattern misses it even though the behaviour is identical to `git add .`.
- **Evidence chain:** `hooks/pretooluse-guard.sh:46`. Live: `git add .` → `deny`, `git add -A` → `deny`, `git add --all` → `deny`, but `git add ./` → **ALLOW**.
- **Adversarial check:** Considered "`./` is out of scope of the documented `git add .` rule." Rejected — `git add ./` stages the whole tree exactly like `git add .` (the documented hazard); it is a trivial equivalent that defeats the guarantee. Reproduces in live test.
- **Fix direction:** Extend the dot branch to also match a trailing `./` (e.g. `\.\/?([[:space:]]|$)`), being careful not to also match unrelated relative paths like `git add ./src/x` (which is a *specific* path and should stay allowed).
- **Regression test:** Guard case asserting `deny` for `git add ./`, and `ALLOW` for an explicit relative path such as `git add ./src/file.py`.
- **Blast radius:** Single hook file; deny-tier only.
- **Suggested route:** `/chore` (one file, no migration/security-data surface).

---

## Resolved

_(none yet)_

---

## Unconfirmed — observations, not filed as bugs (need evidence or are by-design)

These were considered and **dropped** from the backlog (each is either correct-as-of-now or
explicitly documented behaviour), recorded here so a future sweep doesn't re-litigate them:

- **Leak-grep does not scan `*.py` / `*.toml`** (`.github/workflows/validate.yml:61`). Currently the
  `.py` files are clean (verified), and `CLAUDE.md` documents the gate's scope as `*.md`/`*.json`/`*.sh`,
  so this is a documented coverage limitation, not a present defect. (Open PR #7 / the Codex port widens it.)
- **`AGENTS.md` and `CLAUDE.md` carry component-count strings that CI does not enforce** (only the six
  files in `validate.yml`'s step 5 are checked). All counts are consistent today (16 agents + 9 skills =
  25 components), so there is no current bug — but a future component add could drift these two files
  silently. Latent risk, not a reproducing bug.
- **`git commit -am …` is not denied.** It stages all *tracked* modifications; whether that falls under
  the documented `git add -A/.` rule is a scope judgment, not a clear defect. Left as an observation.

## Sweep scope & bounds (no silent truncation)

- **Slices covered:** Bash hooks (`hooks/*.sh`), Python suites (`tests/test_router.py`,
  `tests/translator_eval/eval.py` — both run green: 237/237 router, 420/420 eval case-runs),
  installers/CI/manifests (`install.sh`, `.github/workflows/validate.yml`, `.claude-plugin/*.json`,
  `hooks/hooks.json`), and prompt-logic (`agents/*.md`, `skills/**/SKILL.md`, docs Markdown:
  fences/mermaid balanced, relative links resolve).
- **N/A on `main`:** the `tools/build.py` + `tools/emit/*` generator, `install-codex.sh`, and the
  generated `codex-*` artifacts named in the routine brief **do not exist on `main`** — they live in
  open PR #7 (`6-codex-port`) and were therefore out of scope for this sweep of `main`.
- **Bounded, not exhaustive:** the guard/router regexes were probed against the documented footgun
  spellings plus common equivalents (combined flags, casing, `./`), not fully fuzzed across every
  branch; the translator reference solutions were validated functionally by the eval (420 case-runs)
  rather than re-read line-by-line.
