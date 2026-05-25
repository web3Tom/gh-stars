# Progress

## Current status

Complete. GitHub Lists backfill and batch membership optimization are implemented and verified.

## Completed steps

- Fixed workspace output default so local runs write to `../knowledge/09_feeds/gh-stars`.
- Updated command docs and installed workflow docs to use `uv run gh-stars sync`.
- Added purpose/form taxonomy:
  - `category` and `subCategory` describe repository purpose.
  - `tags` describe repository form with `layer/*` and `lang/*`.
  - Numeric category prefixes and entity tags are excluded.
- Passed README excerpts into Claude categorization.
- Added `tags` frontmatter and updated tests/docs/base view.
- Generated the first 10-note batch, then two one-note validation batches.
- Added GitHub User Lists sync:
  - Captures GitHub GraphQL `node_id`.
  - Creates missing Lists through GraphQL.
  - Assigns repos to deterministic cross-cutting Lists such as `Awesome Lists` and `Agent Skills`, otherwise purpose category Lists.
  - Preserves existing GitHub List memberships.
  - Resolves list token from `GITHUB_LISTS_TOKEN`, then `gh auth token --hostname github.com`, then `GITHUB_PAT_TOKEN`.
- Added language-tag enforcement so `lang/*` cannot contradict GitHub's primary language.
- Created `spec/02_github_user_lists.md`.
- Created `spec/03_github_lists_backfill.md`.
- Added active-note parser for GitHub Lists backfill.
- Optimized GitHub List membership reads to once per list per sync call.
- Added `uv run gh-stars sync-github-lists` backfill command with `--max-repos`.
- Updated README and AGENTS with the new List sync/backfill workflow.

## Remaining steps

- None for this request.

## Blockers

- None currently.

## Test results

- `uv run pytest tests/test_github_lists.py tests/test_api_client.py tests/test_models.py`: passed, 13 tests.
- `uv run pytest tests/test_categorizer.py tests/test_github_lists.py tests/test_main.py`: passed, 18 tests.
- `uv run pytest`: passed, 49 tests.
- `uv run pytest --cov`: passed, 49 tests; total coverage 80.34%.
- `uv run gh-stars sync --max-repos 1 --sync-github-lists`: first attempt wrote one note but GitHub Lists failed because `GITHUB_PAT_TOKEN` lacked User Lists access. Added `gh auth token` fallback.
- `uv run gh-stars sync --max-repos 1 --sync-github-lists`: passed after token fallback; wrote `BenedictKing-ccx.md`, created GitHub List `Infrastructure & Data`, and added `BenedictKing/ccx`.
- `uv run pytest tests/test_markdown_writer.py tests/test_github_lists.py tests/test_main.py`: passed, 18 tests.
- `uv run pytest`: passed, 53 tests.
- `uv run pytest --cov`: initially failed at 79.53%, below the configured 80% gate.
- `uv run pytest tests/test_config.py`: passed, 7 tests after adding token fallback coverage.
- `uv run pytest tests/test_markdown_writer.py`: passed, 9 tests after adding unhydrated-note parser coverage.
- `uv run pytest --cov`: passed, 55 tests; total coverage 80.41%.
- `uv run gh-stars sync-github-lists --max-repos 12`: passed; 11 updated, 4 lists created, 0 skipped, 0 failed.
- GitHub List verification after backfill:
  - `Infrastructure & Data`: 3 items.
  - `Developer Tooling`: 4 items.
  - `Learning & Cookbooks`: 1 item.
  - `Core Frameworks`: 2 items.
  - `Agent Skills`: 1 item.
  - `Applied Systems`: 1 item.
- History record appended with `active_notes: 12`, `syncable: 12`, `missing_node_id: 0`.
- `uv run gh-stars sync --max-repos 25 --sync-github-lists`: passed; 25 notes written, 25 GitHub List memberships updated, 1 List created, 0 skipped, 0 failed.
- Post-batch note count: 37 active repo notes excluding README.
- Post-batch GitHub Lists: 7 total.
  - `Learning & Cookbooks`: 10 items.
  - `Agent Skills`: 7 items.
  - `Awesome Lists`: 4 items.
  - `Core Frameworks`: 4 items.
  - `Applied Systems`: 4 items.
  - `Infrastructure & Data`: 4 items.
  - `Developer Tooling`: 4 items.
- Sanity check over active notes: no missing `tags`, no disallowed tag prefixes, no numbered categories.

## Browser validation notes

- Not applicable; no UI or browser workflow.
