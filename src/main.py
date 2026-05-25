from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from src.api_client import GitHubClient
from src.categorizer import categorize_repos
from src.cloner import reconcile_clones
from src.config import load_config
from src.markdown_writer import read_existing_ids, write_repo_note
from src.removal import remove_candidates, scan_unstar_notes

logger = logging.getLogger(__name__)

_HISTORY_FILENAME = ".gh-stars-history.jsonl"


def _setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _input_yes_no(prompt: str) -> bool:
    """Prompt user for yes/no confirmation."""
    while True:
        response = input(f"{prompt} (yes/no): ").strip().lower()
        if response in ("yes", "y"):
            return True
        if response in ("no", "n"):
            return False
        print("Please answer 'yes' or 'no'.")


async def _sync_command(
    config_path: Path | None = None,
    max_repos: int | None = None,
    dry_run: bool = False,
    yes: bool = False,
    verbose: bool = False,
) -> None:
    """Fetch repos, categorize, write notes, reconcile clones."""
    _setup_logging(verbose)
    logger.info("Starting sync...")

    config = load_config(config_path)
    notes_dir = config.knowledge_base_dir / "09_feeds" / "gh-stars"
    clones_dir = config.clones_dir

    # Read existing repo IDs (dedup key)
    existing_ids = read_existing_ids(notes_dir)
    logger.info(f"Found {len(existing_ids)} existing repo IDs")

    # Fetch starred repos
    client = GitHubClient(config.github_pat)
    all_repos = []
    async for repo in client.list_starred_repos():
        all_repos.append(repo)

    logger.info(f"Fetched {len(all_repos)} starred repos from GitHub")

    # Filter novel repos
    novel_repos = [r for r in all_repos if r.repo_id not in existing_ids]
    logger.info(f"Found {len(novel_repos)} novel repos")

    if max_repos:
        novel_repos = novel_repos[:max_repos]
        logger.info(f"Limited to {len(novel_repos)} repos (--max-repos {max_repos})")

    if dry_run:
        logger.info("DRY RUN: would process the following repos:")
        for repo in novel_repos[:10]:
            logger.info(f"  {repo.owner}/{repo.name}")
        if len(novel_repos) > 10:
            logger.info(f"  ... and {len(novel_repos) - 10} more")
        return

    # Categorization requires the Anthropic key; check now that we know we'll call Claude.
    if not config.anthropic_api_key:
        logger.error("ANTHROPIC_API_KEY not set; cannot categorize")
        return

    # Plan-and-confirm if >100 novel repos
    if len(novel_repos) > 100 and not yes:
        estimated_tokens = len(novel_repos) * 1500  # rough estimate
        estimated_cost = (estimated_tokens / 1_000_000) * 3  # $3 per 1M tokens
        print(
            f"\nPlanned: {len(novel_repos)} repos, est. ~{estimated_tokens:,} tokens = ${estimated_cost:.2f}"
        )
        if not _input_yes_no("Continue with categorization?"):
            logger.info("Sync cancelled by user")
            return

    # Fetch READMEs and categorize in batches
    from src.categorizer import _BATCH_SIZE

    files_written = 0
    for batch_start in range(0, len(novel_repos), _BATCH_SIZE):
        batch_end = min(batch_start + _BATCH_SIZE, len(novel_repos))
        batch_repos = novel_repos[batch_start:batch_end]

        batch_num = batch_start // _BATCH_SIZE + 1
        total_batches = (len(novel_repos) + _BATCH_SIZE - 1) // _BATCH_SIZE

        logger.info(f"Batch {batch_num}/{total_batches}: fetching READMEs and categorizing...")

        # Fetch READMEs for this batch
        readmes = {}
        for repo in batch_repos:
            try:
                readme = await client.fetch_readme(repo.owner, repo.name)
                readmes[repo.repo_id] = readme
            except Exception as e:
                logger.warning(f"Failed to fetch README for {repo.owner}/{repo.name}: {e}")
                readmes[repo.repo_id] = None

        # Categorize
        categorized_list = await categorize_repos(
            batch_repos, notes_dir, config.anthropic_api_key, readmes
        )

        # Write notes
        for categorized in categorized_list:
            readme = readmes.get(categorized.repo.repo_id)
            await write_repo_note(notes_dir, categorized.repo, categorized, readme)
            files_written += 1

        logger.info(f"Batch {batch_num}/{total_batches}: wrote {len(categorized_list)} notes")

    # Reconcile clones
    logger.info("Reconciling clones...")
    clone_stats = await reconcile_clones(notes_dir, clones_dir)
    logger.info(
        f"Clone reconciliation: "
        f"{clone_stats.cloned} cloned, {clone_stats.skipped_existing} skipped, "
        f"{clone_stats.failed} failed"
    )

    # Append to history
    history_path = notes_dir / _HISTORY_FILENAME
    run_record = {
        "run_id": str(uuid4()),
        "status": "completed",
        "started_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "output_dir": str(notes_dir),
        "counters": {
            "fetched": len(all_repos),
            "skipped_existing": len(existing_ids),
            "novel": len(novel_repos),
        },
        "output": {"files_written": files_written},
    }
    notes_dir.mkdir(parents=True, exist_ok=True)
    with open(history_path, "a") as f:
        f.write(json.dumps(run_record) + "\n")

    logger.info(f"Sync complete: wrote {files_written} notes")


