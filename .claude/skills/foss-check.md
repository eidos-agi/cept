# foss-check — FOSS Readiness Audit for Agentic Software

Audit the current repository against Eidos AGI open-source standards for agentic software — tools built for AI agents to use, not humans.

## Trigger

User says `/foss-check` or asks to audit a repo for open-source readiness.

## Instructions

Run every check below against the current working directory. For each item, report PASS, FAIL, or WARN with a one-line explanation. At the end, give an overall grade (A–F) and list the exact commands or steps to fix every failure.

---

### 1. Community Health (Human Layer)

These files serve contributors and maintainers — the humans who build the agentic tools.

| File | What to check |
|------|--------------|
| `README.md` | Exists, >20 lines, has install instructions, has usage example |
| `LICENSE` | Exists, contains a recognized license (MIT, Apache-2.0, etc.) |
| `CHANGELOG.md` | Exists, follows Keep a Changelog format |
| `CONTRIBUTING.md` | Exists, has setup instructions |
| `CODE_OF_CONDUCT.md` | Exists, has enforcement contact |
| `SECURITY.md` | Exists, has vulnerability reporting instructions and contact email |

### 2. Agentic Quality (Agent Layer)

These checks are what make foss-forge different from a generic FOSS checklist. They assess whether an AI agent can effectively discover, understand, and use this tool.

#### MCP Server Checks (if the package is an MCP server)

Detect by looking for: `mcp.server`, `FastMCP`, `@mcp.tool`, `@server.tool`, or MCP entry points in pyproject.toml.

| Check | What to look for |
|-------|-----------------|
| Tool descriptions | Every `@tool` or `@mcp.tool` has a description. Descriptions are >20 chars, explain what the tool does (not just its name restated), and include when to use it. |
| Parameter descriptions | Every tool parameter has a `description` field in its schema. No bare params with just a type. |
| Parameter types | Every parameter has an explicit type. No `Any` or untyped params. |
| Error messages | Error returns/raises include actionable text — not just "failed" but what went wrong and what the agent should try instead. Grep for `raise`, `return.*error`, `HTTPException`. |
| Tool count | WARN if >25 tools — agent context windows are finite. Suggest grouping or splitting. |
| Entry point | Has an MCP entry point in pyproject.toml (`[project.entry-points."mcp"]`) or a documented `uvx`/`npx` invocation. |

#### SDK/Library Checks (if the package is NOT an MCP server)

| Check | What to look for |
|-------|-----------------|
| Type hints | Public functions have type hints on params and return values. |
| Docstrings | Public functions have docstrings that an agent could parse for usage. |
| Structured errors | Exceptions are typed (custom exception classes), not bare `Exception()`. |

#### Agent Discoverability

| Check | What to look for |
|-------|-----------------|
| SKILL.md | If the project is an MCP server or agent tool, check for a `SKILL.md` file that provides structured metadata for agent discovery (name, description, capabilities, entry point). WARN if missing on agentic tools. |
| MCP config example | README includes a JSON snippet showing how to add this tool to `claude_desktop_config.json` or `.mcp.json`. |
| Agent usage example | README has an "Agent integration" section showing programmatic API usage or structured output (e.g., `--json` flag), not just human CLI usage. |

### 3. Package Quality (Engineering Layer)

| Field | What to check |
|-------|--------------|
| `project.name` | Present |
| `project.version` | Present, valid semver |
| `project.description` | Present, >10 chars |
| `project.license` | Present, matches LICENSE file |
| `project.requires-python` | Present |
| `project.classifiers` | Present, ≥3 classifiers |
| `project.keywords` | Present, ≥2 keywords |
| `project.urls` | Has at least Homepage and Repository |
| `build-system` | Uses `hatchling` (WARN if setuptools — recommend migration) |

### 4. CI/CD

