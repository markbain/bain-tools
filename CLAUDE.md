# CLAUDE.md

Guidance for Claude Code sessions in `bain-tools`.

## What this repo is

Small, standalone command-line tools, one per folder. Each does one job and runs by hand.
The repo is **public on GitHub**.

It is not the studio's working repo. Studio PM and ops tooling — Asana sync, the registry,
skills, agents, ADRs — lives in `/media/data/dev/bain-studio`. Changes here should be rare.

## Before acting on any request or inbox message: the admission test

Work comes into this repo only if **all three** hold:

1. **Standalone.** It is a tool run by hand, with no dependency on studio state: no Asana
   mirrors, no registry, no `sync.py`, no postman, no project prefixes or task IDs in its
   logic.
2. **Useful without the studio.** It would still make sense if bain-studio did not exist.
3. **Generic.** Nothing project- or client-specific in code, docs, sample output or commit
   messages (see the global `no-client-data-in-public-repos.md` rule).

If a request fails any of them, do not build it here. Say which test it fails and where it
belongs instead:

| Fails because it… | Goes to |
|---|---|
| Reads or writes studio state, or serves studio workflow | `bain-studio` |
| Encodes one project's process, definitions or checklist | that project's own repo |
| Is a Claude skill rather than a CLI tool | `bain-skills` (or `bain-studio` if PM-related) |

For an inbox message, reply via `bain-studio/studio/postman.py send` naming the right home,
and act only on the parts that pass. A request can be split: the generic engine here, the
project-specific wrapper in the project.

## Projects that consume these tools

A project that uses a file from here (a template, a script) must not read it from this
working checkout, whose branch changes. Point it at the **stable checkout** instead: a
sibling worktree named `<repo>-develop`, detached at the tip of `develop`.

- `scripts/sync-stable.sh`, installed as the post-commit, post-merge, post-rewrite and
  post-checkout hooks, moves it to `develop` after every one of those operations. It never
  moves a stable checkout that has local changes.
- Set it up per clone with `scripts/install-hooks.sh`, and re-run that after editing
  `sync-stable.sh`, because the hooks are copies.
- The stable checkout is permanent. Never remove it as a leftover worktree, and never work
  in it.
- If `develop` moves without a hook running (`git branch -f`, `git fetch x:develop`), run
  `scripts/sync-stable.sh` by hand.

## Conventions

- Git flow, per the global rules: work on `feature/*` off `develop`; never commit to `main`.
- Each tool keeps its own `README.md`; add it to the table in the root `README.md`.
