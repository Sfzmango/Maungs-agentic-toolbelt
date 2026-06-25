<!-- Keep PRs scoped; stage specific paths (no `git add -A`). This is an owner-only development repo. -->

## Summary

<!-- What changed and why, in 1–3 sentences. -->

## Test plan

<!-- How you verified. The CI-run suites, run whichever apply:
     python3 tests/test_router.py             # routing
     python3 tests/translator_eval/eval.py    # translator reference vectors
     python3 tests/test_pretooluse_guard.py   # guard deny/ask/allow
     python3 tests/test_codex_build.py        # Codex generator + gate semantics -->

## Checklist

- [ ] **Bumped `.claude-plugin/plugin.json` `version`** (+ the Codex manifest `plugins/maungs-agentic-toolbelt/.codex-plugin/plugin.json` in parity) **if this PR changes shippable content** (`agents/`, `skills/`, `hooks/`, manifests). Claude Code caches installs by version — without a bump, users never receive the change. See [CONTRIBUTING](../CONTRIBUTING.md#bumping-the-version-every-pr).
- [ ] Regenerated the Codex artifacts (`python3 tools/build.py --target codex`) if a canonical `.md` or hook `.sh` changed — CI's drift guard hard-fails otherwise.
- [ ] Component counts + descriptions kept in sync (CI hard-fails) if a component was added or removed.
- [ ] No AI-assistant attribution in commit messages, the PR body, or files.
