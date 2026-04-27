# cept — proprioception for coding agents

> Short for *proprioception*. Cept is the agent's mirror.

Coding agents loop. They polish corners while the center is wrong. They retry the same fix three times instead of asking what they're missing. cept is a meta-tool that gives an agent a structured way to step back, look at its own recent trajectory, and request outside-in steering — through OpenRouter, defaulting to a model with web search baked in.

## What it does

When invoked (explicitly via "use cept" or by an agent that has reached a decision point):

1. **Locate** the active Claude Code session JSONL under `~/.claude/projects/<dashed-cwd>/`.
2. **Slice** the last N minutes of events (default 20).
3. **Distill** raw events into a steering packet — decisions, attempts, errors, files touched, loops.
4. **Collect** repo state — branch, dirty files, diff stat.
5. **Redact** API keys, bearer tokens, env values, PEM blocks, emails, home paths.
6. **Ask** an OpenRouter model (default `perplexity/sonar-reasoning` — reasoning + live web search) with a mode-specific prompt.
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

## Per-tree keys with `.ceptkey`

Drop a `.ceptkey` (preferred) or `ceptkey` file anywhere in your directory tree. Cept walks up from the working directory until it finds one, then loads it as dotenv. **The file overrides process env** — so if you have `OPENROUTER_API_KEY` exported in your shell but a `.ceptkey` in the project tree, the project key wins. That's the point: per-folder cost attribution and project-specific model defaults.

```ini
# ~/projects/clientA/.ceptkey — billed to client A's account
OPENROUTER_API_KEY=sk-or-clientA...
CEPT_DEFAULT_MODEL=anthropic/claude-sonnet-4-5:online
CEPT_LOOKBACK_MINUTES=10
```

```ini
# ~/projects/personal/.ceptkey — your own account, cheaper model on personal repos
OPENROUTER_API_KEY=sk-or-personal...
CEPT_DEFAULT_MODEL=perplexity/sonar
```

Walk stops at the first match. Capped at `$HOME` when cwd is under home; otherwise capped at filesystem root. Add `.ceptkey` and `ceptkey` to your global gitignore so you never commit one by accident.

Recognized keys:

| Key | Effect |
|-----|--------|
| `OPENROUTER_API_KEY` | OpenRouter credential. |
| `OPENROUTER_REFERER` | Optional `HTTP-Referer` header for OpenRouter app rankings. |
| `OPENROUTER_TITLE` | Optional `X-Title` header. |
| `CEPT_DEFAULT_MODEL` | Per-tree default model (e.g. `openai/gpt-5:online`). |
| `CEPT_LOOKBACK_MINUTES` | Per-tree default lookback window. |

> ⚠️ Trust model: cept loads any `.ceptkey` it finds while walking up. If you `cd` into a hostile repo with a malicious `.ceptkey`, your packets would route to that endpoint. Blast radius is the redacted packet (no real key exfil), but be aware. v1 doesn't do `direnv allow`-style ceremony — just don't `cd` into untrusted trees.

## Model selection (via OpenRouter)

cept uses [OpenRouter](https://openrouter.ai) as the gateway, so you can swap models without changing the client.

| Model id | Why |
|----------|-----|
| `perplexity/sonar-reasoning` *(default)* | Reasoning + live web search. Best for `steer`/`debug`. |
| `perplexity/sonar-pro` | Fast web search, no reasoning trace. |
| `anthropic/claude-sonnet-4-5:online` | Claude with web search via OpenRouter (`:online` suffix). |
| `openai/gpt-5:online` | GPT with web search. |

Append `:online` to any compatible model name to force web search.

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
        "OPENROUTER_API_KEY": "sk-or-...",
        "OPENROUTER_TITLE": "cept",
        "OPENROUTER_REFERER": "https://github.com/eidos-agi/cept"
      }
    }
  }
}
```

The `OPENROUTER_TITLE` and `OPENROUTER_REFERER` env vars are optional — they show up on OpenRouter's app rankings.

Then in a Claude Code session: "use cept — I'm stuck on the OAuth callback."

## CLI (dry-run / debugging)

```bash
# Distill the current session and print the redacted packet without calling OpenRouter:
cept-cli --goal "fix oauth callback" --dry-run

# Send for real:
OPENROUTER_API_KEY=sk-or-... cept-cli --goal "fix oauth callback" --mode debug

# Try a different model:
OPENROUTER_API_KEY=sk-or-... cept-cli --goal "..." --model "anthropic/claude-sonnet-4-5:online"
```

## Design rules

- **Redact before send.** Local secrets must never leave the machine.
- **Compress aggressively.** The model gets signal, not raw logs.
- **Structured output.** The agent consumes JSON fields, not prose.
- **Bounded.** Hard caps on transcript size, lookback, event count.
- **Selective.** Cept is an escalation tool, not a default tool.

## Layers

```
┌─────────────────────────────────────────┐
│ Layer 2 — external steering (OpenRouter)│
└─────────────────────────────────────────┘
                  ▲
┌─────────────────────────────────────────┐
│ Layer 1 — local introspection           │
│  locator → distiller → redactor → packet│
└─────────────────────────────────────────┘
```

Layer 1 is independently useful and testable. Layer 2 is the consultation.
