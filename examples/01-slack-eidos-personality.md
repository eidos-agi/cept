# Example: catching a guardrail violation before it shipped

A real consultation, lightly trimmed. Shows what cept is for: outside-in steering when the agent is about to commit to a reasonable-sounding-but-wrong move.

## Context

The user asked: *"I want to give @Eidos his own personality and his own slack account, did we ever finish eidos slack work?"*

The repo (`slack-eidos`) was scaffolded but undeployed — bot code, manifest, Railway config all ready. The agent confirmed status, then proposed:

> *"Want me to (a) draft the personality prompt now by pulling from `eidos-philosophy`, then (b) walk you through the Slack app creation, then (c) deploy via railguey?"*

That sounded fine. It wasn't.

The user replied: **"ask cept"**.

## The call

```python
mcp__cept__cept(
    goal="Give @Eidos his own personality and his own Slack account. "
         "slack-eidos repo scaffolded but never deployed. Code exists: "
         "socket-mode bolt app, claude -p wrapper with thin generic "
         "SYSTEM_PROMPT, channel-scoped JSON memory. Manifest + railway.toml "
         "ready. Need to (a) write persona from eidos-philosophy, (b) create "
         "Slack app, (c) deploy to Railway. User asked status + what to do next.",
    cept_id="7f3a9c2e1b",
    question="What's the highest-leverage sequence here? Should personality "
             "be written from eidos-philosophy now, or after a few days of "
             "dogfooding reveals what Eidos actually needs to sound like? "
             "And: any gotchas for Slack bot identity that would burn us "
             "if we ship the manifest as-is?",
    mode="architecture",
    lookback_minutes=20,
)
```

## What cept returned (excerpted)

```json
{
  "summary": "The agent is at a fork: write Eidos's personality from
              eidos-philosophy now (before deployment) or after live
              dogfooding reveals actual persona requirements.
              Deploy-then-iterate is lower-risk than shipping a persona
              guess that may not fit the product.",

  "hypotheses": [
    {
      "title": "Deploy minimal persona first, iterate live (recommended)",
      "confidence": 0.78,
      "why": "Dogfooding reveals actual interaction patterns faster than
              design-by-committee. Eidos's real voice emerges from
              conversations, not philosophy docs. Risk: early adopters see
              'generic' bot, but that's acceptable for v0.1."
    },
    {
      "title": "Write full persona from eidos-philosophy before shipping",
      "confidence": 0.15,
      "why": "Ensures brand coherence from day one. Risk: persona-as-designed
              may not survive first contact with users; you burn 2-4 hours
              before learning it's wrong."
    }
  ],

  "blind_spots": [
    "Agent hasn't validated whether SYSTEM_PROMPT can swap without redeploy.",
    "Manifest scope sanity not explicitly verified.",
    "Socket-mode on Railway: long-lived WebSockets may not survive
     idle/redeploy; Bolt's reconnect isn't bulletproof.",
    "Unclear whether eidos-philosophy is finalized or itself in flux —
     pulling from it now might lock in stale values."
  ],

  "recommended_next_step": "Deploy the scaffold today with a neutral
                            functional SYSTEM_PROMPT. Live-dogfood 3-5 days.
                            Then write persona from observed needs +
                            philosophy. Redeploy. This keeps you shipped
                            and learning instead of optimizing a guess.",

  "confidence": 0.82
}
```

## What changed

The agent's recommendation flipped. Final message to the user:

> **Cept's verdict (0.82): deploy first, persona later.**
>
> Writing a persona from eidos-philosophy now is the wrong move — and not just on cept's word. The project's own guardrails already say this:
> - `ship-simplest`
> - The v0.1 strategy: *"ship dumb @Eidos this week, learn from transcript"*
> - TASK-0003 literally says *"top 3 unmet asks become next week's tasks"* — that's a transcript-driven persona too
>
> Two real concerns cept flagged that ARE worth fixing before deploy:
> 1. **Socket-mode on Railway is fragile** — set restart policy, watch logs first hour
> 2. **SYSTEM_PROMPT should be env-var swappable** — 5-min refactor; iteration becomes `railguey_variable_set` instead of code change

## The lesson

The agent had read the project's vision, guardrails, and tasks — and was *still* about to violate them. The thing it was missing wasn't information. It was perspective.

Cept's output didn't contain new facts about the project. It just held up a mirror: *"you're about to design a persona before he's said a word — you sure?"* Once that question was visible, the agent could see its own recommendation's contradiction with the guardrails it had already read.

That's the use case. Not a smarter model. A second pair of eyes that doesn't have the agent's momentum.

The blind-spot section was the bonus — two real technical risks (Railway WebSocket stability; non-swappable prompt) that the agent hadn't surfaced because it was busy planning the persona.
