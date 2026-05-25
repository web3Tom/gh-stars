"""Tests for models module."""

from datetime import date

from src.models import StarredRepo, CategorizedRepo, CloneStats


def test_starred_repo_creation():
    """Test creating a StarredRepo."""
    repo = StarredRepo(
        repo_id=123,
        owner="test",
        name="repo",
        description="Test repo",
        language="Python",
        stars=100,
        homepage="https://example.com",
        topics=("ai", "llm"),
        license="MIT",
        repo_url="https://github.com/test/repo",
        starred_at=date(2026, 5, 18),
    )

    assert repo.repo_id == 123
    assert repo.owner == "test"
    assert repo.name == "repo"
    assert len(repo.topics) == 2


def test_categorized_repo_creation(repo=None):
    """Test creating a CategorizedRepo."""
    repo = StarredRepo(
        repo_id=123,
        owner="test",
        name="repo",
        description="Test repo",
        language="Python",
        stars=100,
        homepage=None,
        topics=(),
        license=None,
        repo_url="https://github.com/test/repo",
        starred_at=date(2026, 5, 18),
    )

    categorized = CategorizedRepo(
        repo=repo,
        category="AI",
        sub_category="LLM",
        list="agent-research",
        tags=("layer/library", "lang/python"),
    )

    assert categorized.category == "AI"
    assert categorized.sub_category == "LLM"
    assert categorized.list == "agent-research"
    assert categorized.tags == ("layer/library", "lang/python")


def test_clone_stats():
    """Test creating CloneStats."""
    stats = CloneStats(
        attempted=10,
        cloned=8,
        skipped_existing=2,
        failed=0,
        warnings=("warning1", "warning2"),
    )

    assert stats.attempted == 10
    assert stats.cloned == 8
    assert len(stats.warnings) == 2
