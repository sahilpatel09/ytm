.PHONY: start clean setup-linux setup-macos

start:
	uv run --locked ytm

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist
	find . \( -type d -name '.*' ! -name . \) -prune -o \
		\( -type d -name __pycache__ -prune -o -type f \( -name '*.pyc' -o -name '*.pyo' \) \) \
		-exec rm -rf {} +

setup-linux:
	@test "$$(uname -s)" = Linux || { printf '%s\n' 'Run make setup-linux on Linux.' >&2; exit 1; }
	@command -v uv >/dev/null 2>&1 || { printf '%s\n' 'Install uv and add it to PATH, then rerun make setup-linux.' >&2; exit 1; }
	@set -e; \
	if ! command -v mpv >/dev/null 2>&1; then \
		command -v apt-get >/dev/null 2>&1 || { printf '%s\n' 'Install mpv with your package manager, then rerun make setup-linux.' >&2; exit 1; }; \
		if [ "$$(id -u)" -eq 0 ]; then \
			apt-get update; \
			apt-get install mpv; \
		else \
			command -v sudo >/dev/null 2>&1 || { printf '%s\n' 'Ask an administrator to install mpv, then rerun make setup-linux.' >&2; exit 1; }; \
			sudo apt-get update; \
			sudo apt-get install mpv; \
		fi; \
	fi
	uv sync --locked

setup-macos:
	@test "$$(uname -s)" = Darwin || { printf '%s\n' 'Run make setup-macos on macOS.' >&2; exit 1; }
	@command -v uv >/dev/null 2>&1 || { printf '%s\n' 'Install uv and add it to PATH, then rerun make setup-macos.' >&2; exit 1; }
	@set -e; \
	if ! command -v mpv >/dev/null 2>&1; then \
		command -v brew >/dev/null 2>&1 || { printf '%s\n' 'Install Homebrew or add mpv to PATH, then rerun make setup-macos.' >&2; exit 1; }; \
		brew install mpv; \
	fi
	uv sync --locked
