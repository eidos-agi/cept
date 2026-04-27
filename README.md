# cept — proprioception for coding agents

> Short for *proprioception*. Cept is the agent's mirror.

Coding agents loop. They polish corners while the center is wrong. They retry the same fix three times instead of asking what they're missing. cept is a meta-tool that gives an agent a structured way to step back, look at its own recent trajectory, and request outside-in steering — backed by Perplexity's web-scale search.

## What it does

When invoked (explicitly via "use cept" or by an agent that has reached a decision point):

1. **Locate** the active Claude Code session JSONL under `~/.claude/projects/<dashed-cwd>/`.
2. **Slice** the last N minutes of events (default 20).
3. **Distill** raw events into a steering packet — decisions, attempts, errors, files touched, loops.
4. **Collect** repo state — branch, dirty files, diff stat.
5. **Redact** API keys, bearer tokens, env values, PEM blocks, emails, home paths.
6. **Ask** Perplexity (`sonar-reasoning` by default) for ranked guidance with a mode-specific prompt.
7. **Return** a structured response: hypotheses, recommended next step, facts to verify, confidence.

## Modes

| Mode | Use when |
|------|----------|
| `steer` | Default. Broad outside-in guidance, blind spots, next step. |
| `debug` | Rank likely causes from evidence and errors. |
| `research` | Find external facts, docs, version gotchas. |
| `architecture` | Compare design alternatives and tradeoffs. |

## Install

```bash
cd cept
uv sync
```

## MCP server

Register with Claude Code:

```jsonc
// ~/.claude/claude_desktop_config.json (or equivalent MCP host config)
{
  "mcpServers": {
    "cept": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/cept", "cept"],
      "env": {
        "PERPLEXITY_API_KEY": "pplx-..."
      }
    }
  }
}
```

Then in a Claude Code session: "use cept — I'm stuck on the OAuth callback."

## CLI (dry-run / debugging)

```bash
# Distill the current session and print the redacted packet without calling Perplexity:
cept-cli --goal "fix oauth callback" --dry-run

# Send for real:
PERPLEXITY_API_KEY=pplx-... cept-cli --goal "fix oauth callback" --mode debug
```

## Design rules

- **Redact before send.** Local secrets must never leave the machine.
- **Compress aggressively.** Perplexity gets signal, not raw logs.
- **Structured output.** The agent consumes JSON fields, not prose.
- **Bounded.** Hard caps on transcript size, lookback, event count.
- **Selective.** Cept is an escalation tool, not a default tool.

## Layers

```
┌─────────────────────────────────────────┐
│ Layer 2 — external steering (Perplexity)│
└─────────────────────────────────────────┘
                  ▲
┌─────────────────────────────────────────┐
│ Layer 1 — local introspection           │
│  locator → distiller → redactor → packet│
└─────────────────────────────────────────┘
```

Layer 1 is independently useful and testable. Layer 2 is the consultation.
