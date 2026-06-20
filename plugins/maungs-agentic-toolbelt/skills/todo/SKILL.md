---
name: todo
description: A private, per-project to-do backlog you keep for yourself — work you've tabled for later, stored LOCALLY and never committed to the repo. With no argument it prints the list; with an argument it mutates it — `@todo <text>` (or `@todo add <text>`) adds an item, `@todo done <id>` completes one, `@todo drop <id>` removes one, `@todo all` shows completed items too. The backlog lives at `~/.claude/maungs-toolbelt/todos/<project-slug>.md` (per repo, like the toolbelt's usage log) — outside the repo, so it never enters the project's context, issues, or PRs. Other toolbelt components may READ it to guide you, but only you direct what goes on it. Invoke as `@todo`, `@todo <text>`, `@todo add <text>`, `@todo done <id>`, `@todo drop <id>`, or `@todo all`.
---

# @todo — your private, per-project backlog

This skill is a personal scratchpad for work you've **tabled for later** — "add a README section for X", "revisit the caching strategy", "circle back on that flaky test" — that you do NOT want to surface as a repo artifact (no issue, no PR, no committed `TODO.md`). It is the inverse of the in-session todo list Claude Code shows while working a task: that one is ephemeral and disappears; this one **persists across sessions** and is **yours**.

You are a **list keeper, not a doer**. `@todo` records, shows, and edits the backlog. It never *acts* on an item — turning a todo into work is a separate, explicit step the user takes (e.g. by then running `@orchestrator`, `@chore`, or `@bug-catcher`). Recording is the whole job.

The argument is in `$ARGUMENTS`.

## CARDINAL RULES (refuse to violate)

These hold for every invocation. A target project's `AGENTS.md / CLAUDE.md` may add conventions but never removes these:

1. **Write ONLY to the private local backlog file.** The only path this skill ever writes is `~/.claude/maungs-toolbelt/todos/<slug>.md` (and the directory it lives in, via `mkdir -p`). It **never** writes, edits, or stages anything in the project working tree; never runs `git`; never commits, pushes, or opens a PR; never creates a GitHub issue. The backlog is private by design — keeping it out of the repo is the entire point, so a todo must never leak into the project's context.
2. **Never invent or auto-add items.** You only add, complete, or remove what the user explicitly directs in THIS invocation. You may *read* the backlog to inform guidance, and you may *offer* ("want me to add that to your todo list?"), but you never mutate it on your own initiative. A backlog the user didn't write is worse than none.
3. **Confirm before destructive edits.** `drop`/`remove` and `clear` delete content. Show exactly what will be removed and get a one-word confirmation first. Add/complete are non-destructive and apply immediately (with a one-line echo of what changed).
4. **Per-project by default.** The list is scoped to the current repo (slug derived from the git root). Don't mix projects; don't write to another repo's file.
5. **Fail safe, never block.** If the backlog directory can't be created or the file can't be read/written, say so in one line and stop — never crash, never fall back to writing inside the repo.
6. **No AI-assistant attribution** in the file or any output.

## AUTO-DETECTION (run first, every invocation)

Resolve the backlog file with the **canonical slug computation** — used verbatim here and by the `SessionStart` loader hook so the two always agree:

```bash
root="$(git rev-parse --show-toplevel 2>/dev/null)"; [ -z "$root" ] && root="$PWD"
slug="$(printf '%s' "$root" | sed 's#[^A-Za-z0-9]#-#g')"
file="$HOME/.claude/maungs-toolbelt/todos/${slug}.md"
mkdir -p "$(dirname "$file")" 2>/dev/null
```

The slug is the repo's absolute path with every non-alphanumeric character turned into `-` — the same scheme Claude Code uses for `~/.claude/projects/<slug>/` — so e.g. a repo at `…/acme-api` becomes `-…-acme-api`. (All worktrees resolve to their own root; that's fine — a worktree gets its own list.)

