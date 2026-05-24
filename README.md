# Cept — proprioception for coding agents

> Short for *proprioception*. Cept is the agent's mirror. The package,
> executable, MCP tool, and Eidos slug remain lowercase `cept` for compatibility.

Coding agents loop. They polish corners while the center is wrong. They retry the same fix three times instead of asking what they're missing. Cept is a meta-tool that gives an agent a structured way to step back, look at its own recent trajectory, and request outside-in steering through OpenRouter, defaulting to a grounded Perplexity model.

## What it does

When invoked (explicitly via "use cept" or by an agent that has reached a decision point):

1. **Headline** the ask in 3-4 words — required, surfaced in the floating HUD callout so the human watching can see what's being asked at a glance.
2. **Locate** the active Claude Code session JSONL under `~/.claude/projects/<dashed-cwd>/`.
3. **Slice** the last N minutes of events (default 20).
4. **Distill** raw events into a steering packet — decisions, attempts, errors, files touched, loops.
5. **Collect** repo state — branch, dirty files, diff stat.
6. **Redact** API keys, bearer tokens, env values, PEM blocks, emails, home paths.
7. **Ask** an OpenRouter model (default `perplexity/sonar-pro` — Perplexity grounding through OpenRouter) with a mode-specific prompt.
8. **Return** a structured response: hypotheses, recommended next step, facts to verify, confidence — plus `refused: bool` if the model declined to engage.

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

For local plugin-style discovery, Cept follows the same source-path pattern as
Conduit:

```text
/Users/dshanklinbv/plugins/cept -> /Users/dshanklinbv/repos-eidos-agi/cept
```

The symlink is an operator convenience. The source repo remains the canonical
home.

## Registry And Storage

Cept keeps a small source-owned registry like Conduit:

```text
registry/
  storage.toml
  cept-proofs/
```

Use it to inspect where Cept stores source, plugin shims, installed Eidos
runtime state, event logs, proof records, and keyfiles:

```bash
scripts/cept-registry registry --json
scripts/cept-registry doctor
scripts/cept-registry proof --json
```

Runtime event logs still go to `~/.cept/status.jsonl` when `CEPT_EMIT` includes
`file:~/.cept/status.jsonl`. Eidos loop evidence belongs under the active Eidos
plugin run or docket evidence directory.

## Per-tree keys with `.ceptkey`

For the full guide, see [docs/CEPTKEY.md](docs/CEPTKEY.md).

Drop a `.ceptkey` (preferred) or `ceptkey` file anywhere in your directory tree. Cept walks up from the working directory until it finds one, then loads it as dotenv. **The file overrides process env** — so if you have `OPENROUTER_API_KEY` exported in your shell but a `.ceptkey` in the project tree, the project key wins. That's the point: per-folder cost attribution and project-specific model defaults.

Easiest way is to use the bundled scaffold:

```bash
cept-keyfile init \
  --service openrouter \
  --name cept-djs-01 \
  --key sk-or-... \
  --provider openrouter \
  --model perplexity/sonar-pro \
  --scope "~/repos-eidos-agi/" \
  --notes "Eidos AGI shared key" \
  --path ~/repos-eidos-agi/.ceptkey
```

That writes a 0600-permissioned file with auto-populated provenance (`created_at`, `created_on`, `created_by`, `created_os`) plus the values you passed. Inspect at any time:

```bash
cept-keyfile show          # nearest keyfile, metadata only — no values
cept-keyfile where         # just the path
```

By hand it looks like:

```ini
# cept-meta:service=openrouter
# cept-meta:key_name=cept-djs-01
# cept-meta:created_at=2026-04-27T18:16:44+00:00
# cept-meta:created_on=daniels-mbp.local
# cept-meta:created_by=dev@example.com
# cept-meta:created_os=Darwin 24.3.0 (arm64)
# cept-meta:scope=~/repos-eidos-agi/
# cept-meta:notes=Eidos AGI shared key

OPENROUTER_API_KEY=sk-or-clientA...
CEPT_PROVIDER=openrouter
CEPT_DEFAULT_MODEL=perplexity/sonar-pro
CEPT_LOOKBACK_MINUTES=10
```

