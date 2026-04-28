# foss-release — Guided Release to PyPI

Walk through a structured release process: version bump, changelog update, git tag, push, and verify.

## Trigger

User says `/foss-release` or asks to release/publish a package to PyPI.

### Arguments

- `patch` (default) — bump patch version (0.1.0 → 0.1.1)
- `minor` — bump minor version (0.1.0 → 0.2.0)
- `major` — bump major version (0.1.0 → 1.0.0)
- A specific version like `0.3.0` — set exactly that version

## Instructions

### Pre-flight Checks

Before starting, verify ALL of these. Stop and fix any failures:

1. **Working tree is clean** — `git status --porcelain` returns empty. If dirty, ask user to commit or stash first.
2. **On main/master branch** — warn if releasing from a feature branch (allow if user confirms).
3. **`pyproject.toml` exists** with `project.version`.
4. **Publish workflow exists** at `.github/workflows/publish.yml` — if missing, offer to create it via `/foss-init publish`.
5. **Publish workflow uses trusted publisher (OIDC)** — FAIL if it stores a PyPI API token in secrets. Must use `pypa/gh-action-pypi-publish` with `permissions: { id-token: write, contents: read }`. See "Why Trusted Publishers" below.
6. **Trusted publisher configured on PyPI** — for first publish, a pending publisher must be registered at pypi.org/manage/account/publishing/. For existing packages, the publisher config must match the workflow (org, repo, workflow name, environment).
7. **GitHub environment exists** — a `pypi` environment must exist in repo settings (Settings → Environments). The publish workflow references this via `environment: pypi`.
8. **CHANGELOG.md exists** — if missing, offer to create via `/foss-init changelog`.
9. **LICENSE exists** — FAIL if missing. Cannot release without a license.
10. **Run `/foss-check` mentally** — if critical issues exist (no README, no license), block the release.

### Release Steps

### Step 1: Determine New Version

Read current version from `pyproject.toml`. Calculate new version based on bump type. Show user:

```
Current version: 0.1.0
New version: 0.1.1 (patch bump)
Proceed? [y/n]
```

### Step 2: Update CHANGELOG.md

Add a new section at the top of the changelog (after the header), following Keep a Changelog format:

```markdown
## [0.1.1] - 2026-03-22

### Changed
- <ask user what changed, or summarize from git log since last tag>
```

Show the user the proposed changelog entry and get confirmation before writing.

### Step 3: Bump Version in pyproject.toml

Edit `project.version` to the new version. This is the only change to pyproject.toml.

### Step 4: Commit

Create a commit with message: `release: v{version}`

Stage only: `pyproject.toml` and `CHANGELOG.md`.

### Step 5: Tag

Create an annotated git tag:
```
git tag -a v{version} -m "Release v{version}"
```

### Step 6: Push

```
git push && git push --tags
```

This triggers the publish workflow if configured.

### Step 7: Verify

After push, tell the user:
- If publish workflow exists: "GitHub Actions will publish to PyPI. Check: https://github.com/{org}/{repo}/actions"
- If no publish workflow: "No automated publish workflow found. To publish manually: `python -m build && twine upload dist/*`"
- Link to the PyPI page: "Once published: https://pypi.org/project/{package-name}/{version}/"

## Why Trusted Publishers (not API tokens)

Eidos AGI uses PyPI trusted publishers (OIDC) for all packages. This is a deliberate decision, not a default.

**What trusted publishers solve:**
- API tokens stored in CI are long-lived bearer credentials. If leaked (compromised repo admin, malicious PR, accidental logging, exfiltrating third-party action, compromised runner), the attacker can publish arbitrary versions until the token is manually revoked.
- Trusted publishers replace this with short-lived OIDC tokens minted just-in-time by GitHub Actions. No static PyPI credential exists to steal. The token is audience-restricted, identity-bound, and expires in minutes.

**Why per-package registration is a feature, not a bug:**
- A shared API token means one compromise = all packages exposed.
- A trusted publisher binds ONE package to ONE repo's ONE workflow. The blast radius of any single compromise is contained to that package.
- The 30-second form per package is what creates this containment.

**What trusted publishers do NOT solve:**
- Compromised maintainer who can modify the release workflow
- Compromised CI runner that alters build outputs
- Malicious code committed by a trusted contributor

For those, you need PEP 740 attestations + Sigstore (provenance on top of identity). That's the next layer.

**Setup for new packages:**
1. Go to https://pypi.org/manage/account/publishing/
2. Add pending publisher: project name, owner (eidos-agi), repo, workflow (publish.yml), environment (pypi)
3. Create `pypi` environment in GitHub repo settings
4. Tag and push — the workflow handles the rest

## Rules

- **Always show the user what will change before making changes.** This is a publish action — no surprises.
- **Never skip the changelog.** Even if the user says "just bump it," insist on a changelog entry.
- **Never force-push.** If push fails, diagnose and fix.
- **One version bump per release.** Don't batch multiple bumps.
- If the tag already exists, stop and ask the user what to do.
- **Never use API tokens for PyPI publishing.** Always use trusted publishers (OIDC). If someone suggests using a token "because it's easier," point them to the "Why Trusted Publishers" section above.
