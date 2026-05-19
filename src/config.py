from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_REQUIRED = ("GITHUB_PAT_TOKEN",)
_OPTIONAL = ("ANTHROPIC_API_KEY",)
_OUTPUT_DIR_ENV = "KNOWLEDGE_BASE_DIR"
_CLONES_DIR_ENV = "CLONES_DIR"
_LOCAL_ENVRC_FILENAME = ".envrc.local"
_PASS_KEY_PATH = "ai/anthropic/api-key"

DEFAULT_LIST_BUCKETS = (
    "agent-research",
    "ai-coding-tools",
    "infrastructure",
    "personal-projects",
    "reference",
    "unsorted",
)


def _resolve_anthropic_key_from_pass() -> str:
    """Fetch the Anthropic API key from the user's `pass` vault.

    Used when `.env` overrides the shell-exported key with an empty value.
    Returns "" if `pass` is unavailable or the entry is missing.
    """
    if shutil.which("pass") is None:
        return ""
    try:
        result = subprocess.run(
            ["pass", _PASS_KEY_PATH],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip()


def _read_local_envrc_value(key: str, envrc_path: Path) -> str:
    """Read a simple export KEY=value entry from a local direnv override file."""
    if not envrc_path.exists():
        return ""

    for raw_line in envrc_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if not line.startswith(f"{key}="):
            continue

        value = line.split("=", 1)[1].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        return os.path.expandvars(value)

    return ""


def _resolve_knowledge_base_dir(env_dir: Path) -> Path:
    """Resolve the target notes directory from env or defaults."""
    output_dir = (
        os.environ.get(_OUTPUT_DIR_ENV)
        or _read_local_envrc_value(_OUTPUT_DIR_ENV, env_dir / _LOCAL_ENVRC_FILENAME)
        or str(Path.home() / "gh-stars-data")
    )
    return Path(output_dir).expanduser().resolve()


def _resolve_clones_dir(env_dir: Path) -> Path:
    """Resolve the clones directory from env or compute from workspace root."""
    clones_dir = (
        os.environ.get(_CLONES_DIR_ENV)
        or _read_local_envrc_value(_CLONES_DIR_ENV, env_dir / _LOCAL_ENVRC_FILENAME)
    )

    if clones_dir:
        return Path(clones_dir).expanduser().resolve()

    # Try workspace root one level up
    workspace = (env_dir.parent / "clones").resolve()
    if workspace.parent.name == "workspace":
        return workspace

    # Fallback
    return (Path.home() / "gh-stars-clones").resolve()


@dataclass(frozen=True)
class Config:
    github_pat: str
    anthropic_api_key: str
    knowledge_base_dir: Path
    clones_dir: Path


def load_config(env_path: Path | None = None) -> Config:
    """Load configuration from environment variables (and optional .env file)."""
    if env_path is not None:
        load_dotenv(env_path, override=True)
        env_dir = env_path.parent
    else:
        load_dotenv(override=True)
        env_dir = Path.cwd()

    # Try to fill ANTHROPIC_API_KEY from pass if not set
    if not os.environ.get("ANTHROPIC_API_KEY"):
        key = _resolve_anthropic_key_from_pass()
        if key:
            os.environ["ANTHROPIC_API_KEY"] = key

    missing = [key for key in _REQUIRED if not os.environ.get(key)]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    return Config(
        github_pat=os.environ["GITHUB_PAT_TOKEN"],
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        knowledge_base_dir=_resolve_knowledge_base_dir(env_dir),
        clones_dir=_resolve_clones_dir(env_dir),
    )
