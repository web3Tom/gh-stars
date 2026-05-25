"""Tests for main CLI module."""

from datetime import date

import pytest

from src.config import Config
from src.models import CategorizedRepo, CloneStats, StarredRepo


def test_main_import():
    """Test that main module imports without errors."""
    from src import main

    assert hasattr(main, "main")


def test_argument_parser():
    """Test that argparse configuration is valid."""
    from src.main import main
    import sys
    from unittest.mock import patch

    # Just verify the parser doesn't crash on --help
    with patch.object(sys, "argv", ["gh-stars", "--help"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        # --help exits with 0
        assert exc_info.value.code == 0

@pytest.mark.asyncio
async def test_sync_command_writes_notes(monkeypatch, tmp_vault, tmp_clones):
    """Test sync fetches, categorizes, writes notes, and reconciles clones."""
    from src import main

    repo = StarredRepo(
        repo_id=123,
        owner="owner",
        name="repo",
        description="Test repo",
        language="Python",
        stars=10,
        homepage=None,
        topics=(),
        license="MIT",
        repo_url="https://github.com/owner/repo",
        starred_at=date(2026, 5, 1),
        node_id="R_kgDOExample",
    )
    categorized = CategorizedRepo(
        repo=repo,
        category="Core Frameworks",
        sub_category="Agentic Orchestration",
        tags=("layer/library", "lang/python"),
    )
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"
    calls = {"write": 0}

    class FakeGitHubClient:
        def __init__(self, pat):
            self.pat = pat

        async def list_starred_repos(self):
            yield repo

        async def fetch_readme(self, owner, name):
            return "# Repo\n\nAgent framework."

    async def fake_categorize(repos, output_dir, api_key, readmes):
        assert repos == [repo]
        assert output_dir == notes_dir
        assert api_key == "sk-test"
        assert readmes == {123: "# Repo\n\nAgent framework."}
        return [categorized]

    async def fake_write_repo_note(output_dir, write_repo, write_category, readme):
        assert write_repo == repo
        assert write_category == categorized
        assert readme == "# Repo\n\nAgent framework."
        calls["write"] += 1
        return output_dir / "owner-repo.md"

    async def fake_reconcile_clones(output_dir, clones_dir):
        assert output_dir == notes_dir
        assert clones_dir == tmp_clones
        return CloneStats(0, 0, 0, 0, ())

    monkeypatch.setattr(
        main,
        "load_config",
        lambda config_path=None: Config("ghp-test", "sk-test", tmp_vault, tmp_clones),
    )
    monkeypatch.setattr(main, "GitHubClient", FakeGitHubClient)
    monkeypatch.setattr(main, "read_existing_ids", lambda output_dir: set())
    monkeypatch.setattr(main, "categorize_repos", fake_categorize)
    monkeypatch.setattr(main, "write_repo_note", fake_write_repo_note)
    monkeypatch.setattr(main, "reconcile_clones", fake_reconcile_clones)

    await main._sync_command()

    assert calls["write"] == 1


@pytest.mark.asyncio
async def test_sync_command_dry_run_skips_categorization(monkeypatch, tmp_vault, tmp_clones):
    """Test dry-run logs fetched repos without requiring an Anthropic key."""
    from src import main

    repos = [
        StarredRepo(
            repo_id=i,
            owner="owner",
            name=f"repo-{i}",
            description="Test repo",
            language="Python",
            stars=10,
            homepage=None,
            topics=(),
            license="MIT",
            repo_url=f"https://github.com/owner/repo-{i}",
            starred_at=date(2026, 5, 1),
        )
        for i in range(12)
    ]

    class FakeGitHubClient:
        def __init__(self, pat):
            self.pat = pat

        async def list_starred_repos(self):
            for repo in repos:
                yield repo

    async def fail_categorize(*args, **kwargs):
        raise AssertionError("dry-run should not categorize")

    monkeypatch.setattr(
        main,
        "load_config",
        lambda config_path=None: Config("ghp-test", "", tmp_vault, tmp_clones),
    )
    monkeypatch.setattr(main, "GitHubClient", FakeGitHubClient)
    monkeypatch.setattr(main, "read_existing_ids", lambda output_dir: set())
    monkeypatch.setattr(main, "categorize_repos", fail_categorize)

    await main._sync_command(max_repos=11, dry_run=True)


@pytest.mark.asyncio
async def test_sync_command_missing_anthropic_key_returns(monkeypatch, tmp_vault, tmp_clones):
    """Test non-dry sync stops before categorization without an Anthropic key."""
    from src import main

    repo = StarredRepo(
        repo_id=123,
        owner="owner",
        name="repo",
        description="Test repo",
        language="Python",
        stars=10,
        homepage=None,
        topics=(),
        license="MIT",
        repo_url="https://github.com/owner/repo",
        starred_at=date(2026, 5, 1),
    )

    class FakeGitHubClient:
        def __init__(self, pat):
            self.pat = pat

        async def list_starred_repos(self):
            yield repo

    async def fail_categorize(*args, **kwargs):
        raise AssertionError("missing key should stop before categorization")

    monkeypatch.setattr(
        main,
        "load_config",
        lambda config_path=None: Config("ghp-test", "", tmp_vault, tmp_clones),
    )
    monkeypatch.setattr(main, "GitHubClient", FakeGitHubClient)
    monkeypatch.setattr(main, "read_existing_ids", lambda output_dir: set())
    monkeypatch.setattr(main, "categorize_repos", fail_categorize)

    await main._sync_command()
