# cept Agent Wakeup

Read this before changing cept.

## What cept is

cept is a proprioception tool for coding agents. It slices the recent Claude Code transcript, distills trajectory, attaches repo state, redacts secrets, and asks an outside model for structured steering.

## Source of truth

- User-facing behavior: `README.md`
- CLI and MCP entrypoints: `pyproject.toml`
- MCP tool surface: `src/cept/server.py`
- Core run loop: `src/cept/core.py`
- Redaction rules: `src/cept/redactor.py`
- Keyfile behavior: `src/cept/keyfile.py`
- Plugin wrapper: `.codex-plugin/plugin.json`, `.claude-plugin/plugin.json`, `.mcp.json`, `skills/use-cept/SKILL.md`

## Boundaries

- Do not commit `.ceptkey`, `ceptkey`, `.env`, tokens, transcript dumps, or packet payloads.
- Keep the plugin CLI-first. The plugin and MCP layer are signposts; the CLI owns progressive reveal and behavior.
- Treat cept guidance as evidence to reconcile, not a command to follow blindly.
- Prefer dry-runs when packet sensitivity is uncertain.

## Verification

Run the smallest relevant checks before claiming done:

```bash
uv run pytest
python3 /Users/dshanklinbv/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
cd /Users/dshanklinbv/repos-eidos-agi/eidos-marketplace && python3 tools/test_plugins.py cept
```
