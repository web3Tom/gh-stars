# Taxonomy Matrix Helper

## Goal

Add a helper script that reports the category, subCategory, and tag matrix currently present in `knowledge/09_feeds/gh-stars`.

## Why this change exists

After processing the full GitHub stars backlog, the generated notes now contain the live taxonomy shape. A read-only helper makes it easy to inspect the actual category/subCategory distribution and tag usage before changing categorization rules again.

## Scope

- Add a testable scanner for gh-stars note frontmatter.
- Add a helper script that prints the matrix to stdout.
- Support Markdown output by default and JSON for automation.
- Support fixed-width terminal table output for VS Code terminal readability.
- Document the helper in the README.

## Non-goals

- Do not recategorize notes.
- Do not mutate notes or GitHub state.
- Do not require GitHub or Anthropic credentials.
- Do not add another LLM call.

## Risks or constraints

- README content may contain YAML examples, so the helper must inspect only the first frontmatter block.
- The feed README should not count as a repository note.
- Missing or malformed frontmatter should not crash the helper.

## Acceptance criteria

- [x] Helper prints category/subCategory rows with note counts.
- [x] Helper can include tag counts per row and global tag counts.
- [x] Helper supports fixed-width terminal table output.
- [x] Helper supports JSON output.
- [x] Helper defaults to the workspace knowledge feed when run from the project root.
- [x] Tests cover scanning and rendering.

## Verification plan

- Run focused taxonomy matrix tests.
- Run `uv run pytest --cov`.
- Run the helper against the live feed in Markdown mode.
- Run the helper against the live feed in JSON mode.
