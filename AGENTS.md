# AGENTS.md

Instructions for coding agents working in this repository.

## Project and setup

ytm is a terminal YouTube Music player built with Python 3.11+ and Textual. Use `uv` to
install dependencies and run it from the repository root:

```sh
uv sync
uv run ytm
```

Playback requires the external `mpv` executable on `PATH`; `uv sync` does not install it.
Search, stream resolution, and lyrics lookup use network services.

## Code layout

- `ytm/__main__.py` starts the app and calls cleanup on exit.
- `ytm/app.py` coordinates Textual events, search, playback, queues, and background work.
- `ytm/ui/` holds widgets and screens for search, queues, playback, lyrics, help, and naming.
- `ytm/services/` handles YouTube Music search, stream URL resolution, lyrics lookup, and
  the `mpv` subprocess and JSON IPC connection.
- `ytm/queue.py` owns in-memory track ordering, selection, navigation, and queue serialization.
- `ytm/store.py` manages named queues and persists them as JSON using atomic file replacement.

Keep queue rules in the queue model, persistence in the store, and external integrations in
services. Keep blocking network work off the Textual event loop. Dispatch player callbacks
to the UI thread before changing widgets.

## Non-negotiable

- **Protect unrelated work.** Read the working tree status before editing. Do not overwrite,
  revert, stage, or commit changes outside the task.
- **Stage files by explicit path.** Never use `git add -A`, `git add .`, or `git commit -a`.
  Untracked scratch files must not enter a commit by accident.
- **Open every pull request as a draft.** Pass `--draft`. A human decides when it is ready.
- **Resolve conflicts by hand.** Never use `git checkout --ours <file>` or `--theirs <file>`.
  Those commands discard hunks already merged from the other side. Check the result against
  both parents before staging the file.
- **No AI attribution anywhere.** No generated footer, session link, or co-author trailer.
- **Never pass `--no-verify`.** Do not bypass hooks.
- **Do not post GitHub comments or review replies** unless asked. Address feedback in code
  and report which changes address it to the person you are working with.

## Verification

No automated test suite or lint configuration currently exists in this repository. Choose
checks that exercise the change; do not claim that an unconfigured tool or CI job is required.

- **Protect saved queues.** The default file is `$XDG_STATE_HOME/ytm/queues.json`, falling back
  to `~/.local/state/ytm/queues.json`. Set `XDG_STATE_HOME` to a temporary directory before
  launching the app for testing. For store checks, pass a temporary path to `QueueStore`.
  Never test against the user's saved queues.
- Mock search, stream resolution, lyrics requests, and player IPC where appropriate so checks
  do not depend on live services or start unwanted playback. Identify live checks separately.
- For queue or persistence changes, check empty queues, selection and removal boundaries,
  switching and renaming queues, save/load round trips, and missing or malformed state.
  Preserve existing saved data when changing its format.
- For player or lifecycle changes, check startup failure and exit cleanup. Verify that the
  app's `mpv` process stops and its IPC socket is removed. Clean up only resources you started.
- For UI or background work changes, check keyboard navigation and responsiveness during slow
  or failed requests. Check rapid searches and track changes for stale results or callbacks.
- A regression test must fail before the fix and pass after it. Run it both ways and report
  the results. Check skip counts when a runner reports success.
- Report commands actually run, observed results, and anything left unchecked. Expected output
  is not evidence. Verify each branch before claiming that it is affected or fixed.

Before committing or pushing, review the full diff for unrelated files and accidental state
changes. After pushing, compare the pushed diff with the PR description.

## Fix the class, not the instance

Look for the same defect in related code paths before stopping. Check accessors that report
the same property, callers that depend on a changed return value, and other inputs accepted
by the same pattern. Share a predicate when several paths must make the same decision.

Search for callers and external uses before deleting code that appears unused. State what
you searched and what you did not check. In a bug-fix PR, report related instances found,
including when the search found none.

## Writing and review

Use plain instructions and concrete reasons. A code comment says what the code does; a commit
message explains why it changed. Do not leave comments that only describe a past mistake.

Keep PR titles and descriptions concise. Lead with the product behavior and why the change
matters. Explain decisions and verification the diff cannot show; do not narrate the diff or
repeat the issue. Put lengthy test output or search details in a `<details>` block with a
descriptive `<summary>` when they are needed for reference.

State findings as observations, with their evidence and limits. Say which checks passed and
where you searched. Do not turn an unverified assumption into a fact for the next reviewer.
