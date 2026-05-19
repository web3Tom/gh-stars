"""Tests for config module."""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import Config, load_config


def test_load_config_missing_github_pat(monkeypatch, tmp_path):
    """Test that missing GITHUB_PAT_TOKEN raises ValueError."""
    monkeypatch.delenv("GITHUB_PAT_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(ValueError, match="GITHUB_PAT_TOKEN"):
        load_config()


def test_load_config_with_env(monkeypatch, tmp_path):
    """Test loading config from environment."""
    monkeypatch.setenv("GITHUB_PAT_TOKEN", "ghp_test123")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test456")

    config = load_config()

    assert config.github_pat == "ghp_test123"
    assert config.anthropic_api_key == "sk-test456"
    assert isinstance(config.knowledge_base_dir, Path)
    assert isinstance(config.clones_dir, Path)


def test_load_config_from_file(monkeypatch, tmp_path):
    """Test loading config from .env file."""
    env_file = tmp_path / ".env"
    env_file.write_text("GITHUB_PAT_TOKEN=ghp_fromfile\nANTHROPIC_API_KEY=sk-fromfile\n")

    monkeypatch.delenv("GITHUB_PAT_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    config = load_config(env_file)

    assert config.github_pat == "ghp_fromfile"
    assert config.anthropic_api_key == "sk-fromfile"
