import json

from src.taxonomy_matrix import (
    render_json,
    render_markdown,
    render_terminal_table,
    resolve_feed_dir,
    scan_taxonomy_matrix,
)


def test_scan_taxonomy_matrix_counts_category_subcategory_and_tags(tmp_vault):
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"
    (notes_dir / "one.md").write_text(
        """---
repo: "owner/one"
repo_id: 1
category: "Core Frameworks"
subCategory: "Memory & Context"
tags: ["layer/library", "lang/python"]
---
# Body
"""
    )
    (notes_dir / "two.md").write_text(
        """---
repo: "owner/two"
repo_id: 2
category: "Core Frameworks"
subCategory: "Memory & Context"
tags: ["layer/api", "lang/python"]
---
# Body
"""
    )
    (notes_dir / "README.md").write_text(
        """# Feed

```yaml
---
repo_id: 999
category: "Ignored"
---
```
"""
    )

    matrix = scan_taxonomy_matrix(notes_dir)

    assert matrix.total_notes == 2
    assert len(matrix.rows) == 1
    assert matrix.rows[0].category == "Core Frameworks"
    assert matrix.rows[0].sub_category == "Memory & Context"
    assert matrix.rows[0].count == 2
    assert dict(matrix.rows[0].tags) == {
        "lang/python": 2,
        "layer/api": 1,
        "layer/library": 1,
    }
    assert dict(matrix.tags)["lang/python"] == 2


def test_scan_taxonomy_matrix_skips_malformed_notes(tmp_vault):
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"
    (notes_dir / "bad.md").write_text("# No frontmatter\n")

    matrix = scan_taxonomy_matrix(notes_dir)

    assert matrix.total_notes == 0
    assert matrix.skipped_files == ("bad.md",)


def test_render_markdown_includes_matrix_and_tags(tmp_vault):
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"
    (notes_dir / "one.md").write_text(
        """---
repo: "owner/one"
repo_id: 1
category: "Developer Tooling"
subCategory: "Workspaces & IDEs"
tags: ["layer/cli", "lang/rust"]
---
# Body
"""
    )

    markdown = render_markdown(scan_taxonomy_matrix(notes_dir))

    assert "| Developer Tooling | Workspaces & IDEs | 1 |" in markdown
    assert "`layer/cli` (1)" in markdown
    assert "| `lang/rust` | 1 |" in markdown


def test_render_json_is_stable(tmp_vault):
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"
    (notes_dir / "one.md").write_text(
        """---
repo: "owner/one"
repo_id: 1
category: "Knowledge & Reference"
subCategory: "Curated Lists"
tags: ["layer/markdown"]
---
# Body
"""
    )

    payload = json.loads(render_json(scan_taxonomy_matrix(notes_dir)))

    assert payload["total_notes"] == 1
    assert payload["matrix"][0]["subCategory"] == "Curated Lists"
    assert payload["tags"] == [{"count": 1, "tag": "layer/markdown"}]


def test_render_terminal_table_is_compact_and_sorted_by_count(tmp_vault):
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"
    (notes_dir / "one.md").write_text(
        """---
repo: "owner/one"
repo_id: 1
category: "Developer Tooling"
subCategory: "Workspaces & IDEs"
tags: ["layer/cli"]
---
# Body
"""
    )
    (notes_dir / "two.md").write_text(
        """---
repo: "owner/two"
repo_id: 2
category: "Developer Tooling"
subCategory: "Workspaces & IDEs"
tags: ["layer/cli"]
---
# Body
"""
    )
    (notes_dir / "three.md").write_text(
        """---
repo: "owner/three"
repo_id: 3
category: "Knowledge & Reference"
subCategory: "Curated Lists"
tags: ["layer/markdown"]
---
# Body
"""
    )

    table = render_terminal_table(scan_taxonomy_matrix(notes_dir))

    assert "Category" in table
    assert "Subcategory" in table
    assert "Top tags:" in table
    assert table.index("Developer Tooling") < table.index("Knowledge & Reference")


def test_resolve_feed_dir_accepts_vault_root(tmp_vault):
    assert resolve_feed_dir(tmp_vault) == (tmp_vault / "09_feeds" / "gh-stars").resolve()
