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

### SEV3 — force-push guard false-positives: a legitimate `git push` is denied when the command line also carries an unrelated `-f` short flag
- **File:** `hooks/pretooluse-guard.sh:51`
- **First seen:** 2026-06-20
- **Status:** open
- **Symptom:** A non-force `git push` is **denied** ("no git push --force") whenever the same command line contains an unrelated ` -f ` short flag — e.g. `git push origin main && grep -f pats.txt file.txt`, or `… && make -f Makefile build`, `… && tar -f out.tar …`. The deny reason wrongly claims a force push.
- **Root cause:** Rule 2 is `has 'git([[:space:]]|.)*push' && has '(--force([[:space:]=]|$)|[[:space:]]-f([[:space:]]|$))' && ! has 'force-with-lease'`. The two `has` clauses are evaluated independently against the **whole** line: `git([[:space:]]|.)*push` matches "git…push" anywhere (`.` ≈ any char), and `[[:space:]]-f([[:space:]]|$)` matches a `-f` that belongs to a *different* command in a `&&`/`;`/`|` chain. So an unrelated `git push` segment and an unrelated `-f` segment together satisfy the rule. (This is the **over-match** twin of the `-fv` **under-match** filed above — same rule, opposite-direction defect, independent fix.)
- **Evidence chain:** `hooks/pretooluse-guard.sh:51`. Live: `git push origin main && grep -f pats.txt file.txt` → **DENY**; `git push origin main && make -f Makefile build` → **DENY**; `git push --force` → `deny` (correct); `git push --force-with-lease` → `ALLOW` (correct).
- **Adversarial check:** Considered "chaining a `git push` with a `-f` command is rare." Rejected — `-f` is among the most common short flags (`grep`/`make`/`tar`/`find`/`ssh`/`docker`), and chaining `git push` after a build/cleanup step is routine; both live cases reproduce. Considered "plan 7 (PR #12) will fix it" — rejected: plan 7 neutralizes *quoted* spans only, and here the `-f` is unquoted and belongs to a separate chained command, so quote-neutralization leaves it matched.
- **Fix direction:** Bind the `-f`/`--force` match to the `git push` invocation itself (scan within the `git … push …` segment, or split on chain operators and evaluate per segment) rather than the whole line. Keep the real `git push --force` deny and the `--force-with-lease` allow intact.
- **Regression test:** `git push origin main && grep -f x y` → allow; `git push --force` → deny; `git push --force-with-lease` → allow.
- **Blast radius:** Single hook file; deny-tier only. False-positive blocks a legitimate `git push`; workaround is `MAUNGS_TOOLBELT_GUARD=off` or unchaining. The fix must not weaken the real force-push deny (block B invariants).
- **Suggested route:** `/orchestrator` (touches the structural security guard; can be batched with the other guard fixes in one pass + a `@security-reviewer` gate).

### SEV3 — catastrophic-`rm` deny is bypassed by separated or long flags (`rm -r -f /`, `rm --recursive --force /`)
- **File:** `hooks/pretooluse-guard.sh:61-64` (and the mirrored ask-tier at `:94`)
- **First seen:** 2026-06-20
- **Status:** open
- **Symptom:** `rm -r -f /` is **allowed** (no decision emitted), although the script's header comment states it "Blocks: … catastrophic rm -rf (/ ~ $HOME *)". The same gap applies to `rm -f -r /` and `rm --recursive --force /`.
- **Root cause:** Both the deny gate (`:61`) and the ask gate (`:94`) require `r` and `f` in a **single** flag token: `rm[[:space:]]+-[a-zA-Z]*[rR][a-zA-Z]*[fF]|rm[[:space:]]+-[a-zA-Z]*[fF][a-zA-Z]*[rR]`. Separated flags (`rm -r -f /`) and long flags (`rm --recursive --force /`) never co-locate both letters in one token, so neither tier fires; the command falls through to the normal permission flow with no guard-level block.
- **Evidence chain:** `hooks/pretooluse-guard.sh:61` (deny outer regex) + `:94` (ask outer regex). Live: `rm -r -f /` → **ALLOW**; `rm -rf /` → `deny`; `rm -fr /` → `deny`.
- **Adversarial check:** Considered "the guard is best-effort/fail-open, so this is by design." Rejected — the header explicitly *claims* catastrophic `rm -rf` is blocked, and separated/long flags are ordinary usage, not exotic; the bypass reproduces. Considered "the ask tier still catches it" — rejected: the ask-tier `rm` rule uses the *same* combined-token regex, so it misses too. This is **under**-enforcement (a real catastrophic command slips the hard block); the normal permission prompt still applies, so it is not a silent execution.
- **Fix direction:** Detect recursive-AND-force intent across separated/long flags — e.g. require `(-[rR]\b|--recursive)` AND `(-[fF]\b|--force)` near `rm`, in addition to the combined-token form — in both the deny and ask gates. Avoid a false positive on a benign `rm -r` of a safe relative dir.
- **Regression test:** `rm -r -f /` → deny; `rm --recursive --force /` → deny; `rm -rf /` → deny (unchanged).
- **Blast radius:** Single hook file; deny + ask tiers. Defense-in-depth safety control.
- **Suggested route:** `/orchestrator` (security guard; batchable with the other guard fixes + `@security-reviewer`).

