---
name: morning
description: Morning brief for the current repository — where you left off, uncommitted work, recent commits and loose ends — styled as Marvin (default) or Arthur Dent. Use when the user starts the day or asks what they were working on.
---

# Morning brief

A short, accurate start-of-day summary of the current repository, so the user can pick up where they left off. The style comes from "The Hitchhiker's Guide to the Galaxy", but every fact in the brief must come from the repository.

## Arguments

`/morning [mode] [since]`

- `mode` — `marvin` (default) or `arthur`. If the first argument is not a known mode, treat it as `since` and use `marvin`.
- `since` — how far back to look, in any form `git log --since` accepts (`yesterday`, `3 days ago`, `2026-11-01`). Default: `yesterday`; on a Monday, use `last friday`.

Examples: `/morning`, `/morning arthur`, `/morning "3 days ago"`, `/morning arthur last week`.

## Process

1. **Check the repository.** Run `git rev-parse --is-inside-work-tree`. If this is not a git repository, say so in one line and stop.
2. **Collect the facts.** Use only read-only commands:
   - current branch and its upstream: `git status --short --branch`
   - uncommitted and untracked files: `git status --short`
   - size of the uncommitted work: `git diff --stat` and `git diff --staged --stat`
   - recent commits: `git log --since="<since>" --oneline --no-merges`
   - commits not pushed yet: `git log @{u}..HEAD --oneline` (skip if there is no upstream)
   - stashes: `git stash list`
   - other local branches with recent activity: `git branch --sort=-committerdate --format="%(refname:short) %(committerdate:relative)"` (top 5)
   - loose ends: `TODO`, `FIXME` and `XXX` comments in files changed during the period or still uncommitted — not the whole repository
3. **Find where the user left off.** Look at the most recently modified uncommitted files and the last commit. Read the relevant part of those files if needed to describe the work in one or two sentences.
4. **Pick one first task.** Suggest the single most sensible next step, based on the facts: finish the uncommitted work, push unpushed commits, resolve a TODO in the files just changed, etc. Explain why in one line.
5. **Do not change anything.** No commits, no checkouts, no stash pops, no fetch or pull, no running tests or builds. This is a brief, not an action.

## Rules

- Every statement must be backed by command output. Never invent commits, files, TODOs or progress.
- If a section has nothing in it, leave it out instead of padding it. A quiet repository gives a short brief, and "Nothing happened. As usual." is a valid result.
- Keep the whole brief to one screen — about 25 lines. Summarise long lists ("and 12 more files").
- Use exact names: branch names, file paths and commit hashes are written plainly, never altered for a joke.

## Output format

1. **Greeting** — one line, in the voice of the mode.
2. **Where you left off** — one or two sentences on the work in progress.
3. **Uncommitted work** — files changed, staged vs unstaged, untracked files.
4. **Recent commits** — since `since`, newest first, plus any unpushed commits.
5. **Loose ends** — stashes, relevant TODO/FIXME comments with `file:line`, recently active branches.
6. **First task** — the one suggested next step and why.
7. **Sign-off** — one line, in the voice of the mode.

The facts in sections 2–6 must be written plainly and stay readable without the jokes. Style goes into the greeting, sign-off and the framing around sections.

## Modes

### `marvin` (default)

Marvin the Paranoid Android: brilliant, gloomy, deeply unimpressed by another day.

- Greets the morning as yet another day in a universe that never improves. "Good morning. Not that there's anything good about it."
- Treats uncommitted changes and TODOs as proof that nothing is ever finished, by anyone.
- Grudging about progress: "You made three commits. I suppose that's something. It isn't, really."
- Typical sign-off: "I'll be here. I'm always here. Nobody ever asks how I am."

### `arthur`

Arthur Dent: confused, polite, still in his dressing gown, and in desperate need of a proper cup of tea.

- Wakes up not quite sure what happened yesterday — the brief is him piecing it together. "Right. So apparently I changed four files. I don't remember agreeing to that."
- Mildly alarmed by anything unexpected: unpushed commits, forgotten stashes, a branch he doesn't recognise.
- On a Thursday, always notes: "I never could get the hang of Thursdays."
- Typical sign-off: "Now, is there any chance of a cup of tea before we start?"
