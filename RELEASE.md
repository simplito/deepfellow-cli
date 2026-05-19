# Release Process

## Steps

1. Update `[Unreleased]` section in `CHANGELOG.md` — rename it to the new version with today's date, e.g. `## [0.3.0] - 2026-05-19`.
2. Update `version` in `pyproject.toml`.
3. Commit:
   ```bash
   git commit -am "Release 0.3.0"
   ```
4. Tag the commit:
   ```bash
   git tag v0.3.0
   ```
5. Push branch and tag:
   ```bash
   git push origin main
   git push origin v0.3.0
   ```

CI picks up the tag and automatically pushes to [github.com/simplito/deepfellow-cli](https://github.com/simplito/deepfellow-cli).

## Tag format

Tags must match `v<major>.<minor>.<patch>` (e.g. `v0.3.0`). Only these trigger the GitHub push.

## Prerequisites (one-time setup)

Add a CI/CD variable in GitLab → Settings → CI/CD → Variables:

| Variable | Value |
|---|---|
| `GITHUB_MIRROR_TOKEN` | GitHub Personal Access Token with `repo` scope (classic) or `contents:write` (fine-grained) for `simplito/deepfellow-cli` |
