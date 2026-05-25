from __future__ import annotations

import logging
import os
import re
import tempfile
from pathlib import Path

from src.models import CategorizedRepo, StarredRepo

logger = logging.getLogger(__name__)

_REPO_ID_PATTERN = re.compile(r'^repo_id:\s*(\d+)', re.MULTILINE)


def _extract_frontmatter(content: str) -> str:
    """Return YAML frontmatter only, ignoring README examples and body content."""
    if not content.startswith("---\n"):
        return ""
    end = content.find("\n---", 4)
    if end == -1:
        return ""
    return content[4:end]


def read_existing_ids(output_dir: Path) -> set[int]:
    """Scan *.md frontmatter for repo_id in active and archive folders.

    CRITICAL: Archive scan ensures re-starring an archived repo does not produce duplicates.
    """
    all_ids: set[int] = set()

    if not output_dir.exists():
        return all_ids

    # Scan active notes
    for md_file in output_dir.glob("*.md"):
        frontmatter = _extract_frontmatter(md_file.read_text())
        match = _REPO_ID_PATTERN.search(frontmatter)
        if match:
            all_ids.add(int(match.group(1)))

    # Scan archive too (non-negotiable for dedup)
    archive = output_dir / "archive"
    if archive.exists():
        for md_file in archive.glob("*.md"):
            frontmatter = _extract_frontmatter(md_file.read_text())
            match = _REPO_ID_PATTERN.search(frontmatter)
            if match:
                all_ids.add(int(match.group(1)))

    return all_ids

def _escape_yaml_string(value: str) -> str:
    """Escape a string for YAML double-quoted scalar."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _build_frontmatter(repo: StarredRepo, categorized: CategorizedRepo) -> str:
    """Build YAML frontmatter with all metadata fields."""
    title = _escape_yaml_string(repo.name)
    description = _escape_yaml_string(repo.description or "")
    language = _escape_yaml_string(repo.language or "")
    category = _escape_yaml_string(categorized.category)
    sub_category = _escape_yaml_string(categorized.sub_category)
    tags = ", ".join(f'"{_escape_yaml_string(tag)}"' for tag in categorized.tags)

    date_str = repo.starred_at.isoformat()

    lines = [
        "---",
        f'title: "{title}"',
        f'repo: "{repo.owner}/{repo.name}"',
        f"repo_id: {repo.repo_id}",
        f'description: "{description}"',
        f'category: "{category}"',
        f'subCategory: "{sub_category}"',
        f"tags: [{tags}]",
        f'language: "{language}"',
        f"stars: {repo.stars}",
        f'starred_at: {date_str}',
        f'repo_url: "{repo.repo_url}"',
        'cloned: false',
        'unstar: false',
        "---",
    ]

    return "\n".join(lines) + "\n"


def _build_body(repo: StarredRepo, readme: str | None) -> str:
    """Build markdown body with repo metadata and README."""
    lines = [
        f"## {repo.owner}/{repo.name}",
        "",
    ]

    if repo.description:
        lines.append(f"> {repo.description}")
        lines.append("")

    stars_formatted = f"{repo.stars:,}" if repo.stars else "0"
    lines.append(
        f"**Language:** {repo.language or 'Unknown'} | "
        f"**Stars:** {stars_formatted} | "
        f"**Starred:** {repo.starred_at}"
    )
    lines.append("")
    lines.append("## README")
    lines.append("")

    if readme:
        lines.append(readme)
    else:
        lines.append("*No README available*")

    lines.append("")
    lines.append("## References")
    lines.append("")
    lines.append(f"- 🔗 [Repository]({repo.repo_url})")

    if repo.homepage:
        lines.append(f"- 🌐 [Homepage]({repo.homepage})")

    return "\n".join(lines) + "\n"


def _sanitize_filename(owner: str, repo: str) -> str:
    """Convert {owner}/{repo} to safe filename: karpathy-llm-wiki.md"""
    return f"{owner}-{repo}".replace("/", "-") + ".md"


async def write_repo_note(
    output_dir: Path,
    repo: StarredRepo,
    categorized: CategorizedRepo,
    readme: str | None,
) -> Path:
    """Write repo note atomically (tempfile + os.replace).

    Returns the path to the written file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = _sanitize_filename(repo.owner, repo.name)
    target_path = output_dir / filename

    frontmatter = _build_frontmatter(repo, categorized)
    body = _build_body(repo, readme)
    content = frontmatter + body

    # Atomic write: tempfile in same dir, then replace
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=output_dir,
        delete=False,
        suffix=".md",
        encoding="utf-8",
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        os.replace(tmp_path, target_path)
        logger.debug(f"Wrote {target_path}")
    except Exception as e:
        os.unlink(tmp_path)
        raise e

    return target_path
