"""Tests for api_client module."""

import pytest
import respx
from httpx import Response

from src.api_client import GitHubClient


@respx.mock
@pytest.mark.asyncio
async def test_list_starred_repos_pagination():
    """Test pagination through starred repos."""
    client = GitHubClient("ghp_test123")

    # Page 1 returns one item, page 2 returns empty to terminate pagination.
    rate_headers = {
        "X-RateLimit-Remaining": "4999",
        "X-RateLimit-Reset": "9999999999",
    }
    respx.get("https://api.github.com/user/starred").mock(
        side_effect=[
            Response(
                200,
                json=[
                    {
                        "starred_at": "2026-03-15T10:30:00Z",
                        "repo": {
                            "id": 123,
                            "name": "repo1",
                            "owner": {"login": "owner1"},
                            "html_url": "https://github.com/owner1/repo1",
                            "description": "Repo 1",
                            "language": "Python",
                            "stargazers_count": 100,
                            "topics": ["ai"],
                        },
                    }
                ],
                headers=rate_headers,
            ),
            Response(200, json=[], headers=rate_headers),
        ]
    )

    repos = []
    async for repo in client.list_starred_repos():
        repos.append(repo)

    assert len(repos) == 1
    assert repos[0].repo_id == 123
    assert repos[0].owner == "owner1"
    assert repos[0].name == "repo1"


@respx.mock
@pytest.mark.asyncio
async def test_fetch_readme_success():
    """Test fetching README successfully."""
    client = GitHubClient("ghp_test123")

    readme_content = "# Test Repo\n\nThis is a test."
    import base64

    respx.get("https://api.github.com/repos/test/repo/readme").mock(
        return_value=Response(
            200,
            json={"content": base64.b64encode(readme_content.encode()).decode()},
        )
    )

    readme = await client.fetch_readme("test", "repo")

    assert readme is not None
    assert "Test Repo" in readme


@respx.mock
@pytest.mark.asyncio
async def test_fetch_readme_not_found():
    """Test fetching non-existent README."""
    client = GitHubClient("ghp_test123")

    respx.get("https://api.github.com/repos/test/norepo/readme").mock(
        return_value=Response(404)
    )

    readme = await client.fetch_readme("test", "norepo")

    assert readme is None


@respx.mock
@pytest.mark.asyncio
async def test_unstar_repo_success():
    """Test unstarring a repo."""
    client = GitHubClient("ghp_test123")

    respx.delete("https://api.github.com/user/starred/test/repo").mock(
        return_value=Response(204)
    )

    result = await client.unstar_repo("test", "repo")

    assert result.success is True
    assert result.owner == "test"
    assert result.repo == "repo"


@respx.mock
@pytest.mark.asyncio
async def test_unstar_repo_unauthorized():
    """Test unstarring without proper scope."""
    from src.api_client import UnstarScopeError

    client = GitHubClient("ghp_test123")

    respx.delete("https://api.github.com/user/starred/test/repo").mock(
        return_value=Response(401)
    )

    with pytest.raises(UnstarScopeError):
        await client.unstar_repo("test", "repo")
