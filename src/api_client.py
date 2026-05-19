from __future__ import annotations

import asyncio
import base64
import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

import httpx

from src.models import StarredRepo, UnstarRateLimitError, UnstarResult, UnstarScopeError

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.github.com"
_PER_PAGE = 100
_RATE_LIMIT_THRESHOLD = 100
_TRUNCATE_README_BYTES = 20 * 1024  # ~20KB


def _parse_repo_from_api(repo_data: dict[str, Any], starred_at: datetime) -> StarredRepo:
    """Extract StarredRepo from GitHub API response."""
    return StarredRepo(
        repo_id=repo_data["id"],
        owner=repo_data["owner"]["login"],
        name=repo_data["name"],
        description=repo_data.get("description"),
        language=repo_data.get("language"),
        stars=repo_data.get("stargazers_count", 0),
        homepage=repo_data.get("homepage"),
        topics=tuple(repo_data.get("topics") or []),
        license=repo_data.get("license", {}).get("name") if repo_data.get("license") else None,
        repo_url=repo_data["html_url"],
        starred_at=starred_at.date(),
    )


class GitHubClient:
    """Async GitHub API client."""

    def __init__(self, pat: str):
        self.pat = pat
        self._base_headers = {
            "Authorization": f"Bearer {pat}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "gh-stars",
        }

    async def list_starred_repos(self) -> AsyncIterator[StarredRepo]:
        """Paginate GET /user/starred with star+json media type to get starred_at."""
        async with httpx.AsyncClient(base_url=_BASE_URL) as client:
            url = "/user/starred"
            page = 1

            while True:
                headers = self._base_headers.copy()
                # Request star+json to get starred_at in response
                headers["Accept"] = "application/vnd.github.star+json"

                params = {"per_page": _PER_PAGE, "page": page}
                resp = await client.get(url, headers=headers, params=params)

                if resp.status_code == 401:
                    raise UnstarScopeError("Unauthorized: check GITHUB_PAT_TOKEN")
                if resp.status_code == 403:
                    raise UnstarScopeError("Forbidden: check GITHUB_PAT_TOKEN scope")

                resp.raise_for_status()

                # Handle rate limiting
                remaining = int(resp.headers.get("X-RateLimit-Remaining", 5000))
                if remaining < _RATE_LIMIT_THRESHOLD:
                    reset_epoch = int(resp.headers.get("X-RateLimit-Reset", 0))
                    sleep_time = max(0, reset_epoch - int(datetime.now(timezone.utc).timestamp())) + 2
                    logger.info(f"Rate limit approaching; sleeping {sleep_time}s")
                    await asyncio.sleep(sleep_time)

                data = resp.json()
                if not data:
                    break

                for item in data:
                    starred_at = datetime.fromisoformat(item["starred_at"].replace("Z", "+00:00"))
                    repo_data = item["repo"]
                    yield _parse_repo_from_api(repo_data, starred_at)

                page += 1

    async def fetch_readme(self, owner: str, repo: str) -> str | None:
        """Fetch README from GET /repos/{owner}/{repo}/readme, base64-decode, truncate."""
        async with httpx.AsyncClient(base_url=_BASE_URL) as client:
            url = f"/repos/{owner}/{repo}/readme"
            headers = self._base_headers.copy()

            resp = await client.get(url, headers=headers)

            if resp.status_code == 404:
                return None
            if resp.status_code in (401, 403):
                logger.warning(f"No access to {owner}/{repo} README")
                return None

            resp.raise_for_status()

            content_base64 = resp.json().get("content", "")
            content = base64.b64decode(content_base64).decode("utf-8", errors="replace")

            if len(content) > _TRUNCATE_README_BYTES:
                content = content[:_TRUNCATE_README_BYTES] + "\n\n... [README truncated]\n"

            return content

    async def unstar_repo(self, owner: str, repo: str) -> UnstarResult:
        """DELETE /user/starred/{owner}/{repo}."""
        async with httpx.AsyncClient(base_url=_BASE_URL) as client:
            url = f"/user/starred/{owner}/{repo}"
            resp = await client.delete(url, headers=self._base_headers)

            if resp.status_code == 204:
                return UnstarResult(owner=owner, repo=repo, success=True)
            if resp.status_code == 401:
                raise UnstarScopeError("Unauthorized: check GITHUB_PAT_TOKEN")
            if resp.status_code == 403:
                raise UnstarScopeError("Forbidden: unstar scope required")
            if resp.status_code == 429:
                reset_epoch = int(resp.headers.get("X-RateLimit-Reset", 0))
                raise UnstarRateLimitError(
                    f"Rate limit hit on unstar {owner}/{repo}",
                    reset_epoch=reset_epoch,
                )

            remaining = int(resp.headers.get("X-RateLimit-Remaining", 0))
            if remaining <= 0:
                reset_epoch = int(resp.headers.get("X-RateLimit-Reset", 0))
                raise UnstarRateLimitError(
                    f"Rate limit exhausted",
                    reset_epoch=reset_epoch,
                )

            resp.raise_for_status()
            return UnstarResult(owner=owner, repo=repo, success=False)
