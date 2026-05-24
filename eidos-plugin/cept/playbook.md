# Cept

## Goal

Use Cept as a deliberate proprioception pause for coding agents. The goal is to
review the agent's recent trajectory, surface blind spots, and return a concrete
next step without leaking secrets or treating outside guidance as a verdict.
In plain terms, Cept helps the AI inspect its own recent work, uncertainty, and
next move before it continues.

## Inputs

- `args.goal` — what the agent is trying to accomplish.
- `args.headline` — a short 3-4 word summary for the cept packet and HUD.
- `args.mode` — optional `steer`, `debug`, `research`, or `architecture`.
- `args.provider` — optional `auto` or `openrouter`; both route grounded
  Perplexity models through OpenRouter in this build.
- `args.transcript` — optional JSONL transcript path for non-Claude agents or
  deterministic replay.
- `args.files` — optional files to include for content-specific critique.

## Procedure

1. Start with local setup and metadata checks:

   ```bash
   cept-keyfile show
   cept-cli --help
   /Users/dshanklinbv/plugins/cept/scripts/cept-registry doctor
   ```

   For live calls, the environment or nearest `.ceptkey` must provide
   `OPENROUTER_API_KEY`. Native `PERPLEXITY_API_KEY` routing is intentionally
   not part of this pass because cept gets Perplexity grounding via OpenRouter
   model slugs such as `perplexity/sonar-pro`.
   See `docs/CEPTKEY.md` for lookup rules, supported keys, examples, and
   troubleshooting.

   If the caller is not Claude Code, provide an explicit transcript file:

   ```bash
   cept-cli --goal "<goal>" --headline "<headline>" --transcript /tmp/agent.jsonl --dry-run
   ```

2. If packet sensitivity is uncertain, dry-run before calling OpenRouter:

   ```bash
   cept-cli --goal "<goal>" --headline "<headline>" --dry-run
   ```

   Do not continue if the dry-run packet contains secrets, protected personal
   data, unrelated private material, or files outside the scope of the task.

3. Choose the smallest useful mode:

   ```bash
   cept-cli --goal "<goal>" --headline "<headline>" --mode steer
   cept-cli --goal "<goal>" --headline "<headline>" --mode debug
   cept-cli --goal "<goal>" --headline "<headline>" --mode research
   cept-cli --goal "<goal>" --headline "<headline>" --mode architecture
   ```

4. For content-shape critique, include only directly relevant files:

   ```bash
   cept-cli --goal "<goal>" --headline "<headline>" --mode debug --file README.md
   ```

5. To make Cept assess Cept itself, use the dogfood path:

   ```bash
   cept-cli --self-assess --transcript /tmp/agent.jsonl --dry-run
   ```

6. Reconcile Cept's output with local evidence before acting. Verify concrete
   claims against repo state, tests, logs, or primary documentation.

7. For Conduit-style storage/proof checks, use the source-owned registry:

   ```bash
   /Users/dshanklinbv/plugins/cept/scripts/cept-registry registry --json
   /Users/dshanklinbv/plugins/cept/scripts/cept-registry proof --json
   ```

## What to produce

When this plugin is used in an Eidos loop, write evidence under the loop's
evidence directory:

- `evidence/cept-dry-run-summary.md` — what was checked before sending and
  whether the packet was safe to send.
- `evidence/cept-guidance.json` — the structured cept result or a note that the
  run stopped before sending.
- `evidence/cept-reconciliation.md` — what the agent accepted, rejected, or
  verified before continuing.

## What good looks like

- Cept is used selectively at real uncertainty points, not as a default reflex.
- The headline is short enough to prove the ask is clear.
- Non-Claude agents use explicit JSONL transcript adapters instead of pretending
  to be Claude Code.
- Sensitive packets are dry-run first.
- Outside guidance is treated as evidence, not command authority.
- The final next step is grounded in both cept output and local proof.
