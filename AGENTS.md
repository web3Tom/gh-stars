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

## Current State (last updated 2026-08-10)

**Pipeline is in routine production use. Full end-to-end sync runs clean against live GitHub + Anthropic APIs, and the workspace vault holds 449 categorized repo notes.**

### What works
- Repository live on GitHub at `https://github.com/web3Tom/gh-stars`, branch `main` tracking `origin/main`.
- `uv sync` resolves cleanly; `uv.lock` committed.
- `pre-commit` hook installed and passing on the current tree; auto-migrated from deprecated `stages: [commit]` to `stages: [pre-commit]`.
- All **50/50 unit tests pass** (`uv run pytest`) at **80.52% coverage** — above the `fail_under = 80` gate.
- **Full sync verified end to end** (2026-08-10): 439 starred repos fetched over 6 pages, 361 deduped by `repo_id`, 88 new notes categorized in 4 batches and written; clone reconciliation ran with 0 failures.
- Local default output resolves to `../knowledge/02_intake/gh-stars` when the project is checked out beside the workspace Obsidian vault and `KNOWLEDGE_BASE_DIR` is unset.
- The vault-relative notes path is defined **once** as `FEED_SUBPATH` in `src/config.py` and consumed by `main.py` and `taxonomy_matrix.py`. Do not re-inline the literal — the vault has already been reorganized once (`09_feeds` → `02_intake`), and the constant is what keeps that a one-line change.
- Frontmatter contract enforced and verified: `markdown_writer.py` scans BOTH `output_dir/*.md` and `archive/*.md` for `repo_id` dedup (see comment at `src/markdown_writer.py:33` — this is a non-negotiable invariant for the re-starring-an-archived-repo edge case).
- Consumed by the Obsidian base at `knowledge/_bases/gh-starred-repos.base`, whose views filter on `file.folder == "02_intake/gh-stars"` and `file.hasProperty("repo_id")`. Any change to the output folder or the frontmatter schema must be mirrored there.

### Known issues (backlog — NOT blocking)
1. **`pass` subprocess hangs 10s for ANTHROPIC_API_KEY auto-resolve.** The `_resolve_anthropic_key_from_pass` helper in `src/config.py` spawns `pass ai/anthropic/api-key` via `subprocess.run`, which blocks waiting for GPG-agent unlock that doesn't propagate to non-interactive contexts. Workaround documented for users: `export ANTHROPIC_API_KEY=...` directly in `.envrc.local` rather than relying on the pass fallback. Real fix: drop the pass fallback OR shorten the subprocess timeout to ~1s.
2. **`main.py` orchestration is the thinnest-covered module at 66%.** The uncovered spans are `_remove_unstarred_command` (175–220) and the argparse dispatch (277–288). Leaf modules are well covered. Worth closing before any further change to the removal flow.

### Where to pick up next
1. **Exercise `remove-unstarred` against real data.** It is the only command never run end to end; notes are flagged with `unstar: true` by hand in Obsidian. Verify the archive move happens only after the GitHub `DELETE` succeeds.
2. **Close the `main.py` coverage gap (#2)** with `_remove_unstarred_command` tests against a respx-mocked GitHub.

### Commit log
Run `git log --oneline` — this section is no longer mirrored by hand.

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
subCategory: "Purpose Discipline"
tags: ["layer/library", "lang/python"]
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
- `subCategory` uses the Title Case purpose taxonomy, for example `Agentic Orchestration` or `Workspaces & IDEs`.
- `tags` is required and must use only form facets: `layer/*` and optional `lang/*`.
- `category`/`subCategory` describe Purpose; `tags` describe Form. Do not use numeric category prefixes such as `01`.
- Do not use entity relationship tag prefixes such as `model/`, `provider/`, `tool/`, `framework/`, or `concept/`.
- `cloned: true` triggers shallow clone on next sync; `false` does nothing.
- `unstar: true` triggers unstar + archive on `remove-unstarred`; `false` does nothing.

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

The `remove-unstarred` command scans notes for `unstar: true`, prompts for confirmation (listing repos as `owner/repo`), and for each:

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
