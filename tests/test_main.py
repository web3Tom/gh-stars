"""Tests for main CLI module."""

from datetime import date

import pytest

from src.config import Config
from src.models import CategorizedRepo, CloneStats, GitHubListSyncStats, StarredRepo


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
async def test_sync_command_invokes_github_lists_when_enabled(monkeypatch, tmp_vault, tmp_clones):
    """Test sync wires categorized repos into GitHub Lists when requested."""
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
        list="agent-research",
        tags=("layer/library", "lang/python"),
    )
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"
    calls = {"lists": 0}

    class FakeGitHubClient:
        def __init__(self, pat):
            self.pat = pat

        async def list_starred_repos(self):
            yield repo

        async def fetch_readme(self, owner, name):
            return "# Repo\n\nAgent framework."

    class FakeListsClient:
        def __init__(self, pat):
            self.pat = pat

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
        return output_dir / "owner-repo.md"

    async def fake_reconcile_clones(output_dir, clones_dir):
        assert output_dir == notes_dir
        assert clones_dir == tmp_clones
        return CloneStats(0, 0, 0, 0, ())

    async def fake_sync_github_lists(client, categorized_repos, readmes):
        assert isinstance(client, FakeListsClient)
        assert categorized_repos == [categorized]
        assert readmes == {123: "# Repo\n\nAgent framework."}
        calls["lists"] += 1
        return GitHubListSyncStats(1, 1, 0, 0, 0, ())

    monkeypatch.setattr(
        main,
        "load_config",
        lambda config_path=None: Config("ghp-test", "sk-test", tmp_vault, tmp_clones),
    )
    monkeypatch.setattr(main, "GitHubClient", FakeGitHubClient)
    monkeypatch.setattr(main, "GitHubListsClient", FakeListsClient)
    monkeypatch.setattr(main, "resolve_github_lists_token", lambda default_token: "gh-list-token")
    monkeypatch.setattr(main, "read_existing_ids", lambda output_dir: set())
    monkeypatch.setattr(main, "categorize_repos", fake_categorize)
    monkeypatch.setattr(main, "write_repo_note", fake_write_repo_note)
    monkeypatch.setattr(main, "reconcile_clones", fake_reconcile_clones)
    monkeypatch.setattr(main, "sync_github_lists", fake_sync_github_lists)

    await main._sync_command(sync_lists=True)

    assert calls["lists"] == 1


@pytest.mark.asyncio
async def test_sync_existing_github_lists_command_backfills_notes(
    monkeypatch, tmp_vault, tmp_clones
):
    """Test backfill command hydrates starred repos and syncs active notes."""
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
        list="agent-research",
        tags=("layer/library", "lang/python"),
    )
    calls = {"lists": 0}

    class FakeGitHubClient:
        def __init__(self, pat):
            self.pat = pat

        async def list_starred_repos(self):
            yield repo

    class FakeListsClient:
        def __init__(self, pat):
            self.pat = pat

    def fake_read_existing_categorized_notes(notes_dir, starred_repos_by_id):
        assert starred_repos_by_id == {123: repo}
        return [categorized]

    async def fake_sync_github_lists(client, categorized_repos, readmes=None):
        assert isinstance(client, FakeListsClient)
        assert categorized_repos == [categorized]
        assert readmes is None
        calls["lists"] += 1
        return GitHubListSyncStats(1, 1, 0, 0, 0, ())

    monkeypatch.setattr(
        main,
        "load_config",
        lambda config_path=None: Config("ghp-test", "sk-test", tmp_vault, tmp_clones),
    )
    monkeypatch.setattr(main, "GitHubClient", FakeGitHubClient)
    monkeypatch.setattr(main, "GitHubListsClient", FakeListsClient)
    monkeypatch.setattr(main, "resolve_github_lists_token", lambda default_token: "gh-list-token")
    monkeypatch.setattr(main, "read_existing_categorized_notes", fake_read_existing_categorized_notes)
    monkeypatch.setattr(main, "sync_github_lists", fake_sync_github_lists)

    await main._sync_existing_github_lists_command(max_repos=1)

    assert calls["lists"] == 1
