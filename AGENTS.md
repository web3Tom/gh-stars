# Repository Instructions

## Purpose

This repository contains `gh-stars`, a Python CLI that fetches starred GitHub repositories, categorizes them with Claude, and writes them as Obsidian-friendly Markdown notes.

Public repository URL:

- `https://github.com/web3Tom/gh-stars`

Primary goals:

- keep the CLI reliable and easy to set up
- keep public docs accurate and safe to publish
- preserve the Markdown/frontmatter contract used by generated notes
- avoid committing secrets, local caches, or machine-specific artifacts

## Repository Layout

- `src/`: application code
- `tests/`: test suite
- `docs/`: public project documentation
- `README.md`: public onboarding
- `.env.example`: safe configuration template

## Skills To Use

When available in this environment:

- `obsidian-markdown`
  - Use for `.md` cleanup, heading normalization, and Markdown structure work.
- `obsidian-bases`
  - Use when work involves creating or editing `.base` files under `knowledge/_bases/`.

## Configuration And Security Rules

- Never commit `.env`, `.envrc.local`, access tokens, API keys, or copied terminal output containing secrets.
- Treat `.env.example` as the only publishable env file.
- **Secret Management:** Use `direnv` with `.envrc.local` for local development. This allows fetching secrets from secure storage like `pass` without hardcoding them in the repository.
  - Example `.envrc.local`: `export GITHUB_PAT_TOKEN=$(pass dev/github/pat-agent)`
- Before finishing, review `git diff --staged` or `git status` for accidental local-only changes.
- Keep default paths portable; avoid author-specific home-directory assumptions in public docs or code unless clearly justified.

### Pre-Commit Privacy Review (Required)

Before every commit and push:

1. **Verify no absolute paths** using home directory or username in code or docs.
2. **Verify no tokens/keys** in any file except `.env.example` (which must be empty-value placeholders).
3. **Run pre-commit hook** to detect patterns: `/home/`, `/Users/`, `ghp_`, `github_pat_`, `sk-ant-`.
4. **Diff staged changes:** `git diff --staged` and visually scan for secrets.

## Generated Markdown Contract

The notes written by `gh-stars` must follow this **exact** frontmatter schema:

```yaml
---
title: "repo-name"
repo: "owner/name"
repo_id: 123456789
description: "..."
category: "Category Name"
subCategory: "SubCategoryName"
list: "lowercase-kebab-case"
language: "Python"
stars: 1234
starred_at: 2026-05-18
repo_url: "https://github.com/owner/name"
cloned: false
unstar: false
---
```

### Frontmatter Rules

- All strings **double-quoted**.
- `repo_id` is the numeric GitHub repo ID (dedup key across active + archive).
- `subCategory` is camelCase (not snake_case or kebab-case).
- `list` is lowercase-kebab-case from a base set in `config.py:DEFAULT_LIST_BUCKETS`, with Claude allowed to extend.
- `cloned: true` triggers shallow clone on next sync; `false` does nothing.
- `unstar: true` triggers unstar + archive on `--remove-unstarred`; `false` does nothing.

### Body Structure

```markdown
## owner/repo

> Description from GitHub API (omit if null)

**Language:** ... | **Stars:** ... | **Starred:** ...

## README

(full README content, truncated at ~20KB with `... [README truncated]\n` marker)

## References

- 🔗 [Repository](https://github.com/owner/repo)
- 🌐 [Homepage](https://...)   # only if homepage is non-empty
```

## GitHub Unstar Safety

The `--remove-unstarred` command scans notes for `unstar: true`, prompts for confirmation (listing repos as `owner/repo`), and for each:

1. Calls `DELETE /user/starred/{owner}/{repo}` via GitHub API.
2. On success, atomically moves `.md` to `archive/{filename}`.
3. On rate limit or auth error, stops and reports failures.
4. Appends a removal record to `.gh-stars-history.jsonl`.

**Invariants:**
- Archive scan during sync dedup ensures re-starring an archived repo doesn't create duplicates.
- Clones are left in place during unstar (separate `--prune-clones` command can clean them up later).
- No automatic cleanup of notes on missing PAT scope — user must explicitly `unstar: true`.

## Clone Reconciliation

The `reconcile_clones` flow (runs at end of every sync by default):

1. Scans **active** notes for `cloned: true`.
2. For each, checks if `clones_dir/{owner}-{repo}/.git` exists.
3. If not, runs `git clone --depth=1 https://github.com/{owner}/{repo}.git {clones_dir}/{owner}-{repo}/`.
4. Sequential (no parallelism in v1).
5. Never deletes clones; they persist independently of note state.

## API Client Rate Limiting

The `GitHubClient` watches `X-RateLimit-Remaining`:

- If it drops below 100, sleep until `X-RateLimit-Reset` (UNIX timestamp) + 2s jitter before resuming.
- This is a **soft guard**, not a hard cap; the client doesn't pre-fetch limits.

## Testing

- Test framework: `pytest` + `pytest-asyncio`.
- Mocking: `respx` for `httpx` calls.
- Coverage: ≥80% required (configured in `pyproject.toml`).
- Critical paths to cover:
  - Pagination + rate-limit sleep in API client.
  - Dedup with archive (re-starring archived repo must not create duplicate).
  - Frontmatter YAML round-trip and escaping.
  - Removal atomicity (move to archive succeeds before API succeeds).
  - Clone reconcile idempotency (existing checkout not re-cloned).
  - Config loading with missing PAT (raises ValueError).
  - Batch-25 categorizer parsing + unparseable fallback.

## Commit Message Format

Use conventional commits:

```
feat: add CLI flag for dry-run
fix: handle missing README gracefully
docs: update frontmatter schema
test: add coverage for clone idempotency
chore: bump httpx to 0.29
```

## Pull Request Workflow

1. Create a feature branch.
2. Make atomic commits with clear messages.
3. Run tests locally: `uv run pytest --cov`.
4. Ensure coverage ≥80%.
5. Push and open a PR with a clear summary.
6. Reference this file for any schema or behavior changes.
