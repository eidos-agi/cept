# Contributing to cept

Thanks for your interest in contributing.

## Quick start

```bash
git clone https://github.com/eidos-agi/cept.git
cd cept
pip install -e ".[dev]"
```

Or with uv:

```bash
uv sync --extra dev
```

## Development

We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
ruff check .
ruff format .
```

Run tests:

```bash
pytest
```

The Swift HUD lives in `hud/` and builds with SwiftPM:

```bash
cd hud && swift build -c release
```

It's auto-built on first `--emit hud` use, so you only need to invoke this if you're actively working on it.

## For agent developers

If you're building tools that AI agents will use, pay special attention to:

1. **Tool descriptions** — Every `@tool` decorator must explain *when* to use it, not just *what* it does. cept's tool description tells Claude to pass a fresh `cept_id` per call — that's the kind of guidance to write.
2. **Parameter descriptions** — Every parameter needs a description. Agents don't have UI tooltips.
3. **Error messages** — When something fails, the message should tell the agent what to do next. cept's "No JSONL contains cept_id … Either the id was wrong or the calling session has not yet flushed" is the standard.
4. **Typed everything** — Type hints on all public functions.

## Pull requests

- Keep PRs focused — one feature or fix per PR
- Include tests for new functionality
- Update CHANGELOG.md under `[Unreleased]`
- Ensure `ruff check .` and `pytest` pass

## Reporting issues

Open an issue with:

1. What you were trying to do
2. What happened instead
3. Steps to reproduce

For security issues, see [SECURITY.md](SECURITY.md) — please do not file public issues.
