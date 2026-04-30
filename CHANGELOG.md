# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.1] - 2026-04-30

### Fixed

- **Wheel now bundles the Swift HUD source** so `uvx --from cept` (and any PyPI install) can auto-build the floating popup on first `--emit hud` use. Previously the wheel was Python-only — `find_source_dir()` couldn't locate `hud/Package.swift`, `build()` failed silently, and the HUD adapter no-op'd. Marketplace plugin users got no popup. Bundled at `cept/_hud_source/` via hatchling `force-include`; resolver checks the bundled path first, then falls back to walking up for editable / source-checkout layouts.

## [0.4.0] - 2026-04-29

### Changed (BREAKING)

- **`headline` is now a required parameter** on the `cept` MCP tool and `--headline` is required on `cept-cli`. The calling agent must compress its ask to 3-4 words (soft cap 4, hard cap 6 — overflow is truncated, not rejected). The headline:
  - Fires as a `request.headline` event at `seq=1`, before any other phase, so the floating HUD popup shows it the moment the call lands and keeps it visible for the rest of the run.
  - Is embedded in `packet.meta.headline` so the model sees the agent's own self-summary alongside the longer goal — useful signal for catching when goal and headline drift apart (a sign of confused intent).
  - Is returned at the top of the result so the calling agent can confirm what got logged.
  Discipline-as-schema: if the calling agent can't compress the ask to 3-4 words, it's not clear on what it needs — exactly the moment cept was made for. The pause to write the headline IS part of cept's value. Existing call sites must add `headline=`; the validation error message names the contract.
- **HUD callout** redesigned: prominent headline header (15 pt semibold) above the existing phase row (now 11 pt monospace, secondary). Panel height grew from 70 → 96 px to accommodate.

## [0.3.0] - 2026-04-29

### Added

- **Refusal detection** — when the underlying model declines to engage with the packet (rather than recommending a substantive backtrack), cept now sets `refused: true` and `refusal_reason: "..."` on the response so the calling agent can switch on the difference. Previously a refusal looked structurally identical to substantive guidance — same `decision`, same `confidence`, same `hypotheses` shape — and callers acted on the refusal as if it were a real recommendation. Heuristics scan `recommended_next_step`, `summary`, and `hypotheses[].title/why` for refusal-shaped language. Closes #4.
- **Owner-positive framing in the system prompt when `files` is attached** — when `packet.files` is non-empty, the user-payload preamble now states explicitly that the calling agent is the document owner asking for help hardening their own deliverable, so adversarial language ("audit", "red-team", "find the holes") doesn't get read as third-party attack prep. This kills the most common false-positive refusal seen in practice on `perplexity/sonar-pro`.

## [0.2.0] - 2026-04-29

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

[Unreleased]: https://github.com/eidos-agi/cept/compare/v0.4.1...HEAD
[0.4.1]: https://github.com/eidos-agi/cept/releases/tag/v0.4.1
[0.4.0]: https://github.com/eidos-agi/cept/releases/tag/v0.4.0
[0.3.0]: https://github.com/eidos-agi/cept/releases/tag/v0.3.0
[0.2.0]: https://github.com/eidos-agi/cept/releases/tag/v0.2.0
[0.1.0]: https://github.com/eidos-agi/cept/releases/tag/v0.1.0
