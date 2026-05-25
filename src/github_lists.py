from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from typing import Any

import httpx

from src.models import CategorizedRepo, GitHubList, GitHubListSyncStats

logger = logging.getLogger(__name__)

_GRAPHQL_URL = "https://api.github.com/graphql"
_PAGE_SIZE = 100

_LIST_DESCRIPTIONS = {
    "Awesome Lists": "Curated awesome lists, indexes, and aggregator repositories.",
    "Agent Skills": "Agent skill repositories for Codex, Claude, and related agent runtimes.",
    "Learning & Cookbooks": "Tutorials, courses, examples, and implementation cookbooks.",
    "Core Frameworks": "Agentic orchestration, primitives, memory, and context frameworks.",
    "Developer Tooling": "Developer workspaces, IDE tooling, observability, and eval tooling.",
    "Infrastructure & Data": "Ingestion, indexing, gateways, and data infrastructure.",
    "Applied Systems": "Turnkey agents, services, backends, and deployable systems.",
    "Knowledge & Reference": "Reference repositories and documentation-heavy knowledge bases.",
    "Unsorted": "Repositories that need manual review.",
}

_USER_LISTS_QUERY = """
query UserLists($after: String) {
  viewer {
    lists(first: 100, after: $after) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        id
        name
        slug
        description
        isPrivate
      }
    }
  }
}
"""

_CREATE_LIST_MUTATION = """
mutation CreateUserList($name: String!, $description: String, $isPrivate: Boolean!) {
  createUserList(input: {name: $name, description: $description, isPrivate: $isPrivate}) {
    list {
      id
      name
      slug
      description
      isPrivate
    }
  }
}
"""

_LIST_ITEMS_QUERY = """
query UserListItems($listId: ID!, $after: String) {
  node(id: $listId) {
    ... on UserList {
      items(first: 100, after: $after) {
        pageInfo {
          hasNextPage
          endCursor
        }
        nodes {
          ... on Repository {
            id
          }
        }
      }
    }
  }
}
"""

_UPDATE_ITEM_LISTS_MUTATION = """
mutation UpdateUserListsForItem($itemId: ID!, $listIds: [ID!]!) {
  updateUserListsForItem(input: {itemId: $itemId, listIds: $listIds}) {
    item {
      ... on Repository {
        id
      }
    }
  }
}
"""

def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return re.sub(r"-{2,}", "-", slug).strip("-")

def _contains_any(text: str, needles: Iterable[str]) -> bool:
    return any(needle in text for needle in needles)

def determine_github_list(categorized: CategorizedRepo, readme: str | None = None) -> str:
    """Choose one GitHub-side List for a categorized repo.

    The list is intentionally coarser than tags. Cross-cutting repository forms
    win first, then the purpose category is used as the stable fallback.
    """
    repo = categorized.repo
    haystack = " ".join(
        [
            repo.owner,
            repo.name,
            repo.description or "",
            " ".join(repo.topics),
            categorized.category,
            categorized.sub_category,
            categorized.list,
            " ".join(categorized.tags),
            readme or "",
        ]
    ).lower()

    if (
        repo.name.lower().startswith("awesome-")
        or "awesome-list" in haystack
        or "awesome list" in haystack
        or categorized.sub_category == "Curated Lists"
    ):
        return "Awesome Lists"

    if _contains_any(
        haystack,
        (
            "skill.md",
            "agent skill",
            "claude skill",
            "codex skill",
            "openai skill",
            "mcp skill",
        ),
    ) or re.search(r"(^|[-_\s])skills?($|[-_\s])", repo.name.lower()):
        return "Agent Skills"

    if categorized.sub_category == "Learning & Cookbooks" or _contains_any(
        haystack, ("cookbook", "tutorial", "course", "learn ", "examples")
    ):
        return "Learning & Cookbooks"

    if categorized.category in _LIST_DESCRIPTIONS:
        return categorized.category

    return "Unsorted"

