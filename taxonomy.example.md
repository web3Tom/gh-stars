---
# Taxonomy Reference for gh-stars
#
# This file documents the intended category/subCategory and tags contract.
# v1 uses this as documentation for the categorizer prompt, not as a runtime
# override file.
#
# Boundary:
# - category/subCategory = Purpose, or what the repository solves.
# - tags = Form, or how the repository is packaged, consumed, and implemented.

taxonomy:
  Core Frameworks:
    - Agentic Orchestration
    - Toolkits & Primitives
    - Memory & Context
  Developer Tooling:
    - Workspaces & IDEs
    - Observability & Evals
  Infrastructure & Data:
    - Ingestion & Indexing
    - Proxies & Gateways
  Applied Systems:
    - Autonomous Agents
    - Services & Backends
  Knowledge & Reference:
    - Curated Lists
    - Learning & Cookbooks

tag_facets:
  layer:
    - cli
    - library
    - api
    - desktop
    - markdown
  lang:
    - python
    - typescript
    - react
    - rust
---

# gh-stars Taxonomy

Categories and subcategories describe repository purpose. They answer: what problem does this repo solve in the development lifecycle?

Tags describe repository form. They answer: how is this repo packaged, consumed, or implemented?

Examples:

- `Core Frameworks / Agentic Orchestration` with `["layer/library", "lang/python"]`
- `Developer Tooling / Workspaces & IDEs` with `["layer/cli", "lang/typescript"]`
- `Knowledge & Reference / Curated Lists` with `["layer/markdown"]`

Do not use ordering prefixes in category names. Use `Core Frameworks`, not `01 Core Frameworks`.

Do not use entity relationship tags such as `model/`, `provider/`, `tool/`, `framework/`, or `concept/` in this feed.
