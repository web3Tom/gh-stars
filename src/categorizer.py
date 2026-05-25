from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import anthropic

from src.models import CategorizedRepo, StarredRepo

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 8192
_BATCH_SIZE = 25
_README_EXCERPT_CHARS = 4000
_ALLOWED_TAG_PREFIXES = frozenset({"layer", "lang"})
_PURPOSE_TAXONOMY: dict[str, tuple[str, ...]] = {
    "Core Frameworks": (
        "Agentic Orchestration",
        "Toolkits & Primitives",
        "Memory & Context",
    ),
    "Developer Tooling": (
        "Workspaces & IDEs",
        "Observability & Evals",
    ),
    "Infrastructure & Data": (
        "Ingestion & Indexing",
        "Proxies & Gateways",
    ),
    "Applied Systems": (
        "Autonomous Agents",
        "Services & Backends",
    ),
    "Knowledge & Reference": (
        "Curated Lists",
        "Learning & Cookbooks",
    ),
}
_TAG_REFERENCE: dict[str, tuple[str, ...]] = {
    "layer": ("cli", "library", "api", "desktop", "markdown"),
    "lang": ("python", "typescript", "react", "rust"),
}

_FRONTMATTER_CATEGORY_RE = re.compile(r'^category:\s*"(.+)"', re.MULTILINE)
_FRONTMATTER_SUBCATEGORY_RE = re.compile(r'^subCategory:\s*"(.+)"', re.MULTILINE)
_FRONTMATTER_TAGS_RE = re.compile(r"^tags:\s*\[(.*)\]", re.MULTILINE)
_FENCED_JSON_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL | re.IGNORECASE)


def _extract_frontmatter(content: str) -> str:
    """Return YAML frontmatter only, ignoring README examples and body content."""
    if not content.startswith("---\n"):
        return ""
    end = content.find("\n---", 4)
    if end == -1:
        return ""
    return content[4:end]


def _normalize_json_response(response_text: str) -> str:
    """Accept raw JSON or a fenced JSON block from the model."""
    text = response_text.strip()
    match = _FENCED_JSON_RE.match(text)
    if match:
        return match.group(1).strip()
    return text


def normalize_tag(raw: object, allowed_prefixes: set[str] | frozenset[str] | None = None) -> str | None:
    """Normalize a tag to prefix/slug format, dropping unknown prefixes."""
    if not isinstance(raw, str) or "/" not in raw:
        return None

    prefix, value = raw.lower().strip().split("/", 1)
    prefix = prefix.strip()
    value = value.strip()
    if not prefix or not value:
        return None
    if allowed_prefixes is not None and prefix not in allowed_prefixes:
        return None

    slug = re.sub(r"[\s_]+", "-", value)
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    if not slug:
        return None

    return f"{prefix}/{slug}"


def normalize_tags(raw_tags: object, *, require_layer: bool = False) -> tuple[str, ...]:
    """Normalize and dedupe form-facet tags."""
    result: list[str] = []
    seen: set[str] = set()
    if isinstance(raw_tags, list):
        for raw in raw_tags:
            tag = normalize_tag(raw, _ALLOWED_TAG_PREFIXES)
            if tag and tag not in seen:
                result.append(tag)
                seen.add(tag)

    if require_layer and not any(tag.startswith("layer/") for tag in result):
        result.insert(0, "layer/library")

    return tuple(result)

def _language_tag(repo: StarredRepo) -> str | None:
    if not repo.language:
        return None
    return normalize_tag(f"lang/{repo.language}")

def _enforce_repo_language(repo: StarredRepo, tags: tuple[str, ...]) -> tuple[str, ...]:
    """Trust GitHub's primary language over model-inferred language tags."""
    language_tag = _language_tag(repo)
    if not language_tag:
        return tags

    result = [tag for tag in tags if not tag.startswith("lang/")]
    result.append(language_tag)
    return normalize_tags(result, require_layer=True)


def _parse_frontmatter_tags(frontmatter: str) -> set[str]:
    match = _FRONTMATTER_TAGS_RE.search(frontmatter)
    if not match:
        return set()
    raw_values = re.findall(r'"([^"]+)"', match.group(1))
    return set(normalize_tags(raw_values))


def read_existing_taxonomy(output_dir: Path) -> tuple[dict[str, set[str]], set[str]]:
    """Scan *.md frontmatter for existing category/subCategory and tag values.

    Returns:
        (categories_dict, tag_set) where categories_dict maps category -> {subcategories}.
    """
    categories: dict[str, set[str]] = {}
    tags: set[str] = set()

    if not output_dir.exists():
        return categories, tags

    # Scan active notes
    for md_file in output_dir.glob("*.md"):
        frontmatter = _extract_frontmatter(md_file.read_text())
        cat_match = _FRONTMATTER_CATEGORY_RE.search(frontmatter)
        sub_match = _FRONTMATTER_SUBCATEGORY_RE.search(frontmatter)

        if cat_match and sub_match:
            cat = cat_match.group(1)
            sub = sub_match.group(1)
            categories.setdefault(cat, set()).add(sub)

        tags.update(_parse_frontmatter_tags(frontmatter))

    # Scan archive too (for tag vocabulary, not category enforcement)
    archive = output_dir / "archive"
    if archive.exists():
        for md_file in archive.glob("*.md"):
            frontmatter = _extract_frontmatter(md_file.read_text())
            tags.update(_parse_frontmatter_tags(frontmatter))

    return categories, tags