async def _remove_unstarred_command(
    config_path: Path | None = None,
    verbose: bool = False,
) -> None:
    """Scan for unstar: true and remove repos."""
    _setup_logging(verbose)
    logger.info("Starting unstar removal...")

    config = load_config(config_path)
    notes_dir = config.knowledge_base_dir / "09_feeds" / "gh-stars"

    client = GitHubClient(config.github_pat)

    # Scan for unstar: true
    scan = scan_unstar_notes(notes_dir)
    logger.info(f"Found {len(scan.eligible)} eligible repos for unstar")

    if not scan.eligible:
        logger.info("No repos to unstar")
        return

    # Confirm and remove
    async def confirm_callback(repos: list[str]) -> bool:
        print("\nRepos to unstar:")
        for repo in repos:
            print(f"  - {repo}")
        return _input_yes_no("\nUnstar these repos?")

    stats = await remove_candidates(client, notes_dir, scan.eligible, confirm_callback)

    logger.info(
        f"Removal complete: "
        f"{stats.removed} unstarred, {stats.archived} archived, {stats.failed} failed"
    )

    # Append to history
    history_path = notes_dir / _HISTORY_FILENAME
    run_record = {
        "run_id": str(uuid4()),
        "status": "completed",
        "started_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "output_dir": str(notes_dir),
        "counters": {
            "eligible": stats.eligible,
            "removed": stats.removed,
            "archived": stats.archived,
        },
    }
    notes_dir.mkdir(parents=True, exist_ok=True)
    with open(history_path, "a") as f:
        f.write(json.dumps(run_record) + "\n")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch starred GitHub repos, categorize with Claude, write to Obsidian vault"
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to .env file (default: auto-detect)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Default: sync
    sync_parser = subparsers.add_parser("sync", help="Fetch and categorize repos (default)")
    sync_parser.add_argument(
        "--max-repos",
        type=int,
        default=None,
        help="Limit processing to N repos (for testing)",
    )
    sync_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch only, do not categorize or write",
    )
    sync_parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt for >100 repos",
    )

    # Removal
    removal_parser = subparsers.add_parser(
        "remove-unstarred",
        help="Unstar repos marked with unstar: true",
    )

    # Clone reconciliation
    clone_parser = subparsers.add_parser(
        "reconcile-clones",
        help="Reconcile cloned: true with on-disk checkouts",
    )

    args = parser.parse_args()

    if args.command == "remove-unstarred":
        asyncio.run(_remove_unstarred_command(args.config, args.verbose))
    elif args.command == "reconcile-clones":
        config = load_config(args.config)
        notes_dir = config.knowledge_base_dir / "09_feeds" / "gh-stars"
        stats = asyncio.run(reconcile_clones(notes_dir, config.clones_dir))
        logger.info(
            f"Clone reconciliation: {stats.cloned} cloned, {stats.skipped_existing} skipped"
        )
    else:
        # Default: sync
        asyncio.run(
            _sync_command(
                args.config,
                getattr(args, "max_repos", None),
                getattr(args, "dry_run", False),
                getattr(args, "yes", False),
                args.verbose,
            )
        )


if __name__ == "__main__":
    main()
