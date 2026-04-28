# foss-launch — FOSS Launch & Marketing Playbook

Guide the launch and promotion of an Eidos AGI open-source project. Covers README optimization, distribution channels, launch timing, and sustained growth.

## Trigger

User says `/foss-launch` or asks about marketing, launching, promoting, or growing an open-source project.

### Arguments

- No args: full launch assessment + playbook for the current repo
- `readme` — README optimization only
- `badges` — generate badge markdown for the project
- `channels` — launch channel strategy only
- `timeline` — phased launch timeline only
- `homebrew` — Homebrew tap setup guide

## Instructions

### Step 1: Assess Launch Readiness

Before anything else, run a mental `/foss-check`. If the project doesn't pass at C or above, tell the user to fix fundamentals first. You can't market something that isn't ready.

### Step 2: README Optimization

The README is the conversion engine. A visitor decides in 5 seconds whether to star or bounce.

#### Hero Section (above the fold)
1. **One-line hook** — what it does + why it matters, ≤15 words. Not a technical description. A value proposition.
   - Bad: "A Python library for managing MCP server configurations"
   - Good: "Drag-and-drop MCP server scoping for Claude Code"
2. **Badges** — 4-6 max. More than 7 looks desperate. Standard set:
   - PyPI version: `[![PyPI](https://img.shields.io/pypi/v/{{PROJECT_SLUG}})](https://pypi.org/project/{{PROJECT_SLUG}}/)`
   - Python version: `[![Python](https://img.shields.io/pypi/pyversions/{{PROJECT_SLUG}})](https://pypi.org/project/{{PROJECT_SLUG}}/)`
   - License: `[![License](https://img.shields.io/github/license/{{GITHUB_ORG}}/{{GITHUB_REPO}})](LICENSE)`
   - CI status: `[![CI](https://github.com/{{GITHUB_ORG}}/{{GITHUB_REPO}}/actions/workflows/ci.yml/badge.svg)](https://github.com/{{GITHUB_ORG}}/{{GITHUB_REPO}}/actions)`
   - Star history (optional): `[![Star History](https://img.shields.io/github/stars/{{GITHUB_ORG}}/{{GITHUB_REPO}}?style=social)](https://github.com/{{GITHUB_ORG}}/{{GITHUB_REPO}})`
3. **Demo** — the single highest-impact element. Options:
   - Terminal recording: `asciinema rec` → convert with `agg` (GIF) or `svg-term-cli` (SVG)
   - Screenshot with annotations
   - For MCP tools: show the tool in action inside Claude Code or Claude Desktop
   - Repos with demos get ~42% more stars

#### Body (keep under 300 lines total)
4. **Install** — one command. `pip install` or `pipx install` for CLIs.
5. **Quick start** — 3-5 lines of code showing the core use case.
6. **For agentic tools: MCP config snippet** — the JSON to add to `.mcp.json` or `claude_desktop_config.json`.
7. **Agent integration section** — REQUIRED for agentic tools. Show:
   - Programmatic Python API usage (not just CLI)
   - Structured output mode (`--json`, `--fields`)
   - MCP config snippet (if applicable)
   - This section proves the tool is agent-native, not just human-facing
8. **Feature list** — bullet points, not paragraphs.
9. **Comparison table** (if applicable) — your tool vs. alternatives. Be honest about trade-offs.
10. Use `<details>` collapsible sections for verbose content (full API reference, advanced config).

#### Star History Chart

For established repos (>10 stars), add a star history chart:
```markdown
## Star History

[![Star History Chart](https://api.star-history.com/svg?repos={{GITHUB_ORG}}/{{GITHUB_REPO}}&type=Date)](https://star-history.com/#{{GITHUB_ORG}}/{{GITHUB_REPO}}&Date)
```

### Step 3: Distribution

For Python packages, set up distribution in this order:

1. **PyPI** — `pip install {{PROJECT_SLUG}}`. Should already be handled by `/foss-release`.
2. **pipx** — for CLI tools, document `pipx install {{PROJECT_SLUG}}` as the primary install method.
3. **Homebrew** (if applicable):
   - Create a personal tap: `eidos-agi/homebrew-tap`
   - Formula template: generate a basic Homebrew formula
   - Graduate to homebrew-core after 50+ stars
4. **uvx** — for MCP servers, document `uvx {{PROJECT_SLUG}}` invocation.

### Step 4: Launch Channel Strategy

#### Day 1: High-Impact Channels
- **Hacker News** — Post Tuesday-Thursday, 8-10am ET. Format: "Show HN: {{PROJECT_NAME}} – {{one-line hook}}". Prepare a first comment with the "why I built this" story. Respond to every comment within 2 hours.
- **Product Hunt** — Same day as HN. Prepare a maker comment.

#### Days 2-5: Reddit Stagger
Post to relevant subreddits one per day (don't spam):
- For MCP tools: r/ClaudeAI, r/LocalLLaMA, r/MachineLearning
- For Python tools: r/Python, r/commandline
- For Mac tools: r/macOS, r/macapps
- Build karma for 1-2 weeks before posting if account is new to the subreddit.

#### Week 2+: Sustained Discovery
- **Awesome Lists** — submit to 2-4 relevant curated lists (one per week). Each list has its own CONTRIBUTING.md — follow it exactly.
- **Dev.to / Hashnode** — technical writeup explaining the architecture. Good for SEO.
- **Twitter/X** — thread with demo GIF. Tag relevant accounts.

#### Month 1+: Community Building
- Seed 3-5 issues tagged `good first issue`
- Respond to every issue within 24 hours (the #1 trust signal)
- Ship v0.2.0 with a meaningful new feature
- Monthly release cadence minimum

### Step 5: Generate Launch Checklist

Output a concrete, time-boxed checklist:

```
## Launch Checklist: {{PROJECT_NAME}}

### Pre-launch (days -7 to -1)
- [ ] README optimized (hero line, badges, demo, install, quick start)
- [ ] CI green on all Python versions
- [ ] Published to PyPI
- [ ] Homebrew tap created (if applicable)
- [ ] 10-15 seed stars from personal network
- [ ] "Why I built this" story drafted for HN first comment
- [ ] Demo GIF/SVG recorded

### Launch day
- [ ] Hacker News "Show HN" post (Tue-Thu, 8-10am ET)
- [ ] Product Hunt listing
- [ ] Monitor and respond to all comments within 2 hours

### Launch week
- [ ] Reddit posts (1 per day, different subreddits)
- [ ] Dev.to technical writeup
- [ ] Twitter/X thread with demo

### Month 1
- [ ] Submit to 2-4 awesome lists
- [ ] Seed 3-5 `good first issue` tickets
- [ ] Ship v0.2.0
- [ ] Star history chart added to README (once >10 stars)
```

## Rules

- Be honest about readiness. If the project isn't ready for launch, say so and point to `/foss-check`.
- Don't generate fake engagement strategies. Seed stars from personal network is fine; buying stars is not.
- Adapt the channel strategy to the project's domain — not every project belongs on Hacker News.
- For agentic tools, emphasize the Claude/MCP community channels over general programming channels.
