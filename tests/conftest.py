"""Pytest configuration and fixtures."""

import pytest
from pathlib import Path


@pytest.fixture
def tmp_vault(tmp_path):
    """Create a temporary vault-like directory structure."""
    vault = tmp_path / "vault"
    vault.mkdir()
    feeds = vault / "09_feeds" / "gh-stars"
    feeds.mkdir(parents=True)
    return vault


@pytest.fixture
def tmp_clones(tmp_path):
    """Create a temporary clones directory."""
    clones = tmp_path / "clones"
    clones.mkdir()
    return clones
