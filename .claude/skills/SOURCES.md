# Skill provenance

These skills are **copies** from forges in the `eidos-agi` ecosystem. They are pinned at the time of copy — they will *not* update automatically when the upstream forge changes. Refresh manually with the commands below.

> **Note**: this approach is the official forge model (per [foss-forge/README.md](https://github.com/eidos-agi/foss-forge#usage)) — copies are explicit and survive `git clone`, but they drift over time. A proper skills-store / manifest design is open work; until then, this file *is* the manifest.

| Skill | Source | Refresh |
|-------|--------|---------|
| `foss-check.md` | [foss-forge](https://github.com/eidos-agi/foss-forge/blob/main/.claude/skills/foss-check.md) | `cp ~/repos-eidos-agi/foss-forge/.claude/skills/foss-check.md .claude/skills/` |
| `foss-release.md` | [foss-forge](https://github.com/eidos-agi/foss-forge/blob/main/.claude/skills/foss-release.md) | `cp ~/repos-eidos-agi/foss-forge/.claude/skills/foss-release.md .claude/skills/` |
| `foss-launch.md` | [foss-forge](https://github.com/eidos-agi/foss-forge/blob/main/.claude/skills/foss-launch.md) | `cp ~/repos-eidos-agi/foss-forge/.claude/skills/foss-launch.md .claude/skills/` |
| `ship-release.md` | [ship-forge](https://github.com/eidos-agi/ship-forge/blob/main/.claude/skills/ship-release.md) | `cp ~/repos-eidos-agi/ship-forge/.claude/skills/ship-release.md .claude/skills/` |
| `ship-full-audit.md` | [ship-forge](https://github.com/eidos-agi/ship-forge/blob/main/.claude/skills/ship-full-audit.md) | `cp ~/repos-eidos-agi/ship-forge/.claude/skills/ship-full-audit.md .claude/skills/` |

## Refresh all

```bash
for skill in foss-check foss-release foss-launch; do
  cp ~/repos-eidos-agi/foss-forge/.claude/skills/${skill}.md .claude/skills/
done
for skill in ship-release ship-full-audit; do
  cp ~/repos-eidos-agi/ship-forge/.claude/skills/${skill}.md .claude/skills/
done
git diff .claude/skills/
```

## When you should refresh

- Before a release (`/foss-release`, `/ship-release`) — pull the latest standards.
- When a forge announces a security update.
- When you notice a skill referencing a tool you don't have.

Date pinned: 2026-04-28
