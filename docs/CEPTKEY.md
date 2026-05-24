# ceptkey guide

`.ceptkey` is cept's per-tree configuration file. It lets one checkout, client
folder, or repo family choose its own OpenRouter key, model, lookback window,
and metadata without relying on whatever happens to be exported in the shell.

## Quick start

Create a keyfile with the helper:

```bash
cept-keyfile init \
  --service openrouter \
  --name cept-eidos-01 \
  --key sk-or-... \
  --provider openrouter \
  --model perplexity/sonar-pro \
  --lookback 20 \
  --scope "~/repos-eidos-agi/" \
  --notes "Eidos AGI shared cept key" \
  --path ~/repos-eidos-agi/.ceptkey
```

Inspect the nearest keyfile without printing secret values:

```bash
cept-keyfile show
cept-keyfile show --json
cept-keyfile where
```

Then run cept from any descendant folder:

```bash
cept-cli --goal "debug auth callback" --headline "debug auth callback" --mode debug
```

## Lookup rules

cept looks for `.ceptkey` first, then `ceptkey`.

Lookup starts at the current working directory and walks upward:

1. If the current directory is under `$HOME`, cept stops at `$HOME`.
2. If the current directory is outside `$HOME`, cept stops at filesystem root.
3. The first matching file wins.
4. Values in the file override existing process environment variables.

That last point is intentional. A project-level key should beat a global shell
key so costs, model defaults, and provider behavior follow the folder you are
working in.

## File format

A `.ceptkey` file is dotenv-style key/value text. Comments are allowed.

```ini
# cept-meta:service=openrouter
# cept-meta:key_name=cept-eidos-01
# cept-meta:created_at=2026-05-23T18:16:44+00:00
# cept-meta:created_on=daniels-mbp.local
# cept-meta:created_by=dev@example.com
# cept-meta:created_os=Darwin 24.3.0 (arm64)
# cept-meta:scope=~/repos-eidos-agi/
# cept-meta:notes=Eidos AGI shared cept key

OPENROUTER_API_KEY=sk-or-...
CEPT_PROVIDER=openrouter
CEPT_DEFAULT_MODEL=perplexity/sonar-pro
CEPT_LOOKBACK_MINUTES=20
OPENROUTER_TITLE=cept
OPENROUTER_REFERER=https://github.com/eidos-agi/cept
```

`# cept-meta:` lines are metadata comments. Shells ignore them, but cept reads
them and includes the metadata in dry-run/live output so you can tell which key
was used without exposing the key value.

## Supported keys

| Key | Required | Effect |
|-----|----------|--------|
| `OPENROUTER_API_KEY` | Yes for live calls | OpenRouter credential used for model calls. |
| `CEPT_PROVIDER` | No | `auto` or `openrouter`. Both resolve to OpenRouter in this build. |
| `CEPT_DEFAULT_MODEL` | No | Default model when `--model` is not passed. Default is `perplexity/sonar-pro`. |
| `CEPT_LOOKBACK_MINUTES` | No | Default transcript window when `--lookback` is not passed. |
| `OPENROUTER_REFERER` | No | Optional `HTTP-Referer` header for OpenRouter attribution. |
| `OPENROUTER_TITLE` | No | Optional `X-Title` header for OpenRouter attribution. |

## Provider reality

cept gets grounded Perplexity answers through OpenRouter model slugs such as
`perplexity/sonar-pro`.

Use:

```ini
OPENROUTER_API_KEY=sk-or-...
CEPT_PROVIDER=openrouter
CEPT_DEFAULT_MODEL=perplexity/sonar-pro
```

Do not use `PERPLEXITY_API_KEY` for cept today. Native Perplexity API routing is
not wired in this build. If `OPENROUTER_API_KEY` is missing, live calls fail
with an actionable provider error.

## Placement patterns

For a whole repo family:

```text
~/repos-eidos-agi/.ceptkey
~/repos-eidos-agi/cept/
~/repos-eidos-agi/eidos-marketplace/
```

For a single repo:

```text
~/repos-eidos-agi/cept/.ceptkey
```

For a temporary experiment:

```text
/tmp/cept-smoke/.ceptkey
```

The nearest file wins, so a repo-specific `.ceptkey` overrides a parent
repo-family `.ceptkey`.

## Safety rules

Add both names to your global git ignore:

```bash
git config --global --add core.excludesfile ~/.gitignore_global
printf '%s\n' '.ceptkey' 'ceptkey' >> ~/.gitignore_global
```

Use `cept-keyfile show` rather than `cat .ceptkey` when sharing diagnostics. It
prints key names and metadata, not secret values.

Be careful in untrusted directories. cept intentionally loads the nearest
`.ceptkey` and lets file values override process env. That is useful for
per-project routing, but a hostile checkout could point cept at an unexpected
key or model. Run `cept-keyfile where` before live calls if the directory is not
one you control.

## Troubleshooting

No key found:

```bash
cept-keyfile where
```

If it prints no file, create one in the repo or a trusted parent folder.

Live call says `OPENROUTER_API_KEY not set`:

```bash
cept-keyfile show
env | grep OPENROUTER_API_KEY
```

If `cept-keyfile show` finds a `.ceptkey`, make sure it contains
`OPENROUTER_API_KEY`. If it does not find one, export the variable or create a
keyfile.

Wrong model:

```bash
cept-keyfile show --json
cept-cli --goal "model check" --headline "model check" --dry-run --quiet
```

Check `CEPT_DEFAULT_MODEL` in the keyfile and the `config.model` field in the
dry-run output.

Need to prove the provider path:

```bash
cept-cli \
  --goal "prove provider smoke path works" \
  --headline "provider smoke test" \
  --transcript /tmp/agent.jsonl \
  --mode steer \
  --quiet \
  --no-repo-state
```

The output should include:

```json
{
  "config": {
    "provider": "openrouter",
    "model": "perplexity/sonar-pro"
  },
  "guidance": {
    "_provider": "openrouter",
    "_model": "perplexity/sonar-pro"
  }
}
```
