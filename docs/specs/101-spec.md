# Add `--version` to ytm

GitHub issue #101

Developers can check which version of ytm their `uv` environment is running without opening the player.

```console
$ uv run ytm --version
ytm 0.1.0
```

## Command behavior

- The standalone `--version` flag prints exactly one newline-terminated `ytm <version>` line to stdout. ytm emits no stderr output and exits with status `0`.
- The version comes from the `ytm` package metadata in the environment selected by `uv`. The example uses the version declared in the current checkout.
- The version command exits before probing the terminal, opening the UI, accessing saved queues, making network requests, or starting `mpv`.
- Running `uv run ytm` opens the player and performs normal cleanup on exit.

## Verification

- In a synced `uv` environment, run `uv run ytm --version` with `mpv` unavailable and a temporary `XDG_STATE_HOME`. Check stdout, stderr, exit status, and the version against the package metadata.
- Check normal startup and cleanup through `uv run ytm` with temporary queue state and mocked external services.