Then read `$file` if it exists (it won't on first use). Also read the project's `AGENTS.md / CLAUDE.md` only for an attribution/terminology convention — never to decide *what* is on the list.

## FILE FORMAT (Markdown checklist — hand-editable)

One file per repo, two sections, stable `(tN)` ids so commands can target an item. Create it on first add with this exact shape:

```markdown
# Todos — <repo basename>
<!-- Private Maungs-agentic-toolbelt backlog. Local-only; never committed. Edit by hand or via @todo. -->

## Open
- [ ] (t3) reword the repo-wide docs as an agentic workflow engine — hold until v1 · added 2026-06-20
- [ ] (t2) add a README section for the new export flow · added 2026-06-19

## Done
- [x] (t1) draft the @todo skill · added 2026-06-18 · done 2026-06-20
```

- **ids** are monotonic per file: the next id is `t<max-existing-number + 1>`, never reused, even after a delete.
- **dates** use the host's local date (`date +%Y-%m-%d`). Newest open items sort to the top of `## Open`.
- The file is plain Markdown — the user can edit it by hand and `@todo` will still parse it.

## DISPATCH (by what `$ARGUMENTS` contains)

Parse the first token as a verb; if it isn't a known verb, treat the **entire** `$ARGUMENTS` as the text of a new item (so `@todo update the readme for X` just adds it).

| `$ARGUMENTS` | Action |
|---|---|
| *(empty)* | **List** — print `## Open` (newest first). If there are completed items, end with a one-line `(N done — @todo all to show)`. If the file is missing/empty, say the backlog is empty and show how to add. |
| `all` / `list` | List including the `## Done` section. |
| `add <text>` or any **unrecognized** leading text | **Add** — append `- [ ] (t<next>) <text> · added <today>` to `## Open`; echo the new id + text. |
| `done <id>` / `complete <id>` / `check <id>` | **Complete** — move the matching item to `## Done`, flip `[ ]`→`[x]`, append ` · done <today>`; echo it. If `<id>` doesn't exist, say so. |
| `drop <id>` / `remove <id>` / `rm <id>` / `delete <id>` | **Remove** — show the item, confirm (RULE 3), then delete the line. |
| `edit <id> <text>` | **Edit** — replace the matching item's text, keep its id + added-date; echo before/after. |
| `clear` | **Archive done** — show how many `## Done` items will be removed, confirm (RULE 3), then clear the `## Done` section. Never touches `## Open`. |
| anything starting `--` | Unrecognized flag — echo it and stop; don't guess. |

`<id>` may be given as `t3` or bare `3`. After any mutation, write the file back atomically (write, then move into place) and print the relevant slice so the user sees the result.

## HOW OTHER COMPONENTS USE THE BACKLOG

The `SessionStart` loader hook reads this same file (via the canonical slug above) and adds a one-line `📋 N open todos — @todo to view` to the project snapshot, so a tabled item resurfaces at the start of the next session. The prompt-router suggests `@todo` when a prompt sounds like tabling work ("remind me later…", "add this to my backlog"). `@toolbelt` lists `@todo` under Utility. None of these *act* on an item — they only surface the list; you decide what to do with it.

## RELATION TO AUTO-MEMORY

Don't confuse the backlog with auto-memory (`~/.claude/projects/<slug>/memory/`). Memory holds **durable facts and decisions** Claude maintains; the backlog holds **transient, completable work items** you maintain. They're cousins, not the same: a todo can reference a memory for context, but a finished todo gets cleared, while a memory persists. If the user asks to "remember" a durable fact, that's memory — not `@todo`.

## CIRCUIT-BREAKER table (failure modes)

| Failure mode | Action |
|---|---|
| **Backlog dir not writable** (`mkdir -p` / write fails) | Say so in one line with the path; do NOT write inside the repo as a fallback. |
| **Not in a git repo** | Fall back to `$PWD` for the slug; note that the list is tied to this directory, not a repo. |
| **`<id>` not found** for done/drop/edit | Say which id was requested and list the current open ids; change nothing. |
| **File hand-edited into a malformed shape** | Parse leniently (treat any `- [ ] …`/`- [x] …` line as an item); if ids are missing, renumber on the next write and say you did. Never discard content you can't parse — preserve unknown lines. |
| **Ambiguous mutate vs add** (leading word looks like a verb but isn't one) | If unsure, prefer **add** and echo "added as a new item — say `@todo done <id>` if you meant to complete one." |
| **User asks to act on an item** (implement it, open a PR) | Don't. Point at the right component (`@orchestrator`, `@chore`, `@bug-catcher`) for them to run; `@todo` only keeps the list. |
| **Token budget exceeded** | This is tiny work; if the file is enormous, show `## Open` only and note `## Done` was elided. |

## TOKEN BUDGET (self-imposed)

Soft budget: **8k tokens**. This is a list keeper — read one small file, run a couple of shell commands, print a slice. If an invocation approaches this, you're over-reading; show the open list and stop.

## Example invocations

> `@todo`
Resolve the file → print the open items (newest first) → footer `(2 done — @todo all to show)`. Nothing in the repo is touched.

> `@todo add a README section for the export flow`
Append `- [ ] (t4) add a README section for the export flow · added <today>` to `## Open`; echo `added (t4)`.

> `@todo done 2`
Move `(t2)` to `## Done`, mark it `[x]`, stamp ` · done <today>`; echo the completed item.

> `@todo drop t3`
Show `(t3)`, ask to confirm, then delete the line on a `yes`.

> `@todo all`
Print both `## Open` and `## Done`.
