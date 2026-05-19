"""Tests for cloner module."""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.cloner import reconcile_clones


@pytest.mark.asyncio
async def test_reconcile_clones_no_notes(tmp_vault, tmp_clones):
    """Test reconcile_clones with no notes directory."""
    notes_dir = tmp_vault / "nonexistent"
    stats = await reconcile_clones(notes_dir, tmp_clones)

    assert stats.attempted == 0
    assert stats.cloned == 0


@pytest.mark.asyncio
async def test_reconcile_clones_skips_archived(tmp_vault, tmp_clones):
    """Test that clones don't try to reconcile archived notes."""
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"
    archive = notes_dir / "archive"
    archive.mkdir(parents=True, exist_ok=True)

    # Create an archived note with cloned: true
    archived_note = archive / "archived-repo.md"
    archived_note.write_text(
        """---
repo: "test/archived"
cloned: true
---
# Body
"""
    )

    stats = await reconcile_clones(notes_dir, tmp_clones)

    # Should not attempt to clone archived repos
    assert stats.attempted == 0


@pytest.mark.asyncio
async def test_reconcile_clones_existing_checkout(tmp_vault, tmp_clones):
    """Test that existing clones are skipped."""
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"

    note = notes_dir / "test-repo.md"
    note.write_text(
        """---
repo: "test/repo"
cloned: true
---
# Body
"""
    )

    # Create existing clone
    clone_dir = tmp_clones / "test-repo"
    clone_dir.mkdir()
    git_dir = clone_dir / ".git"
    git_dir.mkdir()

    stats = await reconcile_clones(notes_dir, tmp_clones)

    assert stats.attempted == 1
    assert stats.skipped_existing == 1
    assert stats.cloned == 0


@pytest.mark.asyncio
async def test_reconcile_clones_false_cloned_field(tmp_vault, tmp_clones):
    """Test that cloned: false notes are ignored."""
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"

    note = notes_dir / "no-clone-repo.md"
    note.write_text(
        """---
repo: "test/noclone"
cloned: false
---
# Body
"""
    )

    stats = await reconcile_clones(notes_dir, tmp_clones)

    assert stats.attempted == 0


@pytest.mark.asyncio
async def test_reconcile_clones_git_error(tmp_vault, tmp_clones):
    """Test handling of git clone errors."""
    notes_dir = tmp_vault / "09_feeds" / "gh-stars"

    note = notes_dir / "bad-repo.md"
    note.write_text(
        """---
repo: "test/badrepo"
cloned: true
---
# Body
"""
    )

    with patch("src.cloner.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 128
        mock_run.return_value.stderr = "fatal: not a git repo"

        stats = await reconcile_clones(notes_dir, tmp_clones)

        assert stats.attempted == 1
        assert stats.failed == 1
        assert len(stats.warnings) > 0
