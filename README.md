# gh-stars

Fetch your starred GitHub repositories, categorize them with Claude, and write them as Obsidian-friendly Markdown notes.

GitHub: [`github.com/web3Tom/gh-stars`](https://github.com/web3Tom/gh-stars)

## Features

- **Fetch starred repos** from your GitHub account via REST API
- **Categorize** each repo using Claude (Sonnet 4.6)
- **Write Obsidian notes** with frontmatter, README content, and metadata
- **Manage lists** using a frontmatter `list` field to organize by project focus
- **Clone support** with `cloned: true` to shallow-clone repos for deeper analysis
- **Unstar workflow** with `unstar: true` to remove repos + move notes to archive
- **Rate-limit aware** with automatic backoff
- **Append-only history** in JSONL format

## Quick Start

### 1. Set up environment

```bash
# Create a fine-grained PAT at https://github.com/settings/personal-access-tokens/new
# with scopes: Account → Starring (read+write), Repository → Metadata (read), Contents (read)

# Install gh-stars
cd ~/workspace/gh-stars
uv sync

# Configure secrets
export GITHUB_PAT_TOKEN="ghp_your_token_here"
export ANTHROPIC_API_KEY="sk-ant-your_key_here"
export KNOWLEDGE_BASE_DIR=/path/to/your/obsidian-vault
```

### 2. Run sync

```bash
uv run gh-stars
```

This will:
- Fetch all starred repos
- Deduplicate against existing notes (including archive)
- For repos >100: prompt for confirmation + cost estimate
- Categorize in batches of 25 using Claude
- Write notes to `knowledge/09_feeds/gh-stars/`
- Reconcile shallow clones for repos marked `cloned: true`
- Append history record

### 3. Manage stars

Edit frontmatter to control behavior:

```yaml
---
unstar: true        # Mark for removal
cloned: false       # Toggle to true to clone on next sync
category: "AI"
list: "agent-research"
---
```

Then run:

```bash
uv run gh-stars remove-unstarred
```

This moves notes to `archive/`, unstar repos via API, and records history.

## CLI Reference

| Command | Description |
|---------|-------------|
| `uv run gh-stars` | Fetch, categorize, write (default) |
| `uv run gh-stars --max-repos 5` | Limit to N repos (testing) |
| `uv run gh-stars --dry-run` | Fetch only, don't write |
| `uv run gh-stars --yes` | Skip >100 confirmation |
| `uv run gh-stars remove-unstarred` | Unstar repos with `unstar: true` |
| `uv run gh-stars reconcile-clones` | Clone reconciliation only |

## Frontmatter Schema

```yaml
---
title: "llm-wiki"                    # repo name
repo: "karpathy/llm-wiki"            # owner/name
repo_id: 884521234                   # GitHub numeric ID (dedup key)
description: "..."                   # From GitHub
category: "AI Knowledge Systems"     # User-editable
subCategory: "personalKnowledgeBase" # User-editable (camelCase)
list: "agent-research"               # Project bucket (lowercase-kebab-case)
language: "Python"                   # From GitHub
stars: 4521                          # Current count
starred_at: 2026-03-15               # When you starred it
repo_url: "https://github.com/..."   # GitHub URL
cloned: false                        # Set true to trigger clone
unstar: false                        # Set true to trigger unstar
---
```

## Known Limitations

- GitHub Lists API is not yet stable (v1 uses frontmatter only)
- No cron/scheduling in v1 (manual runs only)
- Clones are shallow (`--depth=1`) for speed
- README truncated at ~20KB to keep Claude calls affordable

## Environment Variables

```
GITHUB_PAT_TOKEN                 # Required: fine-grained PAT
ANTHROPIC_API_KEY          # Required for categorization (optional for --remove-unstarred)
KNOWLEDGE_BASE_DIR         # Default: ~/gh-stars-data
CLONES_DIR                 # Default: <workspace>/clones/
```

## Testing

```bash
uv run pytest --cov
```

Requires ≥80% coverage. Uses `respx` to mock `httpx` calls.

## Development

- Python ≥3.11
- Package manager: `uv`
- Dependencies: httpx, anthropic, python-dotenv, pyyaml
- Dev: pytest, pytest-asyncio, pytest-cov, respx

See [`AGENTS.md`](./AGENTS.md) for contributor guidelines and Markdown schema.
