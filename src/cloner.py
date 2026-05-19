from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

from src.models import CloneStats

logger = logging.getLogger(__name__)

_REPO_PATTERN = re.compile(r'^repo:\s*"([^/]+)/([^"]+)"', re.MULTILINE)
_CLONED_PATTERN = re.compile(r'^cloned:\s*(.+)$', re.MULTILINE)


async def reconcile_clones(notes_dir: Path, clones_dir: Path) -> CloneStats:
    """Reconcile cloned: true notes with on-disk clones.

    For each active note with cloned: true and no on-disk checkout,
    run `git clone --depth=1` to create the clone.

    Returns stats on attempted/cloned/skipped/failed operations.
    """
    attempted = 0
    cloned = 0
    skipped_existing = 0
    failed = 0
    warnings: list[str] = []

    if not notes_dir.exists():
        logger.info(f"Notes dir {notes_dir} does not exist; skipping clone reconciliation")
        return CloneStats(0, 0, 0, 0, tuple(warnings))

    clones_dir.mkdir(parents=True, exist_ok=True)

    # Scan active notes (not archive)
    for md_file in notes_dir.glob("*.md"):
        if md_file.parent.name == "archive":
            continue

        content = md_file.read_text()

        # Extract repo and cloned status
        repo_match = _REPO_PATTERN.search(content)
        cloned_match = _CLONED_PATTERN.search(content)

        if not repo_match or not cloned_match:
            continue

        owner, repo = repo_match.groups()
        cloned_val = cloned_match.group(1).strip().lower()

        if cloned_val != "true":
            continue

        attempted += 1
        clone_dir = clones_dir / f"{owner}-{repo}"
        git_dir = clone_dir / ".git"

        if git_dir.exists():
            logger.debug(f"Clone already exists: {clone_dir}")
            skipped_existing += 1
            continue

        repo_url = f"https://github.com/{owner}/{repo}.git"
        logger.info(f"Cloning {repo_url} to {clone_dir}...")

        try:
            result = subprocess.run(
                ["git", "clone", "--depth=1", repo_url, str(clone_dir)],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                logger.info(f"Cloned {owner}/{repo}")
                cloned += 1
            else:
                msg = f"Clone failed for {owner}/{repo}: {result.stderr}"
                logger.error(msg)
                warnings.append(msg)
                failed += 1
        except subprocess.TimeoutExpired:
            msg = f"Clone timeout for {owner}/{repo}"
            logger.error(msg)
            warnings.append(msg)
            failed += 1
        except Exception as e:
            msg = f"Clone error for {owner}/{repo}: {e}"
            logger.error(msg)
            warnings.append(msg)
            failed += 1

    return CloneStats(
        attempted=attempted,
        cloned=cloned,
        skipped_existing=skipped_existing,
        failed=failed,
        warnings=tuple(warnings),
    )
