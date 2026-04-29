# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`files` parameter** on the `cept` MCP tool and `--file` flag on `cept-cli` — pass a list of paths and their content goes into the packet under `files`, so the model can quote and critique specific lines instead of only describing what the agent did. Caps: 50 KB/file, 256 KB total, 24 files max. Per-file truncation marker on overflow; binary files (NUL detected) are skipped with a note. System prompt updated to ask for `path:line-range` citations when files are present. Closes #2.

## [0.1.0] - 2026-04-27

### Added

- **Locator** — finds the active Claude Code session JSONL by mapping cwd to `~/.claude/projects/<dashed-cwd>/`, with `history.jsonl` fallback.
- **Two-way `cept_id` handshake** — deterministic session verification. Caller passes a short nonce; cept finds the JSONL whose recent `tool_use` input carries it. Polls up to 2.5s for Claude Code's write buffer to flush.
- **Distiller** — parses raw JSONL events into a structured trajectory: user intents, decisions, attempts, files touched, tool failures, loop detection.
- **Redactor** — strips API keys, bearer tokens, JWTs, env-style assignments, basic-auth URLs, emails, home paths before anything leaves the machine.
- **`.ceptkey` hierarchical loader** — drop a dotenv-style file anywhere in your tree; cept walks up from cwd to find it. File overrides process env. Optional `# cept-meta:` comment lines carry provenance (service, key_name, created_at, created_on, created_by, etc.).
- **`cept-keyfile` CLI** — `init` to scaffold with auto-populated provenance, `show` to inspect metadata without leaking values, `where` to print the resolved path.
- **OpenRouter client** — calls `api.openrouter.ai/v1/chat/completions` with mode-specific system prompts (`steer` / `debug` / `research` / `architecture`) and structured JSON response schema.
- **Progress events + adapter framework** — phase-boundary events fan out to pluggable adapters. Built-in: stdout, file, Unix socket, subprocess, macOS notify, noop.
- **Swift HUD** — translucent floating panel showing live cept progress. Auto-builds on first `--emit hud` use; cached at `~/.cache/cept/cept-hud`.
- **MCP server (stdio)** and **`cept-cli`** — both wrap `core.run_cept` so the pipeline is shared.

[Unreleased]: https://github.com/eidos-agi/cept/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/eidos-agi/cept/releases/tag/v0.1.0