class GitHubListsClient:
    """GraphQL client for GitHub User Lists."""

    def __init__(self, pat: str):
        self._headers = {
            "Authorization": f"Bearer {pat}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "gh-stars",
        }

    async def _graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                _GRAPHQL_URL,
                headers=self._headers,
                json={"query": query, "variables": variables},
            )

        if resp.status_code in (401, 403):
            raise PermissionError("GitHub token lacks access to User Lists GraphQL operations")
        resp.raise_for_status()

        payload = resp.json()
        if payload.get("errors"):
            messages = "; ".join(error.get("message", "unknown GraphQL error") for error in payload["errors"])
            if "requires one of" in messages or "Resource not accessible" in messages:
                raise PermissionError(messages)
            raise RuntimeError(messages)

        return payload["data"]

    async def list_user_lists(self) -> list[GitHubList]:
        """Return all viewer User Lists."""
        lists: list[GitHubList] = []
        after: str | None = None

        while True:
            data = await self._graphql(_USER_LISTS_QUERY, {"after": after})
            connection = data["viewer"]["lists"]
            for node in connection["nodes"]:
                lists.append(_parse_user_list(node))

            page_info = connection["pageInfo"]
            if not page_info["hasNextPage"]:
                return lists
            after = page_info["endCursor"]

    async def create_user_list(self, name: str, description: str | None) -> GitHubList:
        """Create a public GitHub User List."""
        data = await self._graphql(
            _CREATE_LIST_MUTATION,
            {"name": name, "description": description, "isPrivate": False},
        )
        return _parse_user_list(data["createUserList"]["list"])

    async def list_item_ids(self, user_list: GitHubList) -> set[str]:
        """Return repository item IDs in a User List."""
        item_ids: set[str] = set()
        after: str | None = None

        while True:
            data = await self._graphql(
                _LIST_ITEMS_QUERY,
                {"listId": user_list.id, "after": after},
            )
            node = data.get("node") or {}
            connection = node.get("items")
            if connection is None:
                break

            item_ids.update(
                item["id"]
                for item in connection["nodes"]
                if item is not None and item.get("id")
            )

            page_info = connection["pageInfo"]
            if not page_info["hasNextPage"]:
                break
            after = page_info["endCursor"]

        return item_ids

    async def existing_list_ids_for_item(
        self,
        item_id: str,
        user_lists: Iterable[GitHubList],
    ) -> set[str]:
        """Find existing User Lists that contain the item."""
        membership_index = await build_membership_index(self, user_lists)
        return membership_index.get(item_id, set())

    async def update_item_lists(self, item_id: str, list_ids: set[str]) -> None:
        """Replace item membership with the provided complete List ID set."""
        await self._graphql(
            _UPDATE_ITEM_LISTS_MUTATION,
            {"itemId": item_id, "listIds": sorted(list_ids)},
        )

async def sync_github_lists(
    client: GitHubListsClient,
    categorized_repos: list[CategorizedRepo],
    readmes: dict[int, str | None] | None = None,
) -> GitHubListSyncStats:
    """Create target Lists and add categorized repos to them."""
    readmes = readmes or {}
    warnings: list[str] = []
    failed = 0
    updated = 0
    skipped_missing_node_id = 0
    created_lists = 0

    try:
        user_lists = await client.list_user_lists()
    except Exception as exc:
        return GitHubListSyncStats(
            attempted=len(categorized_repos),
            updated=0,
            created_lists=0,
            skipped_missing_node_id=0,
            failed=len(categorized_repos),
            warnings=(f"Failed to read GitHub Lists: {exc}",),
        )

    lists_by_slug = {_slug(user_list.name): user_list for user_list in user_lists}
    sync_candidates: list[CategorizedRepo] = []
    for categorized in categorized_repos:
        if not categorized.repo.node_id:
            skipped_missing_node_id += 1
            warnings.append(f"Skipping {categorized.repo.owner}/{categorized.repo.name}: missing node_id")
            continue
        sync_candidates.append(categorized)

    if not sync_candidates:
        return GitHubListSyncStats(
            attempted=len(categorized_repos),
            updated=0,
            created_lists=0,
            skipped_missing_node_id=skipped_missing_node_id,
            failed=0,
            warnings=tuple(warnings),
        )

    try:
        membership_index = await build_membership_index(client, user_lists)
    except Exception as exc:
        return GitHubListSyncStats(
            attempted=len(categorized_repos),
            updated=0,
            created_lists=0,
            skipped_missing_node_id=0,
            failed=len(categorized_repos),
            warnings=(f"Failed to read GitHub List memberships: {exc}",),
        )

    for categorized in sync_candidates:
        node_id = categorized.repo.node_id
        assert node_id is not None

        target_name = determine_github_list(categorized, readmes.get(categorized.repo.repo_id))
        target_slug = _slug(target_name)
        target_list = lists_by_slug.get(target_slug)

        try:
            if target_list is None:
                target_list = await client.create_user_list(
                    target_name,
                    _LIST_DESCRIPTIONS.get(target_name),
                )
                lists_by_slug[target_slug] = target_list
                user_lists.append(target_list)
                membership_index.setdefault(node_id, set())
                created_lists += 1

            existing_ids = membership_index.get(node_id, set())
            desired_ids = existing_ids | {target_list.id}
            if desired_ids != existing_ids:
                await client.update_item_lists(node_id, desired_ids)
                membership_index[node_id] = desired_ids
                updated += 1
        except Exception as exc:
            failed += 1
            warning = f"Failed to sync {categorized.repo.owner}/{categorized.repo.name}: {exc}"
            logger.warning(warning)
            warnings.append(warning)

    return GitHubListSyncStats(
        attempted=len(categorized_repos),
        updated=updated,
        created_lists=created_lists,
        skipped_missing_node_id=skipped_missing_node_id,
        failed=failed,
        warnings=tuple(warnings),
    )

async def build_membership_index(
    client: GitHubListsClient,
    user_lists: Iterable[GitHubList],
) -> dict[str, set[str]]:
    """Build item_id -> list_ids membership map with one item scan per list."""
    membership_index: dict[str, set[str]] = {}

    for user_list in user_lists:
        for item_id in await client.list_item_ids(user_list):
            membership_index.setdefault(item_id, set()).add(user_list.id)

    return membership_index

def _parse_user_list(node: dict[str, Any]) -> GitHubList:
    return GitHubList(
        id=node["id"],
        name=node["name"],
        slug=node["slug"],
        description=node.get("description"),
        is_private=bool(node["isPrivate"]),
    )