`# cept-meta:` lines are pure comments to anything that isn't cept (including `source ./.ceptkey` in your shell), but cept captures them as a metadata block surfaced in the result. Useful for auditing which key is which without leaking values.

Walk stops at the first match. Capped at `$HOME` when cwd is under home; otherwise capped at filesystem root. Add `.ceptkey` and `ceptkey` to your global gitignore so you never commit one by accident.

Recognized keys:

| Key | Effect |
|-----|--------|
| `CEPT_PROVIDER` | Provider selector. `auto` and `openrouter` both use OpenRouter in this build. |
| `OPENROUTER_API_KEY` | OpenRouter credential. |
| `OPENROUTER_REFERER` | Optional `HTTP-Referer` header for OpenRouter app rankings. |
| `OPENROUTER_TITLE` | Optional `X-Title` header. |
| `CEPT_DEFAULT_MODEL` | Per-tree default model (e.g. `openai/gpt-5:online`). |
| `CEPT_LOOKBACK_MINUTES` | Per-tree default lookback window. |

> ⚠️ Trust model: cept loads any `.ceptkey` it finds while walking up. If you `cd` into a hostile repo with a malicious `.ceptkey`, your packets would route to that endpoint. Blast radius is the redacted packet (no real key exfil), but be aware. v1 doesn't do `direnv allow`-style ceremony — just don't `cd` into untrusted trees.

## Model selection (via OpenRouter)

