# GitHub User Lists Sync

## Goal

Create and populate GitHub-side Lists during `gh-stars sync` using GitHub GraphQL.

## Why this change exists

The Obsidian note `list` field is useful locally, but GitHub also has account-side Lists for starred repositories. The workflow should be able to create those Lists and assign newly processed starred repositories to meaningful buckets.

## Scope

- Add a GraphQL client for GitHub User Lists.
- Add deterministic logic for choosing a GitHub List from repo metadata, categorization, tags, and README text.
- Create missing Lists as needed.
- Add processed repos to the selected List while preserving existing List memberships.
- Expose the account-mutating behavior behind an explicit sync flag.
- Document token scope requirements and commands.

## Non-goals

- Do not delete or rename existing GitHub Lists.
- Do not backfill every existing note in the vault.
- Do not replace the purpose category or form tags taxonomy.
- Do not make GitHub Lists the deduplication source of truth.

## Risks or constraints

- GitHub User Lists are GraphQL-only in the tested CLI/API shape.
- `updateUserListsForItem` takes the full target list set for an item, so the implementation must preserve existing memberships.
- The list token needs GitHub permissions that include User Lists access (`user` scope for `gh` OAuth tokens). The resolver uses `GITHUB_LISTS_TOKEN`, then `gh auth token --hostname github.com`, then `GITHUB_PAT_TOKEN`.
- Some repositories may lack a GraphQL node ID in mocked or older data and must be skipped safely.

## Acceptance criteria

- [x] `StarredRepo` carries GitHub's GraphQL `node_id`.
- [x] The sync command supports `--sync-github-lists`.
- [x] Missing GitHub Lists are created before membership updates.
- [ ] Repos are assigned to cross-cutting Lists where appropriate:
  - awesome/curated markdown repos -> `Awesome Lists`
  - agent/Codex/Claude SKILL repos -> `Agent Skills`
  - learning/cookbook repos -> `Learning & Cookbooks`
  - otherwise fall back to purpose category Lists.
- [x] Existing GitHub List memberships are preserved when adding the target List.
- [x] Unit tests cover list selection, list creation, membership preservation, and missing node ID skips.
- [x] Docs describe the flag, scope requirement, and list-selection contract.

## Verification plan

- Run `uv run pytest tests/test_github_lists.py tests/test_api_client.py tests/test_models.py`.
- Run `uv run pytest`.
- Run `uv run pytest --cov` and record whether the existing coverage gate passes.
- Run a limited real workflow with `uv run gh-stars sync --max-repos 1 --sync-github-lists` if local credentials support it.