### SEV3 — catastrophic-`rm` deny false-positives on ANY absolute path (`rm -rf /tmp/build`, `/var/log/...`), overriding the ask-tier disposable allowlist
- **File:** `hooks/pretooluse-guard.sh:62`
- **First seen:** 2026-06-20
- **Status:** open
- **Symptom:** `rm -rf /tmp/build`, `rm -rf /var/log/myapp`, and `rm -rf /home/foo` are all **denied** outright, though they target specific sub-paths, not `/`. The deny reason misleadingly says the target is "/ ~ $HOME or *". `/tmp` is even on the ask-tier's own disposable-path allowlist (`:95`), yet it is denied because the deny tier short-circuits before the ask tier runs.
- **Root cause:** The third alternative of the inner deny regex at `:62`, `rm[[:space:]]+-[rRfF]+[[:space:]]+(/|~|\*)`, matches `rm -rf /` followed by **any** path beginning with `/` (or `~`/`*`) — not a bare `/`/`~`/`*` token. So every `rm -rf /absolute/path` is treated as catastrophic. The companion alternative `…[[:space:]](/|~|\$HOME|\*)([[:space:]]|$)` is correctly anchored to a standalone token; this one is not.
- **Evidence chain:** `hooks/pretooluse-guard.sh:62` (third alternative) vs. the disposable allowlist at `:95` (lists `/tmp`, `tmp/`, …, unreachable for any abs path because deny wins first). Live: `rm -rf /tmp/build` → **DENY**; `rm -rf /var/log/myapp` → **DENY**; `rm -rf /home/foo` → **DENY**; `rm -rf ./build` → `ask` (correct).
- **Adversarial check:** Considered "denying all abs-path `rm -rf` is intentionally conservative." Rejected — it directly contradicts the ask-tier design (a disposable-path allowlist that is unreachable for abs paths) and the deny reason string's own scope ("/ ~ $HOME or *"). The two tiers are inconsistent; this is a defect, not intent. (Note: this **over-match** and BUG above's **under-match** are independent regex defects in the same `rm` block, with opposite directions and independent fixes.)
- **Fix direction:** Anchor the third alternative to a *bare* root/home/glob target, e.g. `rm[[:space:]]+-[rRfF]+[[:space:]]+(/|~|\$HOME|\*)([[:space:]]|$)`, so a specific abs path like `/tmp/build` correctly falls through to the ask tier and its disposable allowlist.
- **Regression test:** `rm -rf /` → deny; `rm -rf ~` → deny; `rm -rf /tmp/build` → ask (not deny); `rm -rf /var/log/app` → ask.
- **Blast radius:** Single hook file; deny-tier only. False positive blocks legitimate abs-path cleanup; workaround exists. The fix must keep `rm -rf /` and `rm -rf ~` denied.
- **Suggested route:** `/orchestrator` (security guard; batchable with the other guard fixes + `@security-reviewer`).

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
- **usage-tracker bare-slug fallback leans on `CLAUDE_PLUGIN_ROOT`** (`hooks/usage-tracker.sh:56-61`).
  The comment says the bare-slug resolution handles "a copy/install.sh install with no namespace," but
  the resolution requires `CLAUDE_PLUGIN_ROOT` (a plugin-mode variable), and `install.sh` copies only
  `agents/` + `skills/` (not `hooks/`), so a copy install has neither this hook nor that env var. The
  path is reachable only in plugin mode (where components are usually already namespace-matched). Reads
  as a misleading comment rather than a proven functional bug — confirming needs Claude Code's runtime
  `subagent_type`/`CLAUDE_PLUGIN_ROOT` values, which an offline sweep cannot observe.

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
