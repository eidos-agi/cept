---
name: use-cept
description: Use when the user asks to use cept, asks for outside-in steering, wants a Claude Code session reviewed, is stuck or looping, needs debugging triage, or wants architecture/research guidance from the recent agent trajectory. This skill tells Codex to call the local cept CLI or MCP tool first and treat cept output as evidence to reconcile.
---

# Use cept

cept is proprioception for coding agents: a way for the AI to inspect its own
recent work, uncertainty, and next move before continuing. Use it when the agent
needs a deliberate outside-in review of its recent trajectory.

cept is adapter-based at the transcript boundary. Claude Code is the default
adapter, but any agent can use cept by writing agent-neutral JSONL and passing
`--transcript`.

cept's grounded default is `perplexity/sonar-pro` through OpenRouter. Use
`OPENROUTER_API_KEY`; this plugin does not require or read `PERPLEXITY_API_KEY`.
For keyfile setup and troubleshooting, read `docs/CEPTKEY.md` in the cept repo.

## Primary Rule

Run the smallest relevant `cept` command first, then reconcile the result with repo evidence before acting.

Useful entrypoints:

```bash
cept-cli --help
cept-keyfile show
cept-keyfile where
cept-cli --goal "<goal>" --headline "<3-4 word headline>" --dry-run
cept-cli --provider openrouter --goal "<goal>" --headline "<3-4 word headline>"
cept-cli --goal "<goal>" --headline "<3-4 word headline>" --mode debug
cept-cli --goal "<goal>" --headline "<3-4 word headline>" --mode research
cept-cli --goal "<goal>" --headline "<3-4 word headline>" --mode architecture
cept-cli --goal "<goal>" --headline "<3-4 word headline>" --transcript /tmp/agent.jsonl --dry-run
cept-cli --self-assess --transcript /tmp/agent.jsonl --dry-run
cept-hud-install
```

If the MCP tool is available, call the `cept` tool with a fresh session-verification nonce.

## When To Use cept

Use cept when:

- The agent is stuck, looping, or retrying the same fix.
- A bug needs ranked likely causes from the recent transcript.
- A design choice needs outside architecture review.
- Current work depends on external facts or version gotchas.
- The user explicitly says "use cept."

## Modes

- `steer`: broad blind spots and next-step guidance.
- `debug`: rank likely causes from errors and evidence.
- `research`: check external facts, docs, and version-specific gotchas.
- `architecture`: compare design alternatives and tradeoffs.

## Secret Boundary

cept redacts before it sends, but it still packages recent transcript and optional file content. Use `--dry-run` first when the packet may contain sensitive material. Do not include secrets, private keys, raw tokens, protected personal data, or unrelated files.

## Source-Of-Truth Rules

- Treat cept output as evidence, not a verdict.
- Verify any concrete claim against local repo state or primary docs before shipping.
- Keep the headline short. If you cannot summarize the ask in 3-4 words, clarify the goal first.
- Prefer `--file` only for files that are directly relevant to the requested critique.
- For non-Claude agents, normalize transcript rows into user/assistant messages,
  tool calls, and tool results before invoking cept.

## Plugin Boundary

This plugin is a thin signpost to the `cept` CLI/MCP server. The CLI owns transcript discovery, redaction, OpenRouter calls, progress events, and HUD integration.