cept uses [OpenRouter](https://openrouter.ai) as the gateway. Grounded Perplexity answers come from OpenRouter's Perplexity model slugs, not from a native `PERPLEXITY_API_KEY` path.

| Model id | Why |
|----------|-----|
| `perplexity/sonar-pro` *(default)* | Fast grounded Perplexity answers through OpenRouter. |
| `perplexity/sonar-reasoning-pro` | Reasoning-capable Perplexity model when you want deeper synthesis. |
| `anthropic/claude-sonnet-4-5:online` | Claude with web search via OpenRouter (`:online` suffix). |
| `openai/gpt-5:online` | GPT with web search. |

Append `:online` to compatible non-Perplexity model names to request OpenRouter web search. Perplexity model slugs are already the preferred grounding path for cept.

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

## Codex / Claude plugin

Cept ships a source-owned plugin wrapper for Codex and Claude Code:

- `.codex-plugin/plugin.json` describes the Codex plugin card and points at the skill and MCP config.
- `.claude-plugin/plugin.json` describes the Claude plugin.
- `.mcp.json` starts the bounded MCP server from source with `uv run --directory ... cept`.
- `skills/use-cept/SKILL.md` teaches agents when to call cept and how to respect the dry-run and secret boundaries.

The plugin is intentionally thin. It points agents to the CLI/MCP surface; the CLI owns transcript discovery, redaction, OpenRouter calls, progress events, and HUD integration. The registry documents source/runtime storage and records local proof checks.

## Agent transcript adapters

cept is adapter-based at the transcript boundary. The default adapter is
`claude-code`, which keeps the original behavior of finding
`~/.claude/projects/<dashed-cwd>/<session-id>.jsonl`. Other agents can use cept
today by writing a JSONL transcript and passing `--transcript`:

```bash
cept-cli \
  --goal "debug auth callback" \
  --headline "debug auth callback" \
  --transcript /tmp/agent-session.jsonl \
  --dry-run
```

Minimal agent-neutral rows look like this:

```jsonl
{"timestamp":"2026-05-23T12:00:00+00:00","role":"user","text":"please fix the failing auth test","cwd":"/repo"}
{"timestamp":"2026-05-23T12:01:00+00:00","type":"tool_call","tool":"shell","input":{"command":"pytest tests/test_auth.py"}}
{"timestamp":"2026-05-23T12:02:00+00:00","type":"tool_result","is_error":true,"content":"AssertionError: callback missing state"}
```

The normalized event vocabulary is intentionally small: user/assistant messages,
tool calls, and tool results. New agent adapters should normalize into that
shape early so the distiller, redactor, provider clients, and reducers do not
need to know which agent produced the transcript.

For dogfooding, use:

```bash
cept-cli --self-assess --transcript /tmp/agent-session.jsonl --dry-run
```

`--self-assess` switches to architecture mode, supplies a cept-specific goal and
headline, and includes cept's core source files in the packet.

## CLI (dry-run / debugging)

```bash
# Distill the current session and print the redacted packet without calling OpenRouter:
cept-cli --goal "fix oauth callback" --headline "fix oauth callback" --dry-run

# Send for real:
OPENROUTER_API_KEY=sk-or-... cept-cli --goal "fix oauth callback" \
  --headline "fix oauth callback" --mode debug

# Be explicit about the provider:
OPENROUTER_API_KEY=sk-or-... cept-cli --provider openrouter \
  --goal "fix oauth callback" --headline "fix oauth callback"

# Include source files for content-shape critique (not just trajectory):
OPENROUTER_API_KEY=sk-or-... cept-cli --goal "audit this readme" \
  --headline "audit research README" \
  --file research-findings/README.md --file checklist.md --mode debug

# Try a different model:
OPENROUTER_API_KEY=sk-or-... cept-cli --goal "..." --headline "..." \
  --model "anthropic/claude-sonnet-4-5:online"
```

## Headline (required)

Every cept call requires a `headline` — a 3-4 word newspaper-style summary of what's being asked. It surfaces in the floating HUD popup (so the human watching sees what's happening at a glance), in `packet.meta.headline` (so the model sees the agent's own self-summary alongside the longer goal), and in the return value (so the calling agent can confirm what got logged).

- Soft cap: 4 words (warning emitted at 5)
- Hard cap: 6 words (truncated with `…` at 7+)
- Empty rejected: if the calling agent can't compress the ask to a phrase, it's not clear on what it needs — and that's exactly the moment cept was made for. The pause to write the headline IS part of cept's value.

Examples: `"audit research README"`, `"debug oauth callback loop"`, `"compare Postgres vs SQLite"`, `"fix flaky test_distiller"`.

## Including source files in the packet

By default, cept's packet describes *what the agent did* — tool calls, decisions, errors. Trajectory critique catches workflow problems but misses content problems ("this README quotes a statute that's actually from a summary page", "this function ignores its `null` branch"). Pass file paths to include their content in the packet:

- **MCP**: `files=["README.md", "src/handler.py"]`
- **CLI**: repeat `--file PATH`

Each file is capped at 50 KB; total at 256 KB across all files; max 24 files per call. Truncated files keep the head and append a marker. Binary files (NUL byte detected) are skipped with a note. Paths can be absolute or relative to cwd. Redaction still applies to the file content. When files are present, the system prompt asks the model to cite issues as `path:line-range` so you can navigate directly to them, and frames the request as owner-self-review so adversarial language ("audit", "red-team") doesn't trip third-party-attack refusals.

## Refusal detection

When a model declines to engage with the packet (rather than recommending a substantive backtrack), the response shape is otherwise identical to real guidance — same `decision`, same `confidence`, same `hypotheses` keys. cept detects refusal-shaped language in the response and sets two extra top-level fields:

```json
{
  "refused": true,
  "refusal_reason": "recommended_next_step opens with refusal: 'Decline the request clearly'",
  "decision": "backtrack",
  "confidence": 0.88,
  ...
}
```

Switch on `refused` in the calling agent: if true, the audit didn't happen — try a different model (`model="anthropic/claude-sonnet-4-5:online"`) or reframe the goal. The default `perplexity/sonar-pro` over-refuses on owner-self-review of confidential corporate text; the layer-2 prompt fix above kills the most common false positive, and refusal detection catches the rest.

## Examples

- [01 — catching a guardrail violation before it shipped](examples/01-slack-eidos-personality.md): agent was about to write a persona before deploying the bot. Cept caught that this contradicted the project's own ship-simplest guardrails and surfaced two technical risks (socket-mode on Railway, non-swappable SYSTEM_PROMPT) the agent had missed.

## Design rules

- **Redact before send.** Local secrets must never leave the machine.
- **Compress aggressively.** The model gets signal, not raw logs.
- **Structured output.** The agent consumes JSON fields, not prose.
- **Bounded.** Hard caps on transcript size, lookback, event count.
- **Selective.** Cept is an escalation tool, not a default tool.

## Live progress (`--emit`) and the floating HUD

cept emits structured progress events at every phase boundary. Adapters consume them; you choose what surface you want.

```bash
# default: text events on stderr (stdout stays clean for the JSON result)
cept-cli --goal "..." --dry-run

# JSONL on stderr (machine-readable)
cept-cli --goal "..." --emit jsonl:stderr

# append to a log file
cept-cli --goal "..." --emit file:~/.cept/status.jsonl

# floating HUD panel (see below)
cept-cli --goal "..." --emit hud

# multiple at once: HUD + log
cept-cli --goal "..." --emit hud --emit file:~/.cept/status.jsonl

# silent
cept-cli --goal "..." --quiet
```

For the MCP server (where stdout is the JSON-RPC channel and must stay clean), set `CEPT_EMIT` in the server's env:

```jsonc
"env": {
  "OPENROUTER_API_KEY": "sk-or-...",
  "CEPT_EMIT": "hud,file:~/.cept/status.jsonl"
}
```

### Adapter spec syntax

| Spec | What |
|------|------|
| `stdout` / `stderr` | Human-readable text |
| `jsonl:-` / `jsonl:stderr` | JSONL to stdout/stderr |
| `jsonl:PATH` / `file:PATH` | Append JSONL to file |
| `socket:PATH` | JSONL to a Unix domain socket (no-op if no listener) |
| `subprocess:CMD` | Spawn CMD, write JSONL to its stdin |
| `hud` | Spawn the bundled Swift HUD (`$CEPT_HUD_CMD` or `cept-hud --once` in `$PATH`) |
| `notify` | macOS notification banners (skips noisy phases) |
| `noop` | Drop everything |

### Event schema (the stable contract)

```json
{
  "run_id": "abc123",
  "seq": 7,
  "ts": "2026-04-27T20:00:00.000Z",
  "phase": "asking_model",
  "level": "info",
  "msg": "asking perplexity/sonar-pro",
  "data": {"model": "perplexity/sonar-pro", "provider": "openrouter"}
}
```

Anyone can write a different consumer (dashboard, Slack bridge, log forwarder) by reading JSONL with this schema.

### The HUD just works

`--emit hud` auto-builds the Swift binary on first use and caches it at `~/.cache/cept/cept-hud` (or `$XDG_CACHE_HOME/cept/cept-hud`). First call costs ~5-10 seconds; subsequent calls are instant. You don't need to know Swift exists.

```bash
# First time: cept builds cept-hud, then runs.
cept-cli --goal "..." --emit hud

# Every time after: cache hit, no build, panel pops up.
```

Resolution order:

1. `$CEPT_HUD_CMD` — full command override (e.g. for testing builds)
2. `$CEPT_HUD_BIN` — path to a binary you already have
3. `cept-hud` on `$PATH`
4. `~/.cache/cept/cept-hud` — auto-built and cached
5. Build from `hud/Package.swift` next to the cept package — first-call cost

If none work (no Swift toolchain, source missing) `--emit hud` falls back to noop with a clear stderr message.

Want to pre-build (e.g. in CI) or refresh the cache?

```bash
cept-hud-install            # build if missing
cept-hud-install --force    # rebuild
cept-hud-install --path     # print resolved binary path
```

The HUD itself is a translucent `NSPanel` (Swift 5, macOS 13+, top-right of the active screen, click-through, no Dock icon). Source lives in `hud/`.

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
                  │
                  ▼ (events fan out)
┌─────────────────────────────────────────┐
│ Adapters — stdout / file / socket /     │
│ HUD / notify / noop                     │
└─────────────────────────────────────────┘
```

Layer 1 is independently useful and testable. Layer 2 is the consultation. Adapters are the surface — swap them without touching the pipeline.
