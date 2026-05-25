from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class StarredRepo:
    """A GitHub repository starred by the user."""

    repo_id: int
    owner: str
    name: str
    description: str | None
    language: str | None
    stars: int
    homepage: str | None
    topics: tuple[str, ...]
    license: str | None
    repo_url: str
    starred_at: date
    node_id: str | None = None


@dataclass(frozen=True)
class CategorizedRepo:
    """A repo with assigned categorization metadata."""

    repo: StarredRepo
    category: str
    sub_category: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class UnstarResult:
    """Result of an unstar operation."""

    owner: str
    repo: str
    success: bool = True


class UnstarScopeError(RuntimeError):
    """User lacks permission to unstar repos."""

    pass


class UnstarRateLimitError(RuntimeError):
    """Rate limit hit during unstar operation."""

    def __init__(self, message: str, *, reset_epoch: int | None = None) -> None:
        super().__init__(message)
        self.reset_epoch = reset_epoch


@dataclass(frozen=True)
class CloneStats:
    """Statistics from clone reconciliation."""

    attempted: int
    cloned: int
    skipped_existing: int
    failed: int
    warnings: tuple[str, ...]
