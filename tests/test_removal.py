"""Tests for removal module."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.removal import scan_unstar_notes, remove_candidates, ScanResult


def test_scan_unstar_notes_empty(tmp_vault):
    """Test scan_unstar_notes with no notes."""
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"
    result = scan_unstar_notes(notes_dir)

    assert result.eligible == ()
    assert result.skipped == 0


def test_scan_unstar_notes_unstar_true(tmp_vault):
    """Test scanning notes with unstar: true."""
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"

    note = notes_dir / "unstar-me.md"
    note.write_text(
        """---
repo: "test/tounstar"
unstar: true
---
# Body
"""
    )

    result = scan_unstar_notes(notes_dir)

    assert len(result.eligible) == 1
    assert result.eligible[0].owner == "test"
    assert result.eligible[0].repo == "tounstar"


def test_scan_unstar_notes_unstar_false(tmp_vault):
    """Test that unstar: false notes are skipped."""
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"

    note = notes_dir / "keep-me.md"
    note.write_text(
        """---
repo: "test/tokeep"
unstar: false
---
# Body
"""
    )

    result = scan_unstar_notes(notes_dir)

    assert result.eligible == ()
    assert result.skipped == 1


def test_scan_unstar_notes_ignores_archive(tmp_vault):
    """Test that archive notes are ignored."""
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"
    archive = notes_dir / "archive"
    archive.mkdir(parents=True)

    note = archive / "archived.md"
    note.write_text(
        """---
repo: "test/archived"
unstar: true
---
# Body
"""
    )

    result = scan_unstar_notes(notes_dir)

    assert result.eligible == ()


@pytest.mark.asyncio
async def test_remove_candidates_user_declines(tmp_vault):
    """Test remove_candidates when user declines."""
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"

    note = notes_dir / "test.md"
    note.write_text(
        """---
repo: "test/repo"
unstar: true
---
# Body
"""
    )

    candidates = (
        type("obj", (), {
            "filepath": note,
            "owner": "test",
            "repo": "repo"
        })(),
    )

    def decline_callback(repos):
        return False

    from src.api_client import GitHubClient

    mock_client = AsyncMock(spec=GitHubClient)
    stats = await remove_candidates(mock_client, notes_dir, tuple(candidates), decline_callback)

    assert stats.removed == 0
    assert stats.skipped == 1


@pytest.mark.asyncio
async def test_remove_candidates_unstar_success(tmp_vault):
    """Test successful unstar and archival."""
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"
    archive_dir = notes_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    note = notes_dir / "test-unstar.md"
    note.write_text(
        """---
repo: "test/repo"
unstar: true
---
# Body
"""
    )

    from src.removal import RemovalCandidate
    from src.api_client import GitHubClient

    candidates = (RemovalCandidate(filepath=note, owner="test", repo="repo"),)

    mock_client = AsyncMock(spec=GitHubClient)
    from src.models import UnstarResult

    mock_client.unstar_repo.return_value = UnstarResult(owner="test", repo="repo")

    def accept_callback(repos):
        return True

    stats = await remove_candidates(mock_client, notes_dir, candidates, accept_callback)

    assert stats.removed == 1
    assert stats.archived == 1
    assert not note.exists()  # Original should be moved
    assert (archive_dir / "test-unstar.md").exists()  # Archive should exist
