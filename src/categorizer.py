from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import anthropic

from src.config import DEFAULT_LIST_BUCKETS
from src.models import CategorizedRepo, StarredRepo

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 8192
_BATCH_SIZE = 25

_FRONTMATTER_CATEGORY_RE = re.compile(r'^category:\s*"(.+)"', re.MULTILINE)
_FRONTMATTER_SUBCATEGORY_RE = re.compile(r'^subCategory:\s*"(.+)"', re.MULTILINE)
_FRONTMATTER_LIST_RE = re.compile(r'^list:\s*"(.+)"', re.MULTILINE)


def read_existing_taxonomy(output_dir: Path) -> tuple[dict[str, set[str]], set[str]]:
    """Scan *.md frontmatter for existing category/subCategory and list values.

    Returns:
        (categories_dict, list_set) where categories_dict maps category -> {subcategories}
        and list_set contains all existing list values.
    """
    categories: dict[str, set[str]] = {}
    lists: set[str] = set()

    if not output_dir.exists():
        return categories, lists

    # Scan active notes
    for md_file in output_dir.glob("*.md"):
        content = md_file.read_text()
        cat_match = _FRONTMATTER_CATEGORY_RE.search(content)
        sub_match = _FRONTMATTER_SUBCATEGORY_RE.search(content)
        list_match = _FRONTMATTER_LIST_RE.search(content)

        if cat_match and sub_match:
            cat = cat_match.group(1)
            sub = sub_match.group(1)
            categories.setdefault(cat, set()).add(sub)

        if list_match:
            lists.add(list_match.group(1))

    # Scan archive too (for vocabulary, not enforcement)
    archive = output_dir / "archive"
    if archive.exists():
        for md_file in archive.glob("*.md"):
            content = md_file.read_text()
            list_match = _FRONTMATTER_LIST_RE.search(content)
            if list_match:
                lists.add(list_match.group(1))

    return categories, lists


def _build_taxonomy_block(categories: dict[str, set[str]]) -> str:
    """Format existing categories/subcategories for the prompt."""
    lines: list[str] = []
    for category, subs in sorted(categories.items()):
        lines.append(f"- {category}")
        for sub in sorted(subs):
            lines.append(f"  - {sub}")
    return "\n".join(lines)


def _build_list_block(lists: set[str], default_buckets: tuple[str, ...]) -> str:
    """Format existing and default lists for the prompt."""
    all_lists = set(default_buckets) | lists
    return ", ".join(sorted(all_lists))


def _build_system_prompt(
    categories: dict[str, set[str]], lists: set[str], default_buckets: tuple[str, ...]
) -> str:
    """Build the categorization system prompt."""
    if categories:
        taxonomy_section = (
            f"Existing categories and subcategories in the vault:\n"
            f"{_build_taxonomy_block(categories)}\n\n"
            "Rules:\n"
            "- Prefer the existing categories and subcategories listed above.\n"
            "- If a repo fits an existing category but needs a new subcategory, add it.\n"
            "- If no existing category fits, create a new one in Title Case.\n"
            "- New category names: 2-4 words, Title Case, must not duplicate existing ones.\n"
            "- Do NOT use \"General\" or \"Uncategorized\" — every repo deserves meaningful categorization."
        )
    else:
        taxonomy_section = (
            "No existing categories yet — this is the first run.\n\n"
            "Rules:\n"
            "- Create meaningful categories in Title Case (e.g., \"AI Frameworks\", \"DevOps Tools\").\n"
            "- Each category must have exactly one subcategory per repo, also in Title Case.\n"
            "- Keep names concise (2-4 words). Group related repos under the same category.\n"
            "- Do NOT use \"General\" or \"Uncategorized\" — every repo deserves meaningful categorization."
        )

    lists_section = (
        f"Project lists (preferred values, may extend):\n{_build_list_block(lists, default_buckets)}\n\n"
        "Rules:\n"
        "- Assign each repo to exactly one list.\n"
        "- Prefer values above, but create a new lowercase-kebab-case list if none fit.\n"
    )

    return (
        "You are a GitHub repository categorizer. Given a JSON array of repos, "
        "assign each one to category, subCategory, and list.\n\n"
        f"{taxonomy_section}\n\n"
        f"{lists_section}\n\n"
        "Response format (ONLY JSON, no other text):\n"
        '[{"repo_id": 123, "category": "AI Frameworks", "subCategory": "LLM Agents", "list": "ai-coding-tools"}, ...]'
    )


def _build_payload(repos: list[StarredRepo]) -> str:
    """Build JSON payload for Claude."""
    entries = []
    for repo in repos:
        entry = {
            "repo_id": repo.repo_id,
            "repo": f"{repo.owner}/{repo.name}",
            "description": repo.description or "",
            "language": repo.language or "",
            "stars": repo.stars,
            "license": repo.license or "",
            "topics": repo.topics,
        }
        entries.append(entry)
    return json.dumps(entries)


async def categorize_repos(
    repos: list[StarredRepo],
    output_dir: Path,
    api_key: str,
) -> list[CategorizedRepo]:
    """Categorize a list of repos using Claude, returning CategorizedRepo objects."""
    if not repos:
        return []

    categories, lists = read_existing_taxonomy(output_dir)
    system_prompt = _build_system_prompt(categories, lists, DEFAULT_LIST_BUCKETS)

    client = anthropic.Anthropic(api_key=api_key)
    payload = _build_payload(repos)

    logger.info(f"Categorizing {len(repos)} repos with Claude...")

    message = client.messages.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": f"Categorize these repos:\n\n{payload}",
            }
        ],
    )

    response_text = message.content[0].text

    # Parse response
    try:
        parsed = json.loads(response_text)
        if not isinstance(parsed, list):
            raise ValueError("response is not a list")
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse Claude response: {e}")
        logger.error(f"Response text: {response_text}")
        # Return fallback categorization
        return [
            CategorizedRepo(
                repo=repo,
                category="General",
                sub_category="Uncategorized",
                list="unsorted",
            )
            for repo in repos
        ]

    result = []
    for item in parsed:
        repo_id = item.get("repo_id")
        repo = next((r for r in repos if r.repo_id == repo_id), None)
        if not repo:
            logger.warning(f"repo_id {repo_id} not found in input list")
            continue

        result.append(
            CategorizedRepo(
                repo=repo,
                category=item.get("category", "General"),
                sub_category=item.get("subCategory", "Uncategorized"),
                list=item.get("list", "unsorted"),
            )
        )

    return result
