---
telos:
  statement: "Keep Cept as the coding agent proprioception layer that can inspect recent agent trajectory and return grounded steering without leaking secrets."
  success_when:
    - "Cept can dry-run against explicit transcripts and Claude Code transcripts."
    - "Cept can call OpenRouter-backed Perplexity models when an OpenRouter key is available."
    - "The CLI, MCP, Codex plugin, Eidos plugin, and marketplace bundle stay aligned."
    - "Shipments prove source tests, package build, clean wheel install, entrypoints, plugin validators, marketplace drift, installed plugin run, and final artifact cleanliness."
  failure_when:
    - "Cept silently ships stale source, stale marketplace, or stale installed plugin surfaces."
    - "Cept sends unredacted secrets or weak transcript packets."
    - "Cept claims grounding without a provider proof path."
  success_when_not:
    - "becomes a default always-on tool rather than a deliberate proprioception pause"
    - "couples to one agent runtime without adapter boundaries"
    - "treats model guidance as a verdict instead of evidence to reconcile"
---

# Telos

Cept is the coding agent proprioception layer: it helps an agent inspect its
own recent trajectory, blind spots, and next move before continuing.
