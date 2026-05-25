"""Tests for config module."""

from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

from src.config import Config, load_config, resolve_github_lists_token


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
    monkeypatch.setenv("KNOWLEDGE_BASE_DIR", str(tmp_path / "vault"))

    config = load_config()

    assert config.github_pat == "ghp_test123"
    assert config.anthropic_api_key == "sk-test456"
    assert isinstance(config.knowledge_base_dir, Path)
    assert isinstance(config.clones_dir, Path)


def test_load_config_defaults_to_workspace_knowledge(monkeypatch, tmp_path):
    """Test default output path uses sibling knowledge vault in workspace."""
    workspace = tmp_path / "workspace"
    project = workspace / "gh-stars"
    vault = workspace / "knowledge"
    project.mkdir(parents=True)
    vault.mkdir()

    monkeypatch.chdir(project)
    monkeypatch.setenv("GITHUB_PAT_TOKEN", "ghp_test123")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test456")
    monkeypatch.delenv("KNOWLEDGE_BASE_DIR", raising=False)

    config = load_config()

    assert config.knowledge_base_dir == vault.resolve()


def test_load_config_from_file(monkeypatch, tmp_path):
    """Test loading config from .env file."""
    env_file = tmp_path / ".env"
    env_file.write_text("GITHUB_PAT_TOKEN=ghp_fromfile\nANTHROPIC_API_KEY=sk-fromfile\n")

    monkeypatch.delenv("GITHUB_PAT_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    config = load_config(env_file)

    assert config.github_pat == "ghp_fromfile"
    assert config.anthropic_api_key == "sk-fromfile"

def test_resolve_github_lists_token_prefers_env(monkeypatch):
    """Test GitHub Lists token can be separated from the REST PAT."""
    monkeypatch.setenv("GITHUB_LISTS_TOKEN", "gho_lists")

    assert resolve_github_lists_token("ghp_default") == "gho_lists"

def test_resolve_github_lists_token_falls_back_to_default_without_gh(monkeypatch):
    """Test normal PAT is used when no list-specific token is available."""
    monkeypatch.delenv("GITHUB_LISTS_TOKEN", raising=False)
    monkeypatch.setattr("src.config.shutil.which", lambda command: None)

    assert resolve_github_lists_token("ghp_default") == "ghp_default"


def test_resolve_github_lists_token_uses_gh_auth_token(monkeypatch):
    """Test gh CLI token is used when no list-specific env token is set."""
    monkeypatch.delenv("GITHUB_LISTS_TOKEN", raising=False)
    monkeypatch.setattr("src.config.shutil.which", lambda command: "/usr/bin/gh")

    def fake_run(args, capture_output, text, timeout, check):
        assert args == ["gh", "auth", "token", "--hostname", "github.com"]
        assert capture_output is True
        assert text is True
        assert timeout == 10
        assert check is True
        return CompletedProcess(args, 0, stdout="gho_lists\n")

    monkeypatch.setattr("src.config.subprocess.run", fake_run)

    assert resolve_github_lists_token("ghp_default") == "gho_lists"
