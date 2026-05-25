"""Tests for markdown_writer module."""

from datetime import date
from pathlib import Path

import pytest

from src.markdown_writer import (
    read_existing_categorized_notes,
    read_existing_ids,
    write_repo_note,
)
from src.models import StarredRepo, CategorizedRepo


def test_read_existing_ids_empty(tmp_vault):
    """Test read_existing_ids with no files."""
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"
    ids = read_existing_ids(notes_dir)
    assert ids == set()


def test_read_existing_ids_from_active_notes(tmp_vault):
    """Test read_existing_ids from active notes."""
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"

    # Create a sample note
    note = notes_dir / "test-repo.md"
    note.write_text(
        """---
title: "test"
repo: "test/repo"
repo_id: 123
---
# Body
"""
    )

    ids = read_existing_ids(notes_dir)
    assert 123 in ids


def test_read_existing_ids_ignores_readme_examples(tmp_vault):
    """Test README examples do not count as existing repo notes."""
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"

    readme = notes_dir / "README.md"
    readme.write_text(
        """# gh-stars Feed

```yaml
---
repo_id: 884521234
---
```
"""
    )

    ids = read_existing_ids(notes_dir)

    assert ids == set()


def test_read_existing_ids_from_archive(tmp_vault):
    """Test read_existing_ids includes archive."""
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"
    archive_dir = notes_dir / "archive"
    archive_dir.mkdir(parents=True)

    # Create archive note
    note = archive_dir / "archived-repo.md"
    note.write_text(
        """---
title: "archived"
repo: "test/archived"
repo_id: 456
---
# Body
"""
    )

    ids = read_existing_ids(notes_dir)
    assert 456 in ids


def test_read_existing_categorized_notes_hydrates_starred_repo(tmp_vault):
    """Test active notes can be read back for GitHub Lists backfill."""
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"
    note = notes_dir / "owner-repo.md"
    note.write_text(
        """---
title: "repo"
repo: "owner/repo"
repo_id: 123
description: "From note"
category: "Core Frameworks"
subCategory: "Agentic Orchestration"
list: "agent-research"
tags: ["layer/library", "lang/python"]
language: "Python"
stars: 10
starred_at: 2026-05-01
repo_url: "https://github.com/owner/repo"
---
# Body
"""
    )
    starred_repo = StarredRepo(
        repo_id=123,
        owner="owner",
        name="repo",
        description="From GitHub",
        language="Python",
        stars=11,
        homepage=None,
        topics=("agent",),
        license="MIT",
        repo_url="https://github.com/owner/repo",
        starred_at=date(2026, 5, 1),
        node_id="R_kgDOExample",
    )

    result = read_existing_categorized_notes(notes_dir, {123: starred_repo})

    assert len(result) == 1
    assert result[0].repo is starred_repo
    assert result[0].category == "Core Frameworks"
    assert result[0].sub_category == "Agentic Orchestration"
    assert result[0].list == "agent-research"
    assert result[0].tags == ("layer/library", "lang/python")


def test_read_existing_categorized_notes_skips_readme_examples(tmp_vault):
    """Test README examples do not become backfill records."""
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"
    (notes_dir / "README.md").write_text(
        """# Feed

```yaml
---
repo: "example/repo"
repo_id: 123
---
```
"""
    )

    assert read_existing_categorized_notes(notes_dir) == []


def test_read_existing_categorized_notes_builds_repo_without_hydration(tmp_vault):
    """Test note parsing still works when the repo is not in the starred API map."""
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"
    (notes_dir / "owner-old.md").write_text(
        """---
title: "old"
repo: "owner/old"
repo_id: 321
description: "Old repo"
category: "Knowledge & Reference"
subCategory: "Curated Lists"
list: "reference"
tags: ["layer/markdown"]
language: "Markdown"
stars: 5
starred_at: 2026-05-01
repo_url: "https://github.com/owner/old"
---
# Body
"""
    )

    result = read_existing_categorized_notes(notes_dir)

    assert len(result) == 1
    assert result[0].repo.repo_id == 321
    assert result[0].repo.owner == "owner"
    assert result[0].repo.name == "old"
    assert result[0].repo.node_id is None
    assert result[0].category == "Knowledge & Reference"


@pytest.mark.asyncio
async def test_write_repo_note(tmp_vault):
    """Test writing a repo note atomically."""
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"

    repo = StarredRepo(
        repo_id=789,
        owner="karpathy",
        name="llm-wiki",
        description="Personal knowledge base",
        language="Python",
        stars=4521,
        homepage="https://karpathy.ai",
        topics=("ai", "knowledge-base"),
        license="MIT",
        repo_url="https://github.com/karpathy/llm-wiki",
        starred_at=date(2026, 3, 15),
    )

    categorized = CategorizedRepo(
        repo=repo,
        category="AI Knowledge",
        sub_category="personalKnowledgeBase",
        list="agent-research",
        tags=("layer/markdown", "lang/python"),
    )

    readme = "# LLM Wiki\n\nA personal knowledge base for AI."

    path = await write_repo_note(notes_dir, repo, categorized, readme)

    assert path.exists()
    assert path.name == "karpathy-llm-wiki.md"

    content = path.read_text()
    assert 'repo_id: 789' in content
    assert 'category: "AI Knowledge"' in content
    assert 'subCategory: "personalKnowledgeBase"' in content
    assert 'list: "agent-research"' in content
    assert 'tags: ["layer/markdown", "lang/python"]' in content
    assert "karpathy/llm-wiki" in content
    assert "LLM Wiki" in content


@pytest.mark.asyncio
async def test_write_repo_note_no_readme(tmp_vault):
    """Test writing a repo note without README."""
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"

    repo = StarredRepo(
        repo_id=999,
        owner="test",
        name="no-readme",
        description=None,
        language=None,
        stars=0,
        homepage=None,
        topics=(),
        license=None,
        repo_url="https://github.com/test/no-readme",
        starred_at=date(2026, 5, 1),
    )

    categorized = CategorizedRepo(
        repo=repo,
        category="Misc",
        sub_category="Uncategorized",
        list="unsorted",
        tags=("layer/library",),
    )

    path = await write_repo_note(notes_dir, repo, categorized, None)

    content = path.read_text()
    assert "No README available" in content


@pytest.fixture
def pytest():
    """Add pytest import for asyncio tests."""
    import pytest

    return pytest
