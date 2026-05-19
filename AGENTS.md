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

## Current State (last updated 2026-05-18)

**Scaffold + 2 bug-fix commits shipped. Pipeline is functionally complete and tested at the unit level. The first end-to-end run is blocked on a user-side PAT issue (GitHub returns 401 "Bad credentials" — see below).**

### What works
- Repository live on GitHub at `https://github.com/web3Tom/gh-stars`, branch `main` tracking `origin/main`.
- `uv sync` resolves cleanly; `uv.lock` committed.
- `pre-commit` hook installed and passing on the current tree; auto-migrated from deprecated `stages: [commit]` to `stages: [pre-commit]`.
- All **34/34 unit tests pass** (`uv run pytest`).
- CLI entrypoint runs end-to-end: `uv run gh-stars sync --dry-run` correctly loads config, authenticates to GitHub, paginates `/user/starred`, and surfaces auth errors as `UnstarScopeError` with a clear message.
- Frontmatter contract enforced and verified: `markdown_writer.py` scans BOTH `output_dir/*.md` and `archive/*.md` for `repo_id` dedup (see comment at `src/markdown_writer.py:33` — this is a non-negotiable invariant for the re-starring-an-archived-repo edge case).

### Blocked (user-side)
- **GitHub PAT returns 401 on every endpoint, including `/user`.** Indicates the credential itself is rejected (not a scope issue — scope problems are 403). Most likely root cause: when minting the fine-grained PAT on github.com, the "Resource owner" dropdown wasn't set to the user's own account, leaving the token without any permitted resources.
- Verification command:
  ```bash
  curl -s -o /dev/null -w "HTTP %{http_code}\n" \
    -H "Authorization: Bearer $GITHUB_PAT_TOKEN" \
    https://api.github.com/user
  ```
  Must return `HTTP 200` before any further smoke testing is meaningful.

### Known issues (backlog — NOT blocking)
1. **CLI shape deviates from spec.** The implementer built subcommands (`gh-stars sync`, `gh-stars remove-unstarred`, `gh-stars reconcile-clones`); the design spec called for flat top-level flags (`--dry-run`, `--remove-unstarred`, `--reconcile-clones`). The README's CLI reference table and the `gh-stars` Claude Code skill still describe the flag syntax. Fix path: either update docs to subcommand syntax (smaller change) or refactor `main.py` to flat flags (preserves spec, larger change).
2. **Test coverage at 69.79%, below spec's 80% target.** `main.py` orchestration paths sit at 24% coverage; the leaf modules (markdown_writer 95%, categorizer 86%, removal/cloner/config all ~75%) are well-covered. `pytest --cov` exits non-zero solely due to the `fail_under = 80` gate in `pyproject.toml`. Closing the gap requires ~6–10 additional tests over the `_sync_command` / `_remove_unstarred_command` / `_reconcile_clones_command` async flows.
3. **`pass` subprocess hangs 10s for ANTHROPIC_API_KEY auto-resolve.** The `_resolve_anthropic_key_from_pass` helper in `src/config.py` spawns `pass ai/anthropic/api-key` via `subprocess.run`, which blocks waiting for GPG-agent unlock that doesn't propagate to non-interactive contexts. Workaround documented for users: `export ANTHROPIC_API_KEY=...` directly in `.envrc.local` rather than relying on the pass fallback. Real fix: drop the pass fallback OR shorten the subprocess timeout to ~1s.
4. **CLI subcommand `--help` output doesn't match docs.** Once #1 is decided, README + SKILL.md should be regenerated against the actual `argparse` surface.

### Where to pick up next
1. **User unblocks the PAT** — verify with the curl command above. Once `HTTP 200` returns, re-run `uv run gh-stars sync --max-repos 5 --dry-run` and confirm pagination + dedup log lines look sane.
2. **First real categorization run** (after PAT works) — `uv run gh-stars sync --max-repos 10`. Watch for: `pass` subprocess hang on Anthropic key resolution (issue #3); category/list output quality on first batch; correct frontmatter emission; `.gh-stars-history.jsonl` written to `09_feeds/gh-stars/`.
3. **Decide #1 (CLI shape).** If keeping subcommands: rewrite README CLI table + SKILL.md usage examples in one PR. If reverting to spec: refactor `main.py` argparse — a single afternoon's work.
4. **Close coverage gap (#2)** by adding `_sync_command` integration tests against a respx-mocked GitHub + a MagicMock-patched Anthropic.

### Commit log
```
289ba94  fix(tests): unblock pytest run by fixing two test-setup bugs
8aee5f5  fix: dry-run skips Anthropic key check; add missing pytest import
fb0c97e  feat: initial gh-stars scaffold
```

### Design spec (not in this repo)
The full design rationale, 27 numbered decisions, and grill-session history live in the user's Obsidian vault at `knowledge/07_specs/051826_github_stars_feed.md`. Source of truth for "why we built it this way." Not pushed to GitHub.

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
