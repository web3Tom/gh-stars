# Goal

Make local `gh-stars` runs write to the workspace Obsidian vault by default and align command documentation with the actual CLI.

# Why this change exists

The CLI currently resolves `KNOWLEDGE_BASE_DIR` to `~/gh-stars-data` when unset, so generated notes miss the intended vault path at `../knowledge/09_feeds/gh-stars`. The README and installed `gh-stars` skill also show flat flags that the current argparse surface does not accept.

# Scope

- Default `KNOWLEDGE_BASE_DIR` resolution in project config.
- Config tests for workspace-vault default behavior.
- README, AGENTS handoff notes, `.envrc` guidance, and installed skill command examples.
- First-batch sync after tests pass.

# Non-goals

- Refactor the CLI back to flat top-level flags.
- Close the project-wide coverage gap.
- Change generated Markdown frontmatter schema.

# Risks or constraints

- Public docs should avoid hardcoded machine-specific absolute paths.
- Existing users who explicitly set `KNOWLEDGE_BASE_DIR` must keep that override behavior.
- The installed skill file is outside the repo and is only being updated because the user explicitly requested skill command fixes.

# Acceptance criteria

- [x] With no `KNOWLEDGE_BASE_DIR`, config defaults to `../knowledge` when running from the workspace project.
- [x] Explicit `KNOWLEDGE_BASE_DIR` still wins.
- [x] README and installed skill use `uv run gh-stars sync ...` for sync flags.
- [x] `uv run pytest` passes.
- [x] Coverage command is run and its result is reported.
- [x] First batch writes notes to `knowledge/09_feeds/gh-stars`.

# Verification plan

- Run focused config tests.
- Run `uv run pytest`.
- Run `uv run pytest --cov`.
- Run `uv run gh-stars sync --max-repos 10`.
- Inspect generated note count under `../knowledge/09_feeds/gh-stars`.
