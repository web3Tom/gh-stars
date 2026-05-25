# Remove List Allocation

## Goal

Remove GitHub List allocation and the local `list` frontmatter field from the active gh-stars workflow.

## Why this change exists

The current list allocation is too coarse and the account-side GitHub Lists created so far are not useful enough to continue mutating. The existing implementation should be preserved on a separate branch, but the active workflow should stop creating, syncing, or emitting lists.

## Scope

- Preserve the current Lists implementation on a feature branch.
- Remove GitHub Lists CLI options and backfill command from the active branch.
- Remove `list` from generated note frontmatter.
- Remove `list` from categorization prompts and parsed model responses.
- Strip `list:` from active gh-stars notes in the knowledge vault.
- Update docs and tests to reflect the list-free workflow.

## Non-goals

- Do not delete GitHub-side Lists from the user's account.
- Do not process additional starred repositories.
- Do not change category/subCategory purpose taxonomy.
- Do not change tag enforcement.

## Risks or constraints

- Existing notes may contain `list:` fields that should be removed without altering README content.
- GitHub-side Lists already created remain in the account unless explicitly deleted later.
- Tests that exercised GitHub Lists behavior need to be removed or rewritten.

## Acceptance criteria

- [x] A preservation branch exists for the current Lists implementation.
- [x] `uv run gh-stars sync --help` no longer exposes `--sync-github-lists`.
- [x] `uv run gh-stars --help` no longer exposes `sync-github-lists`.
- [x] Generated frontmatter no longer includes `list:`.
- [x] Active knowledge notes under `knowledge/09_feeds/gh-stars` no longer contain `list:` in frontmatter.
- [x] Relevant tests pass.

## Verification plan

- Run `uv run pytest`.
- Run `uv run pytest --cov`.
- Run `uv run gh-stars --help` and `uv run gh-stars sync --help`.
- Scan source/docs/tests for GitHub Lists and `list:` schema references.
- Scan active gh-stars knowledge notes for frontmatter `list:`.
