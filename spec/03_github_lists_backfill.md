# GitHub Lists Backfill And Batch Optimization

## Goal

Backfill existing gh-stars notes into GitHub-side Lists cleanly, and reduce GraphQL calls during list sync batches.

## Why this change exists

The first generated notes were written before GitHub Lists sync was working. They should be added to account-side Lists without re-categorizing or rewriting the notes. The current membership preservation logic is correct but inefficient because it checks each repo against each list independently.

## Scope

- Add a parser for active gh-stars note frontmatter into `CategorizedRepo` objects.
- Hydrate existing notes with current GitHub `node_id` values by fetching starred repos.
- Add a `sync-github-lists` command for backfilling existing notes.
- Fetch GitHub List item IDs once per list per sync call and reuse them across repos.
- Preserve existing GitHub List memberships during updates.
- Add tests for note parsing, batch membership caching, and the backfill command path.

## Non-goals

- Do not re-categorize existing notes.
- Do not rewrite existing notes during backfill.
- Do not sync archived notes.
- Do not remove repos from GitHub Lists.

## Risks or constraints

- Existing notes do not contain GraphQL `node_id`, so backfill must hydrate from the current starred repos API response.
- Repos no longer starred cannot be backfilled to User Lists from local note data alone.
- `updateUserListsForItem` replaces full membership for a repo, so cached membership must be included when adding the target List.

## Acceptance criteria

- [x] Existing active notes can be read as categorized repos.
- [x] `uv run gh-stars sync-github-lists` syncs existing active notes without calling Claude.
- [x] The command supports `--max-repos` for staged backfill.
- [x] Batch sync fetches each GitHub List's items at most once per sync call.
- [x] Existing GitHub List memberships are preserved.
- [x] Tests cover parser, batch optimization, and command wiring.
- [x] Existing 12 active notes are backfilled successfully.

## Verification plan

- Run `uv run pytest tests/test_markdown_writer.py tests/test_github_lists.py tests/test_main.py`.
- Run `uv run pytest`.
- Run `uv run pytest --cov`.
- Run `uv run gh-stars sync-github-lists --max-repos 12`.
- Verify GitHub Lists and history output.
