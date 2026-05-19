from __future__ import annotations

import logging
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from src.api_client import GitHubClient, UnstarRateLimitError, UnstarScopeError

logger = logging.getLogger(__name__)

_UNSTAR_PATTERN = re.compile(r"^unstar:\s*(.+)$", re.MULTILINE)
_REPO_PATTERN = re.compile(r'^repo:\s*"([^/]+)/([^"]+)"', re.MULTILINE)
_MAX_LIVE_REMOVALS = 50


@dataclass(frozen=True)
class RemovalCandidate:
    filepath: Path
    owner: str
    repo: str


@dataclass(frozen=True)
class ScanResult:
    eligible: tuple[RemovalCandidate, ...]
    skipped: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class RemovalStats:
    eligible: int
    attempted: int
    removed: int
    archived: int
    skipped: int
    failed: int
    removed_repos: tuple[str, ...]
    failed_repos: tuple[dict[str, str], ...]
    warnings: tuple[str, ...]


def scan_unstar_notes(output_dir: Path) -> ScanResult:
    """Scan active notes for unstar: true."""
    eligible: list[RemovalCandidate] = []
    skipped = 0
    warnings: list[str] = []

    if not output_dir.exists():
        return ScanResult(tuple(eligible), skipped, tuple(warnings))

    for md_file in output_dir.glob("*.md"):
        if md_file.parent.name == "archive":
            continue

        content = md_file.read_text()

        unstar_match = _UNSTAR_PATTERN.search(content)
        if not unstar_match:
            skipped += 1
            continue

        unstar_val = unstar_match.group(1).strip().lower()
        if unstar_val != "true":
            skipped += 1
            continue

        repo_match = _REPO_PATTERN.search(content)
        if not repo_match:
            msg = f"Could not extract repo from {md_file.name}"
            logger.warning(msg)
            warnings.append(msg)
            skipped += 1
            continue

        owner, repo = repo_match.groups()
        eligible.append(RemovalCandidate(filepath=md_file, owner=owner, repo=repo))

    return ScanResult(tuple(eligible), skipped, tuple(warnings))


async def remove_candidates(
    client: GitHubClient,
    output_dir: Path,
    candidates: tuple[RemovalCandidate, ...],
    confirm_callback: Callable[[list[str]], bool],
) -> RemovalStats:
    """Unstar repos and move notes to archive.

    Up to MAX_LIVE_REMOVALS per run. On rate limit, stop and report.
    On success, atomically move .md to archive/. Requires user confirmation.
    """
    if not candidates:
        return RemovalStats(0, 0, 0, 0, 0, 0, tuple(), tuple(), tuple())

    # User confirmation
    candidate_list = [f"{c.owner}/{c.repo}" for c in candidates[: min(len(candidates), 100)]]
    if not confirm_callback(candidate_list):
        logger.info("Unstar cancelled by user")
        return RemovalStats(
            eligible=len(candidates),
            attempted=0,
            removed=0,
            archived=0,
            skipped=len(candidates),
            failed=0,
            removed_repos=tuple(),
            failed_repos=tuple(),
            warnings=("User declined removal",),
        )

    attempted = 0
    removed = 0
    archived = 0
    failed = 0
    removed_repos: list[str] = []
    failed_repos: list[dict[str, str]] = []
    warnings: list[str] = []

    # Create archive dir if missing
    archive_dir = output_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    for candidate in candidates[: min(len(candidates), _MAX_LIVE_REMOVALS)]:
        attempted += 1

        try:
            await client.unstar_repo(candidate.owner, candidate.repo)
            removed += 1

            # Atomically move to archive
            archive_path = archive_dir / candidate.filepath.name
            try:
                os.replace(candidate.filepath, archive_path)
                archived += 1
                removed_repos.append(f"{candidate.owner}/{candidate.repo}")
                logger.info(f"Archived {candidate.owner}/{candidate.repo}")
            except Exception as e:
                msg = f"Failed to archive {candidate.filepath.name}: {e}"
                logger.error(msg)
                warnings.append(msg)

        except UnstarRateLimitError as e:
            logger.error(f"Rate limit hit: {e}")
            warnings.append(f"Rate limit: {e}")
            break
        except UnstarScopeError as e:
            logger.error(f"Scope error: {e}")
            failed += 1
            failed_repos.append(
                {"repo": f"{candidate.owner}/{candidate.repo}", "error": str(e)}
            )
        except Exception as e:
            logger.error(f"Failed to unstar {candidate.owner}/{candidate.repo}: {e}")
            failed += 1
            failed_repos.append(
                {"repo": f"{candidate.owner}/{candidate.repo}", "error": str(e)}
            )

    return RemovalStats(
        eligible=len(candidates),
        attempted=attempted,
        removed=removed,
        archived=archived,
        skipped=len(candidates) - attempted,
        failed=failed,
        removed_repos=tuple(removed_repos),
        failed_repos=tuple(failed_repos),
        warnings=tuple(warnings),
    )
