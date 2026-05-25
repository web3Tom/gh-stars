# Goal

Enforce a `tags` frontmatter field for GitHub star notes while keeping categories focused on repository purpose and tags focused on repository form/ecosystem.

# Why this change exists

GitHub repositories are structural and functional artifacts, not just informational bookmarks. Category/Subcategory should describe what a repository solves in the development lifecycle. Tags should describe how it is packaged, consumed, implemented, or connected to known ecosystem entities.

# Scope

- Add `tags` to the generated frontmatter contract.
- Update categorization prompt to enforce the boundary:
  - Category/Subcategory = purpose.
  - Tags = form, interface, implementation, and ecosystem entities.
- Include README snippets in the LLM categorization payload.
- Normalize and enforce allowed form tag prefixes.
- Update tests and vault/feed documentation.

# Non-goals

- Introduce a fully configurable taxonomy override loader.
- Migrate every historical archive note.
- Replace `list` frontmatter behavior.

# Risks or constraints

- Category names must not include ordering prefixes like `01` or `02`.
- README content increases LLM prompt size; snippets should be bounded.
- Existing generated notes without tags need regeneration or backfill before the vault is fully consistent.

# Acceptance criteria

- [x] `CategorizedRepo` carries normalized tags.
- [x] `write_repo_note()` always writes a `tags: [...]` frontmatter field.
- [x] The categorizer prompt contains the purpose/form boundary.
- [x] LLM payload includes bounded README snippets.
- [x] Tags use allowed form prefixes and malformed/entity tags are dropped.
- [x] Fallback categorization still emits at least one valid tag.
- [x] Tests pass.

# Verification plan

- Run focused categorizer/model/writer tests.
- Run full `uv run pytest`.
- Run `uv run pytest --cov` and report the existing coverage gate status.
- Regenerate the first batch if needed so visible notes include tags.