| Check | What to look for |
|-------|-----------------|
| Test workflow | `.github/workflows/ci.yml` or similar — runs tests on push/PR |
| Publish workflow | `.github/workflows/publish.yml` or similar — publishes on tag push |
| Trusted publisher | Publish workflow uses `pypa/gh-action-pypi-publish` with OIDC (`permissions: { id-token: write, contents: read }`). FAIL if workflow uses a stored `PYPI_TOKEN` secret instead. No long-lived PyPI credentials in CI — the friction of per-package OIDC registration is the security feature (blast radius containment). |
| GitHub environment | Publish workflow references `environment: pypi`. WARN if missing — trusted publisher won't work without it. |

### 5. Dependency Hygiene

Agentic tools get installed programmatically — bloated dependency trees mean slow installs, version conflicts, and fragile environments. Fewer deps = better agent UX.

| Check | What to look for |
|-------|-----------------|
| Dependency count | Count direct dependencies in `project.dependencies`. PASS if ≤5, WARN if 6-10, FAIL if >10. |
| Heavy deps | Flag known heavy packages: `numpy`, `pandas`, `scipy`, `torch`, `tensorflow` — WARN unless the project genuinely needs them. |
| Vendorable deps | If using `rich` or `click`, WARN and suggest vendoring or replacing (rich → ANSI escapes, click → argparse). Reference apple-a-day research. |
| Pinned versions | WARN if dependencies use `==` pins (fragile). Prefer `>=` with upper bounds or no pins. |

### 6. Security

| Check | What to look for |
|-------|-----------------|
| No secrets | Grep for patterns: API keys, tokens, passwords in source files |
| `.gitignore` | Exists, covers `.env`, `__pycache__`, `dist/`, `*.egg-info` |

### 7. README Quality (deeper check)

| Check | What to look for |
|-------|-----------------|
| Badges | Has at least a PyPI version badge or CI status badge |
| Install section | Contains `pip install` or equivalent |
| Usage example | Contains a code block with actual usage |
| License mention | References the license type |
| Demo content | `demo/` directory exists with at least one asset (GIF, SVG, PNG). README embeds it above the fold. WARN if missing — repos with demos get ~42% more stars. |
| Image URLs absolute | All `<img src=` and `![](` in README use absolute URLs (https://), not relative paths. Relative images break on PyPI, npm, and anywhere README is rendered outside GitHub. FAIL if relative paths found. Fix: use `https://raw.githubusercontent.com/{org}/{repo}/main/{path}`. |

### 8. Content Freshness

| Check | What to look for |
|-------|-----------------|
| CONTRIBUTING.md accuracy | If CONTRIBUTING.md mentions tools or dependencies (e.g., "we use click and rich"), verify they still exist in pyproject.toml. WARN if references are stale. |
| Demo currency | If demo-script.sh exists, check for version strings and compare against pyproject.toml version. WARN if stale. |

---

## Grading

| Grade | Criteria |
|-------|----------|
| **A** | 0 FAIL, ≤1 WARN. Ship it. |
| **B** | 0-2 FAIL (non-critical), ≤3 WARN. Community health + agentic quality pass. |
| **C** | 3-5 FAIL, or missing LICENSE but has README. Agentic quality has gaps. |
| **D** | >5 FAIL, or no README. Critical agentic quality failures. |
| **F** | No LICENSE + no README. Not ready for public release. |

## Output Format

```
## FOSS Readiness Audit: <package-name>

### Results

| # | Layer | Check | Status | Detail |
|---|-------|-------|--------|--------|
| 1 | Community | README.md | PASS | 85 lines, has install + usage |
| 2 | Community | LICENSE | FAIL | File missing |
| 3 | Agentic | Tool descriptions | WARN | 2/8 tools have <20 char descriptions |
| ... | ... | ... | ... | ... |

### Grade: B (20/24 checks passed)

### Fix List

1. **LICENSE** — Run `/foss-init license` or copy from foss-forge templates
2. **Tool descriptions** — Expand descriptions for `tool_x` and `tool_y` to explain when to use them
...
```

## Rules

- Do NOT create or modify any files. This skill only audits and reports.
- If the repo is not a Python package (no pyproject.toml), skip the Python-specific checks and note it.
- Be specific in failure messages — say exactly what's missing, not just "missing."
- If a file exists but is low quality (e.g., 3-line README), WARN instead of PASS.
- For agentic checks, quote the actual bad descriptions/errors found — show, don't just tell.
