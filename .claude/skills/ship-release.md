# ship-release — End-to-End Release Pipeline

Walk through a complete release: preflight checks, build verification, version bump, changelog, tag, push, and post-release smoke test.

## Trigger

User says `/ship-release` or asks to release, publish, or ship a package.

### Arguments

- `patch` (default) — 0.1.0 → 0.1.1
- `minor` — 0.1.0 → 0.2.0
- `major` — 0.1.0 → 1.0.0
- A specific version like `0.3.0`

## Instructions

### Phase 1: Preflight (blocks release if any FAIL)

Run `/ship-check` mentally. These must all pass:

1. **Clean working tree** — no uncommitted changes
2. **On main/master branch** — WARN if not, allow with confirmation
3. **CI is green** — check GitHub Actions status for latest commit
4. **Build succeeds** — `python -m build` produces wheel + sdist
5. **Artifacts install cleanly** — wheel + sdist both install in clean venvs
6. **Import + CLI test** — package imports and entry points work
7. **LICENSE exists** — cannot release without a license
8. **No known vulnerabilities** — `pip-audit` clean (WARN, not block)

If any FAIL: stop, report what's broken, don't proceed.

### Phase 2: Version + Changelog

1. **Determine new version** — read current from pyproject.toml, calculate new based on bump type
2. **Show the user:**
   ```
   Current: 0.1.0
   New: 0.1.1 (patch)
   Proceed? [y/n]
   ```
3. **Update pyproject.toml** — edit `project.version`
4. **Update CHANGELOG.md** — add entry with today's date. Ask user what changed, or summarize from `git log` since last tag. Use Keep a Changelog format.
5. **Show the changelog entry** — get user confirmation before writing

### Phase 3: Build + Verify (again, with new version)

1. `rm -rf dist/`
2. `python -m build`
3. `twine check dist/*`
4. Install wheel in temp venv, verify import + CLI
5. Verify version string matches: `python -c "import <pkg>; print(<pkg>.__version__)"`

### Phase 4: Commit + Tag + Push

1. Stage: `pyproject.toml` and `CHANGELOG.md` only
2. Commit: `release: v{version}`
3. Tag: `git tag -a v{version} -m "Release v{version}"`
4. Push: `git push && git push --tags`

### Phase 5: Post-Release Verification

After push (wait for CI/publish to complete):

1. **If publish workflow exists:**
   - "GitHub Actions will publish to PyPI. Monitor: https://github.com/{org}/{repo}/actions"
   - Wait for workflow to complete, then verify

2. **Verify on PyPI:**
   ```bash
   pip install {package}=={version}  # from PyPI, not local
   python -c "import {module}"
   {cli} --help  # if CLI exists
   ```

3. **Create GitHub Release** (optional but recommended):
   - `gh release create v{version} --title "v{version}" --notes "$(changelog entry)"`

4. **Report:**
   ```
   ## Release Complete: {package} v{version}

   ✓ Built and verified locally
   ✓ Tagged and pushed
   ✓ Published to PyPI
   ✓ Verified install from PyPI

   PyPI: https://pypi.org/project/{package}/{version}/
   GitHub: https://github.com/{org}/{repo}/releases/tag/v{version}
   ```

## Rules

- **Never skip preflight.** If checks fail, the release is blocked. No --force. (GUARD-002)
- **Always verify the built artifacts.** Test the wheel and sdist, not the source checkout.
- **Build twice** — once to verify, once after version bump with the final version.
- **Never push without user seeing the changelog entry.**
- **If publish workflow doesn't exist,** offer to create it via `/ship-init publish`, then continue.
- **Clean up temp venvs** after verification.
