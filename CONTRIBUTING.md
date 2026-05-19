# Contributing to gh-stars

Thank you for your interest in contributing!

## Getting Started

1. Clone the repository.
2. Install Python ≥3.11.
3. Create a venv and run `uv sync` to install dependencies.
4. Copy `.env.example` to `.env.local` and fill in your `GITHUB_PAT_TOKEN` and `ANTHROPIC_API_KEY`.

## Running Tests

```bash
uv run pytest --cov
```

Coverage must be ≥80%.

## Code Style

- Follow PEP 8.
- Use type hints.
- Keep functions small (<50 lines).
- Keep files focused (<800 lines).

## Before Submitting a PR

1. Run `uv run pytest --cov` and ensure all tests pass.
2. Run `pre-commit run --all-files` to check for secrets.
3. Review `git diff --staged` for hardcoded paths or credentials.
4. Write clear commit messages using conventional commits.

## Key Files

- `src/api_client.py`: GitHub REST API client
- `src/categorizer.py`: Claude categorization logic
- `src/markdown_writer.py`: Note generation
- `src/removal.py`: Unstar workflow
- `src/cloner.py`: Git clone reconciliation
- `src/main.py`: CLI entry point

See `AGENTS.md` for the full contract.
