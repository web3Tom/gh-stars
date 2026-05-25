"""Tests for GitHub User Lists sync."""

import json
from datetime import date

import pytest
import respx
from httpx import Response

from src.github_lists import GitHubListsClient, determine_github_list, sync_github_lists
from src.models import CategorizedRepo, GitHubList, StarredRepo

def _repo(
    *,
    name: str = "repo",
    description: str | None = "Test repo",
    topics: tuple[str, ...] = (),
    node_id: str | None = "R_kgDOExample",
    repo_id: int = 123,
) -> StarredRepo:
    return StarredRepo(
        repo_id=repo_id,
        owner="owner",
        name=name,
        description=description,
        language="Python",
        stars=100,
        homepage=None,
        topics=topics,
        license="MIT",
        repo_url=f"https://github.com/owner/{name}",
        starred_at=date(2026, 5, 1),
        node_id=node_id,
    )

def _categorized(
    *,
    repo: StarredRepo | None = None,
    category: str = "Core Frameworks",
    sub_category: str = "Agentic Orchestration",
    list_name: str = "agent-research",
    tags: tuple[str, ...] = ("layer/library", "lang/python"),
) -> CategorizedRepo:
    return CategorizedRepo(
        repo=repo or _repo(),
        category=category,
        sub_category=sub_category,
        list=list_name,
        tags=tags,
    )

def test_determine_github_list_groups_awesome_lists():
    categorized = _categorized(
        repo=_repo(name="awesome-ai-agents"),
        category="Knowledge & Reference",
        sub_category="Curated Lists",
        tags=("layer/markdown",),
    )

    assert determine_github_list(categorized) == "Awesome Lists"

def test_determine_github_list_groups_agent_skill_repos():
    categorized = _categorized(repo=_repo(name="markdown-viewer-skills"))

    assert determine_github_list(categorized, "# Markdown Viewer\n\nContains SKILL.md") == "Agent Skills"

def test_determine_github_list_falls_back_to_purpose_category():
    categorized = _categorized(category="Infrastructure & Data", sub_category="Ingestion & Indexing")

    assert determine_github_list(categorized) == "Infrastructure & Data"

@respx.mock
@pytest.mark.asyncio
async def test_github_lists_client_creates_and_preserves_membership():
    client = GitHubListsClient("ghp_test123")
    requests = []

    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload)
        query = payload["query"]

        if "query UserLists" in query:
            return Response(
                200,
                json={
                    "data": {
                        "viewer": {
                            "lists": {
                                "pageInfo": {"hasNextPage": False, "endCursor": None},
                                "nodes": [
                                    {
                                        "id": "UL_existing",
                                        "name": "Existing",
                                        "slug": "existing",
                                        "description": None,
                                        "isPrivate": False,
                                    }
                                ],
                            }
                        }
                    }
                },
            )

        if "mutation CreateUserList" in query:
            assert payload["variables"]["name"] == "Core Frameworks"
            return Response(
                200,
                json={
                    "data": {
                        "createUserList": {
                            "list": {
                                "id": "UL_core",
                                "name": "Core Frameworks",
                                "slug": "core-frameworks",
                                "description": "Core framework repos",
                                "isPrivate": False,
                            }
                        }
                    }
                },
            )

        if "query UserListItems" in query:
            list_id = payload["variables"]["listId"]
            nodes = [{"id": "R_kgDOExample"}] if list_id == "UL_existing" else []
            return Response(
                200,
                json={
                    "data": {
                        "node": {
                            "items": {
                                "pageInfo": {"hasNextPage": False, "endCursor": None},
                                "nodes": nodes,
                            }
                        }
                    }
                },
            )

        if "mutation UpdateUserListsForItem" in query:
            assert payload["variables"]["itemId"] == "R_kgDOExample"
            assert payload["variables"]["listIds"] == ["UL_core", "UL_existing"]
            return Response(
                200,
                json={"data": {"updateUserListsForItem": {"item": {"id": "R_kgDOExample"}}}},
            )

        return Response(500)

    respx.post("https://api.github.com/graphql").mock(side_effect=handler)

    stats = await sync_github_lists(client, [_categorized()])

    assert stats.attempted == 1
    assert stats.created_lists == 1
    assert stats.updated == 1
    assert stats.failed == 0
    assert any("mutation UpdateUserListsForItem" in request["query"] for request in requests)

@pytest.mark.asyncio
async def test_sync_github_lists_skips_missing_node_id():
    class FakeClient:
        async def list_user_lists(self):
            return [
                GitHubList(
                    id="UL_core",
                    name="Core Frameworks",
                    slug="core-frameworks",
                    description=None,
                    is_private=False,
                )
            ]

    stats = await sync_github_lists(FakeClient(), [_categorized(repo=_repo(node_id=None))])

    assert stats.attempted == 1
    assert stats.updated == 0
    assert stats.skipped_missing_node_id == 1
    assert stats.failed == 0


@pytest.mark.asyncio
async def test_sync_github_lists_scans_each_list_once_for_batch():
    """Test batch sync reuses list membership data across repos."""
    class FakeClient:
        def __init__(self):
            self.item_scans = 0
            self.updates = []

        async def list_user_lists(self):
            return [
                GitHubList(
                    id="UL_core",
                    name="Core Frameworks",
                    slug="core-frameworks",
                    description=None,
                    is_private=False,
                )
            ]

        async def list_item_ids(self, user_list):
            self.item_scans += 1
            return set()

        async def create_user_list(self, name, description):
            raise AssertionError("list already exists")

        async def update_item_lists(self, item_id, list_ids):
            self.updates.append((item_id, list_ids))

    client = FakeClient()
    categorized = [
        _categorized(repo=_repo(node_id="R_one", repo_id=1)),
        _categorized(repo=_repo(node_id="R_two", repo_id=2)),
    ]

    stats = await sync_github_lists(client, categorized)

    assert stats.updated == 2
    assert client.item_scans == 1
    assert client.updates == [("R_one", {"UL_core"}), ("R_two", {"UL_core"})]
