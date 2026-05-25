from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class MatrixRow:
    category: str
    sub_category: str
    count: int
    tags: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class TaxonomyMatrix:
    feed_dir: Path
    total_notes: int
    rows: tuple[MatrixRow, ...]
    tags: tuple[tuple[str, int], ...]
    skipped_files: tuple[str, ...]


def resolve_feed_dir(path: Path | None = None) -> Path:
    """Resolve a gh-stars feed directory without requiring secrets."""
    if path is not None:
        candidate = path.expanduser().resolve()
        nested = candidate / "09_feeds" / "gh-stars"
        return nested if nested.exists() else candidate

    env_vault = os.environ.get("KNOWLEDGE_BASE_DIR")
    if env_vault:
        return (Path(env_vault).expanduser().resolve() / "09_feeds" / "gh-stars")

    cwd = Path.cwd().resolve()
    candidates = (
        cwd.parent / "knowledge" / "09_feeds" / "gh-stars",
        cwd / "knowledge" / "09_feeds" / "gh-stars",
        Path.home() / "gh-stars-data" / "09_feeds" / "gh-stars",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0]


def scan_taxonomy_matrix(feed_dir: Path) -> TaxonomyMatrix:
    """Read active gh-stars notes and summarize category/subCategory/tag usage."""
    matrix: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    row_counts: Counter[tuple[str, str]] = Counter()
    tag_counts: Counter[str] = Counter()
    skipped_files: list[str] = []
    total_notes = 0

    if not feed_dir.exists():
        return TaxonomyMatrix(feed_dir, 0, (), (), (f"missing feed directory: {feed_dir}",))

    for note_path in sorted(feed_dir.glob("*.md")):
        if note_path.name == "README.md":
            continue

        frontmatter = _extract_frontmatter(note_path.read_text())
        if not frontmatter:
            skipped_files.append(note_path.name)
            continue

        parsed = yaml.safe_load(frontmatter) or {}
        if not isinstance(parsed, dict) or "repo_id" not in parsed:
            skipped_files.append(note_path.name)
            continue

        category = _clean_value(parsed.get("category"), "Uncategorized")
        sub_category = _clean_value(parsed.get("subCategory"), "Uncategorized")
        tags = _clean_tags(parsed.get("tags"))

        total_notes += 1
        key = (category, sub_category)
        row_counts[key] += 1
        matrix[key].update(tags)
        tag_counts.update(tags)

    rows = tuple(
        MatrixRow(
            category=category,
            sub_category=sub_category,
            count=row_counts[(category, sub_category)],
            tags=tuple(sorted(matrix[(category, sub_category)].items())),
        )
        for category, sub_category in sorted(row_counts)
    )
    return TaxonomyMatrix(
        feed_dir=feed_dir,
        total_notes=total_notes,
        rows=rows,
        tags=tuple(sorted(tag_counts.items())),
        skipped_files=tuple(skipped_files),
    )


def render_markdown(matrix: TaxonomyMatrix, *, tag_limit: int = 8) -> str:
    """Render a taxonomy matrix as Markdown."""
    lines = [
        "# gh-stars Taxonomy Matrix",
        "",
        f"Feed: `{matrix.feed_dir}`",
        f"Total repo notes: {matrix.total_notes}",
        "",
        "| Category | Subcategory | Notes | Tags |",
        "|---|---|---:|---|",
    ]

    for row in matrix.rows:
        lines.append(
            "| "
            f"{_escape_table(row.category)} | "
            f"{_escape_table(row.sub_category)} | "
            f"{row.count} | "
            f"{_escape_table(_format_tag_counts(row.tags, tag_limit=tag_limit))} |"
        )

    lines.extend(["", "## Tags", "", "| Tag | Notes |", "|---|---:|"])
    for tag, count in matrix.tags:
        lines.append(f"| `{_escape_table(tag)}` | {count} |")

    if matrix.skipped_files:
        lines.extend(["", "## Skipped Files", ""])
        lines.extend(f"- `{name}`" for name in matrix.skipped_files)

    return "\n".join(lines) + "\n"


def render_json(matrix: TaxonomyMatrix) -> str:
    """Render a taxonomy matrix as stable JSON."""
    payload: dict[str, Any] = {
        "feed_dir": str(matrix.feed_dir),
        "total_notes": matrix.total_notes,
        "matrix": [
            {
                "category": row.category,
                "subCategory": row.sub_category,
                "count": row.count,
                "tags": [{"tag": tag, "count": count} for tag, count in row.tags],
            }
            for row in matrix.rows
        ],
        "tags": [{"tag": tag, "count": count} for tag, count in matrix.tags],
        "skipped_files": list(matrix.skipped_files),
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_terminal_table(matrix: TaxonomyMatrix) -> str:
    """Render a compact fixed-width summary table for terminal output."""
    rows = [
        (row.category, row.sub_category, str(row.count))
        for row in sorted(matrix.rows, key=lambda item: (-item.count, item.category, item.sub_category))
    ]
    headers = ("Category", "Subcategory", "Notes")
    all_rows = [headers, *rows]
    widths = tuple(max(len(row[idx]) for row in all_rows) for idx in range(3))

    lines = [
        f"Feed: {matrix.feed_dir}",
        f"Total repo notes: {matrix.total_notes}",
        "",
        _format_terminal_row(headers, widths),
        _format_terminal_row(tuple("-" * width for width in widths), widths),
    ]
    lines.extend(_format_terminal_row(row, widths) for row in rows)

    if matrix.tags:
        lines.extend(["", "Top tags:"])
        for tag, count in sorted(matrix.tags, key=lambda item: (-item[1], item[0]))[:10]:
            lines.append(f"  {tag:<24} {count:>4}")

    if matrix.skipped_files:
        lines.extend(["", f"Skipped files: {len(matrix.skipped_files)}"])

    return "\n".join(lines) + "\n"


def _extract_frontmatter(content: str) -> str:
    if not content.startswith("---\n"):
        return ""
    end = content.find("\n---", 4)
    if end == -1:
        return ""
    return content[4:end]


def _clean_value(raw: object, fallback: str) -> str:
    if not isinstance(raw, str):
        return fallback
    value = raw.strip()
    return value or fallback


def _clean_tags(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    return tuple(sorted({tag.strip() for tag in raw if isinstance(tag, str) and tag.strip()}))


def _format_tag_counts(tags: tuple[tuple[str, int], ...], *, tag_limit: int) -> str:
    if not tags:
        return ""

    sorted_tags = sorted(tags, key=lambda item: (-item[1], item[0]))
    if tag_limit > 0:
        shown = sorted_tags[:tag_limit]
        hidden = len(sorted_tags) - len(shown)
    else:
        shown = sorted_tags
        hidden = 0

    rendered = ", ".join(f"`{tag}` ({count})" for tag, count in shown)
    if hidden:
        rendered = f"{rendered}, +{hidden} more"
    return rendered


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|")


def _format_terminal_row(row: tuple[str, str, str], widths: tuple[int, int, int]) -> str:
    return f"{row[0]:<{widths[0]}}  {row[1]:<{widths[1]}}  {row[2]:>{widths[2]}}"
