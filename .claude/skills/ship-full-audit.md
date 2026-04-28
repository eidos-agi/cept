# ship-full-audit — Run Every Forge Against a Project

Single command that chains all forge audits in sequence: FOSS standards, security, shipping quality, MCP QA, and manifest enforcement. The complete quality pipeline.

## Trigger

User says `/ship-full-audit` or asks to run a full audit, complete check, or quality gate on a project.

## Instructions

Run each forge's audit skill in order. Each check builds on the previous — stop if a critical failure would make later checks meaningless.

### Step 1: foss-check (community health + agentic quality)

Run the `/foss-check` audit from foss-forge. This covers:
- Required files (LICENSE, README, CHANGELOG, CONTRIBUTING, SECURITY, CODE_OF_CONDUCT)
- Agentic quality (tool descriptions, parameter schemas, error messages)
- Package metadata (pyproject.toml completeness)
- README quality (badges, install, usage, demo, absolute images)
- Dependency hygiene
- Content freshness

**Stop if:** No LICENSE or no README (grade F). Everything else is fixable.

### Step 2: sec-audit (security)

Run the `/sec-audit` audit from security-forge. This covers:
- Secret detection in source
- Git history secrets
- Dependency vulnerabilities
- Agentic threat surface (tool description injection, error exfiltration)
- Pre-public release checks (internal URLs, employee names)
- SECURITY.md presence

**Stop if:** Secrets found in source (CRITICAL). Everything else can proceed.

### Step 3: ship-check (shipping quality)

Run the `/ship-check` audit from ship-forge. This covers:
- Working tree hygiene (clean, up to date)
- .gitignore coverage
- Build verification (build → twine check → install-test wheel + sdist)
- Version consistency (pyproject.toml, git tags, CHANGELOG)
- CI/CD presence (ci.yml, publish.yml, trusted publisher, permissions)
- Pre-commit config
- Dependency hygiene

**Stop if:** Build fails (can't ship what doesn't build).

### Step 4: ship-qa (MCP server quality — if applicable)

Only run if the project is an MCP server (detect by `mcp.server`, `FastMCP`, `@mcp.tool`). Run the `/ship-qa` audit from ship-forge:
- Tool schema verification
- Tool description quality
- Error message standards
- Protocol correctness
- Behavior testing readiness

### Step 5: forge-enforce (manifest compliance — if applicable)

Only run if `.forge/manifest.yaml` exists. Run the `/forge-enforce` check from forge-forge:
- Compare manifest desired state to actual state
- Report drift
- Optionally fix

## Output Format

```
## Full Audit: <package-name>

### Pipeline Results

| # | Forge | Check | Grade/Status | Issues |
|---|-------|-------|-------------|--------|
| 1 | foss-forge | /foss-check | B | 2 WARN |
| 2 | security-forge | /sec-audit | CLEAN | 0 issues |
| 3 | ship-forge | /ship-check | PASS | 0 issues |
| 4 | ship-forge | /ship-qa | N/A | Not an MCP server |
| 5 | forge-forge | /forge-enforce | 0 drift | Manifest compliant |

### Overall: SHIP IT / BLOCKED (reason)

### Fix List
1. ...
2. ...
```

## Rules

- **Run in order.** Each check builds context for the next.
- **Report everything, even if you'd normally skip.** This is the complete picture.
- **Don't fix anything automatically.** This is an audit. Report findings, let the user decide.
- **Grade the overall result:** SHIP IT (all pass), WARN (minor issues), or BLOCKED (critical failures).
- **If a project has no manifest**, suggest creating one with `/forge-manifest-init`.
