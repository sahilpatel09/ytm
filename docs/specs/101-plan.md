# Add `--version` to ytm Implementation Plan

> Execute the task in a fresh session using the test-driven-development skill after plan approval.

**Goal** — Report the version of ytm that `uv run` launches.

**Architecture** — Handle the standalone `--version` flag at the console entry point and look up the installed distribution with `importlib.metadata`. Import the player app after the version check so the version path exits before reaching terminal or player setup.

**Tech stack** — Python 3.11+, `uv`, `unittest`.

**Spec** — [Issue #101](101-spec.md)

## Constraints

- Invoke the app through `uv run`. Use temporary `XDG_STATE_HOME` directories for app checks.
- The version command emits exactly `ytm <version>` and a newline on stdout, leaves stderr empty, and exits with status `0`.
- The normal launch calls the existing terminal probe, runs the app, and cleans up on exit.

## Review focus

- Version differs from the checkout example. Use a distinct mocked metadata value in the regression test.
- Terminal probe or app startup runs on the version path. Guard the probe in the regression test and check the real command with `mpv` absent.
- Extra arguments accompany `--version`. Check that the existing launch path still receives invocations other than standalone `--version`.
- The app raises during startup. Verify that cleanup still runs and the exception propagates.

## Task 1 · Implement and verify the version flag

- **Modify `ytm/__main__.py`** — Keep `main() -> None` as the entry point declared in `pyproject.toml`.
- **Create `tests/test_cli.py`** — Use the repository's existing `unittest` runner for the entry point checks.

- [ ] **Prepare the test environment.** Run `uv sync --locked` and set `XDG_STATE_HOME` to a temporary directory before running tests.
- [ ] **Write `test_version_bypasses_startup`.** Patch `sys.argv` to `['ytm', '--version']`, patch `importlib.metadata.version` to return `8.9.10`, and make `native_cover_widget()` raise `AssertionError` if called. Call `main()` and assert it returns `None`, calls the metadata lookup once with `'ytm'`, and produces stdout `ytm 8.9.10\n` and empty stderr.
- [ ] **Verify the regression fails.** Run `uv run --locked python -m unittest discover -s tests -p test_cli.py -k test_version_bypasses_startup -v`. Expect the probe assertion from the current startup path.
- [ ] **Implement `main() -> None`.** When `sys.argv[1:] == ['--version']`, print `ytm` followed by a space and `importlib.metadata.version('ytm')`, then return. Put the `YtmApp` import below that branch and keep the existing construction and `try`/`finally` cleanup.
- [ ] **Check launch and cleanup.** In `test_launch_runs_and_cleans_up`, patch `ytm.app.YtmApp` and the terminal probe. For `['ytm']` and `['ytm', '--version', 'extra']`, assert the app receives the probe result as `native_cover` and that `run()` precedes `cleanup()`. In `test_launch_cleans_up_when_run_raises`, have `run()` raise `RuntimeError('startup failed')` and assert that `cleanup()` runs once and the same error propagates.
- [ ] **Verify the regression and existing tests pass.** Rerun the focused command, then run `uv run --locked python -m unittest discover -s tests -v`. Record failures and skips along with the test counts.

## Console checks

- [ ] **Verify the real version command.** In a temporary directory, create separate empty `bin` and state directories. Resolve `uv_bin` with `command -v uv` before narrowing `PATH` to the empty `bin` directory. With that `PATH`, run `"$uv_bin" run --locked python -c 'import shutil; assert shutil.which("mpv") is None'` to confirm `mpv` is absent from the child environment. Run `"$uv_bin" run ytm --version` with the same `PATH` and the temporary `XDG_STATE_HOME`. Capture stdout, stderr, and status. Compare stdout with `ytm ` followed by the output of `uv run --locked python -c 'from importlib.metadata import version; print(version("ytm"))'`. Verify empty stderr, status `0`, and that ytm created no state files.
- [ ] **Verify the real launch and exit.** Create a temporary `sitecustomize.py` that mocks `ytm.app.MusicService`, `StreamResolver`, `LyricsService`, and `MpvPlayer`. Start `uv run ytm` in a terminal with temporary `XDG_STATE_HOME` and add the directory containing `sitecustomize.py` to `PYTHONPATH`. Confirm that the UI opens, press `q`, and check for exit status `0` and `ytm/queues.json` in the temporary state directory.
