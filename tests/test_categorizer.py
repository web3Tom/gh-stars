"""Tests for categorizer module."""

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.categorizer import read_existing_taxonomy, categorize_repos, normalize_tags
from src.models import StarredRepo


def test_read_existing_taxonomy_empty(tmp_vault):
    """Test read_existing_taxonomy with no files."""
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"
    categories, lists, tags = read_existing_taxonomy(notes_dir)

    assert categories == {}
    assert lists == set()
    assert tags == set()


def test_read_existing_taxonomy_with_notes(tmp_vault):
    """Test read_existing_taxonomy scans frontmatter."""
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"

    note = notes_dir / "test.md"
    note.write_text(
        """---
category: "AI"
subCategory: "LLM"
list: "agent-research"
tags: ["layer/library", "lang/python"]
---
# Body
"""
    )

    categories, lists, tags = read_existing_taxonomy(notes_dir)

    assert "AI" in categories
    assert "LLM" in categories["AI"]
    assert "agent-research" in lists
    assert tags == {"layer/library", "lang/python"}


def test_read_existing_taxonomy_ignores_readme_examples(tmp_vault):
    """Test README examples do not pollute taxonomy."""
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"

    readme = notes_dir / "README.md"
    readme.write_text(
        """# gh-stars Feed

```yaml
---
category: "Example Category"
subCategory: "exampleSubcategory"
list: "example-list"
---
```
"""
    )

    categories, lists, tags = read_existing_taxonomy(notes_dir)

    assert categories == {}
    assert lists == set()
    assert tags == set()


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

    categories, lists, tags = read_existing_taxonomy(notes_dir)

    # Archive categories NOT in main dict (we only scan active for categories)
    # But lists ARE scanned from archive
    assert "archived-bucket" in lists
    assert tags == set()


def test_normalize_tags_allows_only_form_prefixes():
    """Test tag normalization drops entity-relationship prefixes."""
    tags = normalize_tags(
        [
            "Layer/CLI",
            "lang/TypeScript",
            "concept/rag",
            "tool/docker",
            "layer/cli",
            "bad",
        ],
        require_layer=True,
    )

    assert tags == ("layer/cli", "lang/typescript")


def test_normalize_tags_requires_layer_when_requested():
    """Test enforced tags always include a layer facet."""
    tags = normalize_tags(["lang/python"], require_layer=True)

    assert tags == ("layer/library", "lang/python")


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
        assert result[0].tags == ("layer/library", "lang/python")


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
            '[{"repo_id": 1, "category": "Core Frameworks", "subCategory": "Agentic Orchestration", "list": "ai-coding-tools", "tags": ["layer/library", "lang/python", "tool/docker"]}]'
        )

        result = await categorize_repos(
            repos,
            notes_dir,
            "sk-test",
            {1: "# Repo\n\nPython library for agent orchestration."},
        )

        assert len(result) == 1
        assert result[0].category == "Core Frameworks"
        assert result[0].sub_category == "Agentic Orchestration"
        assert result[0].list == "ai-coding-tools"
        assert result[0].tags == ("layer/library", "lang/python")

        user_payload = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert "readme_excerpt" in user_payload
        assert "Python library for agent orchestration" in user_payload

@pytest.mark.asyncio
async def test_categorize_repos_trusts_github_language_tag(tmp_vault):
    """Test model-inferred lang tags cannot contradict GitHub primary language."""
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"

    repos = [
        StarredRepo(
            repo_id=1,
            owner="owner",
            name="proxy",
            description="API proxy",
            language="Go",
            stars=100,
            homepage=None,
            topics=("proxy",),
            license="MIT",
            repo_url="https://github.com/owner/proxy",
            starred_at=date(2026, 5, 1),
        )
    ]

    with patch("src.categorizer.anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value.content[0].text = (
            '[{"repo_id": 1, "category": "Infrastructure & Data", "subCategory": "Proxies & Gateways", "list": "infrastructure", "tags": ["layer/api", "lang/python"]}]'
        )

        result = await categorize_repos(repos, notes_dir, "sk-test")

        assert result[0].tags == ("layer/api", "lang/go")


@pytest.mark.asyncio
async def test_categorize_repos_accepts_fenced_json(tmp_vault):
    """Test Claude JSON fenced in Markdown parses successfully."""
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
        mock_client.messages.create.return_value.content[0].text = """```json
[{"repo_id": 1, "category": "Core Frameworks", "subCategory": "Agentic Orchestration", "list": "ai-coding-tools", "tags": ["lang/python"]}]
```"""

        result = await categorize_repos(repos, notes_dir, "sk-test")

        assert len(result) == 1
        assert result[0].category == "Core Frameworks"
        assert result[0].sub_category == "Agentic Orchestration"
        assert result[0].list == "ai-coding-tools"
        assert result[0].tags == ("layer/library", "lang/python")