def _build_taxonomy_block(categories: dict[str, set[str]]) -> str:
    """Format existing categories/subcategories for the prompt."""
    lines: list[str] = []
    for category, subs in sorted(categories.items()):
        lines.append(f"- {category}")
        for sub in sorted(subs):
            lines.append(f"  - {sub}")
    return "\n".join(lines)


def _build_purpose_taxonomy_block() -> str:
    lines: list[str] = []
    for category, subcategories in _PURPOSE_TAXONOMY.items():
        lines.append(f"- {category}")
        for subcategory in subcategories:
            lines.append(f"  - {subcategory}")
    return "\n".join(lines)


def _build_tag_reference_block(existing_tags: set[str]) -> str:
    lines: list[str] = []
    for prefix, values in _TAG_REFERENCE.items():
        known_values = sorted({*values, *(tag.split("/", 1)[1] for tag in existing_tags if tag.startswith(f"{prefix}/"))})
        lines.append(f"- {prefix}: {', '.join(known_values)}")
    return "\n".join(lines)


def _build_system_prompt(
    categories: dict[str, set[str]],
    tags: set[str],
) -> str:
    """Build the categorization system prompt."""
    existing_taxonomy = ""
    if categories:
        existing_taxonomy = (
            "\nExisting vault categories/subcategories, for reuse when compatible:\n"
            f"{_build_taxonomy_block(categories)}\n"
        )

    return (
        "You are a GitHub repository categorizer. Given a JSON array of repos, "
        "assign each one to category, subCategory, and tags.\n\n"
        "Strict boundary:\n"
        "- category and subCategory describe Purpose: what problem the repository solves.\n"
        "- tags describe Form: how the repository is packaged, consumed, and implemented.\n"
        "- Do not use category names with numeric prefixes such as 01, 02, etc.\n\n"
        "Purpose taxonomy. Prefer exactly these category/subCategory pairs:\n"
        f"{_build_purpose_taxonomy_block()}\n"
        f"{existing_taxonomy}\n"
        "Rules:\n"
        "- Pick exactly one category and one subCategory per repo.\n"
        "- Prefer the Purpose taxonomy above over inventing new categories.\n"
        "- Do NOT use \"General\" or \"Uncategorized\".\n\n"
        "Tag taxonomy for Form facets only:\n"
        f"{_build_tag_reference_block(tags)}\n\n"
        "Tag rules:\n"
        "- Return tags as an array of strings using prefix/value format.\n"
        "- Use at least one layer/ tag for every repo.\n"
        "- Use lang/ when implementation language is clear.\n"
        "- Do not emit entity relationship tags such as model/, provider/, tool/, framework/, or concept/.\n"
        "- Tags should describe package form and consumption surface, not duplicate the purpose category.\n\n"
        "Response format (ONLY JSON, no other text):\n"
        '[{"repo_id": 123, "category": "Core Frameworks", "subCategory": "Agentic Orchestration", "tags": ["layer/library", "lang/python"]}, ...]'
    )


def _readme_excerpt(readme: str | None) -> str:
    if not readme:
        return ""
    readme = readme.strip()
    if len(readme) <= _README_EXCERPT_CHARS:
        return readme
    return readme[:_README_EXCERPT_CHARS] + "\n... [README excerpt truncated]"


def _fallback_tags(repo: StarredRepo) -> tuple[str, ...]:
    tags: list[str] = []
    topic_text = " ".join(repo.topics).lower()
    description = (repo.description or "").lower()
    name = repo.name.lower()

    if "awesome" in name or "list" in description:
        tags.append("layer/markdown")
    elif "cli" in topic_text or "terminal" in description:
        tags.append("layer/cli")
    elif repo.homepage:
        tags.append("layer/api")
    else:
        tags.append("layer/library")

    language = _language_tag(repo)
    if language:
        tags.append(language)

    return normalize_tags(tags, require_layer=True)


def _build_payload(repos: list[StarredRepo], readmes: dict[int, str | None] | None = None) -> str:
    """Build JSON payload for Claude."""
    readmes = readmes or {}
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
            "readme_excerpt": _readme_excerpt(readmes.get(repo.repo_id)),
        }
        entries.append(entry)
    return json.dumps(entries)


async def categorize_repos(
    repos: list[StarredRepo],
    output_dir: Path,
    api_key: str,
    readmes: dict[int, str | None] | None = None,
) -> list[CategorizedRepo]:
    """Categorize a list of repos using Claude, returning CategorizedRepo objects."""
    if not repos:
        return []

    categories, tags = read_existing_taxonomy(output_dir)
    system_prompt = _build_system_prompt(categories, tags)

    client = anthropic.Anthropic(api_key=api_key)
    payload = _build_payload(repos, readmes)

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
        parsed = json.loads(_normalize_json_response(response_text))
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
                tags=_fallback_tags(repo),
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
                tags=_enforce_repo_language(
                    repo,
                    normalize_tags(item.get("tags"), require_layer=True) or _fallback_tags(repo),
                ),
            )
        )

    return result
