"""Tests for categorizer module."""

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.categorizer import read_existing_taxonomy, categorize_repos
from src.models import StarredRepo


def test_read_existing_taxonomy_empty(tmp_vault):
    """Test read_existing_taxonomy with no files."""
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"
    categories, lists = read_existing_taxonomy(notes_dir)

    assert categories == {}
    assert lists == set()


def test_read_existing_taxonomy_with_notes(tmp_vault):
    """Test read_existing_taxonomy scans frontmatter."""
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"

    note = notes_dir / "test.md"
    note.write_text(
        """---
category: "AI"
subCategory: "LLM"
list: "agent-research"
---
# Body
"""
    )

    categories, lists = read_existing_taxonomy(notes_dir)

    assert "AI" in categories
    assert "LLM" in categories["AI"]
    assert "agent-research" in lists


def test_read_existing_taxonomy_from_archive(tmp_vault):
    """Test that archive lists are scanned."""
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"
    archive_dir = notes_dir / "archive"
    archive_dir.mkdir(parents=True)

    note = archive_dir / "archived.md"
    note.write_text(
        """---
category: "Archive"
subCategory: "Old"
list: "archived-bucket"
---
# Body
"""
    )

    categories, lists = read_existing_taxonomy(notes_dir)

    # Archive categories NOT in main dict (we only scan active for categories)
    # But lists ARE scanned from archive
    assert "archived-bucket" in lists


@pytest.mark.asyncio
async def test_categorize_repos_fallback_on_parse_error(tmp_vault):
    """Test fallback when Claude response is unparseable."""
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"

    repos = [
        StarredRepo(
            repo_id=1,
            owner="test",
            name="repo",
            description="Test",
            language="Python",
            stars=10,
            homepage=None,
            topics=(),
            license=None,
            repo_url="https://github.com/test/repo",
            starred_at=date(2026, 5, 1),
        )
    ]

    with patch("src.categorizer.anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        # Simulate unparseable response
        mock_client.messages.create.return_value.content[0].text = "not valid json"

        result = await categorize_repos(repos, notes_dir, "sk-test")

        # Should return fallback categorization
        assert len(result) == 1
        assert result[0].category == "General"
        assert result[0].sub_category == "Uncategorized"
        assert result[0].list == "unsorted"


@pytest.mark.asyncio
async def test_categorize_repos_success(tmp_vault):
    """Test successful categorization."""
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"

    repos = [
        StarredRepo(
            repo_id=1,
            owner="owner",
            name="repo",
            description="AI repo",
            language="Python",
            stars=100,
            homepage=None,
            topics=("ai", "llm"),
            license="MIT",
            repo_url="https://github.com/owner/repo",
            starred_at=date(2026, 5, 1),
        )
    ]

    with patch("src.categorizer.anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        # Mock successful response
        mock_client.messages.create.return_value.content[0].text = (
            '[{"repo_id": 1, "category": "AI", "subCategory": "LLM", "list": "ai-coding-tools"}]'
        )

        result = await categorize_repos(repos, notes_dir, "sk-test")

        assert len(result) == 1
        assert result[0].category == "AI"
        assert result[0].sub_category == "LLM"
        assert result[0].list == "ai-coding-tools"
