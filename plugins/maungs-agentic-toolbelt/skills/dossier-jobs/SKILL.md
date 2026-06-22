---
name: "dossier-jobs"
description: "Prepare the bug, security, and wiki scheduled-dossier workflows for Codex Automations. Uses automation-management tools when available; in Codex CLI it generates complete copy/paste Codex app automation configurations without claiming they were created. Invoke with `$dossier-jobs [repo] [flags]`."
---

# Codex adapter

This is the Codex version of the scheduled dossier workflow. Codex CLI does not
expose Claude's `RemoteTrigger` API. Never call or simulate `RemoteTrigger`.

## Inputs

Read the repository, selected jobs (`--bug`, `--security`, `--wiki`), schedule,
timezone, model, `--max-fixes`, and action flags from the user's request text
after the skill name. Resolve the repository from the positional argument or the
current checkout's `origin` remote.

## Supported behavior

1. Build the same three job prompts as the Claude workflow:
   - **bug**: run `$bug-catcher --global`; keep SEV1 issue-only; draft, never
     merge, at most `--max-fixes` non-SEV1 fix PRs.
   - **security**: run the `security-reviewer` subagent for a repository-wide
     compliance sweep; issue/comment output only.
   - **wiki**: run `$wiki-generator --update`; produce one rolling proposal PR.
2. Keep one rolling `[dossier-jobs] Dossier` issue and one marker-delimited
   comment per job so reruns update rather than duplicate.
3. Show the exact repository, local and UTC schedule, model, prompts, and outward
   actions before any creation/update/run action. Wait for explicit confirmation.
4. If the current Codex surface exposes automation-management tools, use them
   after confirmation and report the created automation identifiers.
5. In Codex CLI, where automation creation is unavailable, output a complete
   copy/paste configuration for three Codex app automations and the exact steps:
   open Codex app → Automations → New automation → select the repository and
   local environment → paste the prompt and schedule. Do not claim the
   automations were created.
6. `--status`, `--disable`, and `--run-now` operate only when automation tools are
   available. In CLI-only mode, print the exact Codex app action required.

## Safety

- Reads and preflight are free. Creation, update, disable, run-now, issue writes,
  and PR creation remain human-gated.
- Never auto-merge generated PRs.
- Never use `--dangerously-bypass-approvals-and-sandbox` to make a scheduled CLI
  job work.
- If unattended CLI execution would require bypassing approvals, stop and route
  the user to Codex app Automations instead.

## Output

Return a table for each selected job: action, repository, schedule, model,
prompt summary, automation id or `MANUAL APP SETUP REQUIRED`, and rollback
instructions. Clearly distinguish completed actions from generated setup.
