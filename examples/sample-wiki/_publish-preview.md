# Sample `--publish` dry-run preview

> Illustrative example of what `/wiki-generator --publish --dry-run` prints
> **before** the human approval gate. This is the artifact a human reviews to
> decide whether to publish; nothing has been pushed when it is shown. It targets
> the same fictional **ExampleApp** wiki the sibling pages in this folder
> demonstrate ([`Home.md`](./Home.md), [`architecture-overview.md`](./architecture-overview.md),
> [`module-billing.md`](./module-billing.md)). The page set is read from
> `docs/wiki/` and shipped **unchanged** — publish authors no content (cardinal
> rule 9); it only computes the platform page mapping and this preview.

## Case 1 — initialized wiki (the publish would proceed on approval)

When the GitHub repository wiki has been initialized (its first page was created
once via the Wiki tab), the probe reports `INITIALIZED`, the page set maps to wiki
page names, and the preview ends by offering the approval gate:

```text
PUBLISH PREVIEW — target: github
  Destination : example-org/exampleapp.wiki.git  (repo Wiki tab)
  Wiki state  : INITIALIZED
  Pages (3)   :
    docs/wiki/Home.md                  ->  Home          (wiki index/home page)
    docs/wiki/architecture-overview.md ->  Architecture-Overview
    docs/wiki/module-billing.md        ->  Module-Billing
    (generated _Sidebar from the page set)  ->  _Sidebar
  Nothing has been pushed. Approve to publish, or re-run with --dry-run to preview only.
```

On approval (without `--dry-run`), the GitHub adapter performs a **single-ref
atomic update** — one push of one branch to the wiki's default ref, all-or-nothing
at the ref level — reusing the human's existing local `git` / `gh` credentials. No
new secret is introduced and none is committed. On `--dry-run`, the preview prints
and the flow stops here: no gate, no push.

## Case 2 — uninitialized wiki (the publish is explained, not failed)

A GitHub repository wiki does not exist as a `*.wiki.git` repo until its first page
is created once via the web UI — there is no API to bootstrap it. The adapter
detects the "repository not found" signature on probe and turns it into a human
instruction rather than surfacing a raw git error:

```text
PUBLISH PREVIEW — target: github
  Destination : example-org/exampleapp.wiki.git  (repo Wiki tab)
  Wiki state  : UNINITIALIZED
  Action      : create the first Wiki page once in the Wiki tab, then re-run.
                (GitHub has no API to bootstrap a wiki — the first page is a
                 one-time manual step; nothing has been pushed.)
```

This is the path reachable on a repo whose wiki is enabled but not yet
initialized: the uninitialized state is named and explained up front, the approval
gate is not offered, and no push is attempted.

## The five reported failure classes (for reference)

If a publish does proceed and fails, the GitHub adapter names the cause and the
next step rather than swallowing the error:

| Failure class | What happened | Next step |
| --- | --- | --- |
| Auth | `gh` / `git` credential rejected | re-auth `gh` / `git`, then re-run |
| Uninitialized wiki | "repository not found" on the `*.wiki.git` remote | create the first Wiki page once in the Wiki tab, then re-run |
| Disabled Wiki tab | the Wiki feature is off for the repo | enable the Wiki tab in repo settings, then re-run |
| Network / push | transport / push error mid-operation | atomic single-ref update — no partial push left in an unknown state; retry |
| Remote-ahead / non-fast-forward | the wiki was edited in the Wiki tab between probe and push | the wiki changed since preview; re-run to re-probe and re-preview (no force-push) |
