#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path

from src.taxonomy_matrix import (
    render_json,
    render_markdown,
    render_terminal_table,
    resolve_feed_dir,
    scan_taxonomy_matrix,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Report category/subCategory/tag usage in the gh-stars feed."
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        help="Optional feed directory or vault root. Defaults to the workspace knowledge feed.",
    )
    parser.add_argument(
        "--format",
        choices=("table", "markdown", "json"),
        default="table",
        help="Output format.",
    )
    parser.add_argument(
        "--tag-limit",
        type=int,
        default=8,
        help="Max tags shown per matrix row in Markdown. Use 0 for all tags.",
    )

    args = parser.parse_args()
    matrix = scan_taxonomy_matrix(resolve_feed_dir(args.path))
    if args.format == "json":
        print(render_json(matrix), end="")
    elif args.format == "markdown":
        print(render_markdown(matrix, tag_limit=args.tag_limit), end="")
    else:
        print(render_terminal_table(matrix), end="")


if __name__ == "__main__":
    main()
