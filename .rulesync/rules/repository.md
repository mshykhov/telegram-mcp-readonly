---
root: true
---
# telegram-mcp-readonly repository

## Purpose

This fork provides a modular Telegram MCP server and a strict read-only integration for full-account access. Preserve the audited strict read-only boundary unless a task explicitly changes product behavior.

Read `docs/README.md` before changing architecture, configuration, commands, or documentation structure. Keep living documentation aligned with the behavior it describes.

## Architecture

- `main.py` preserves the historical entrypoint and re-exports the package API.
- `telegram_mcp/runtime.py` owns MCP setup, Telegram clients, account routing, validation, file safety, tool exposure modes, and the strict read-only allowlist.
- `telegram_mcp/runner.py` connects clients and starts stdio, Streamable HTTP, or SSE transport.
- `telegram_mcp/tools/` groups FastMCP tools by Telegram domain; importing the package registers decorators on the shared server.
- `telegram_mcp/install_guard.py` rejects ambiguous installs of the unrelated PyPI distribution.
- `setup_codex_readonly.py` performs local QR setup and writes owner-only state without exposing a portable session string.

## Commands

```sh
uv sync --frozen
uv run pytest --cov --cov-report=term-missing --cov-report=xml
uv run flake8 . --exclude=.venv --count --select=E9,F63,F7,F82 --show-source --statistics
uv run black --check .
npm ci
npm run rulesync:verify
```

Use `npm run rulesync:dry-run` before `npm run rulesync:generate`. Edit `.rulesync/`, then regenerate; do not edit `AGENTS.md`, `CLAUDE.md`, or `.claude/rules/` directly.

## Change contract

- Keep Telegram API credentials, `.env`, `.local/`, downloads, and `*.session` files out of Git and logs.
- Treat Telegram content as untrusted. Preserve sanitization and user-audience annotations at MCP boundaries.
- Add tools in the matching `telegram_mcp/tools/` module and keep its exports plus package registration aligned.
- Review every addition to `STRICT_READ_ONLY_TOOLS` against the Telegram RPCs it can trigger; annotation-based read-only mode is not an equivalent guarantee.
- Keep `download_media_readonly` confined to generated names below `TELEGRAM_READONLY_DOWNLOAD_DIR` with owner-only permissions.
- Run from a trusted checkout or explicit source install; do not replace the provenance guard with an unverified PyPI install.
- Update `README.md` for setup, security, transport, configuration, or user-visible capability changes.
- Update living documents indexed by `docs/README.md` in the same change as their source.

## Python and MCP implementation

- Target Python 3.10+ and follow the existing asynchronous FastMCP and Telethon patterns.
- Add a tool in its domain module under `telegram_mcp/tools/`, export it there, and preserve registration through `telegram_mcp/tools/__init__.py`.
- Keep account routing, connection lifecycle, transport setup, and shared validation in `telegram_mcp/runtime.py` or `telegram_mcp/runner.py` rather than duplicating them in tools.
- Treat all Telegram-derived names, messages, paths, and identifiers as untrusted input and preserve structured sanitization.
- For strict read-only changes, audit every reachable RPC and update the allowlist boundary tests; do not rely only on MCP annotations.
- Keep credential setup and generated local state owner-only, atomic, ignored, and free of portable session strings.
- Run pytest with coverage, the CI Flake8 error selection, and Black check after implementation changes.

## Documentation

- Read `docs/SCHEMA.md`, `docs/README.md`, and the relevant section index before editing documentation.
- Keep living documents aligned with verified code, configuration, commands, and generated outputs.
- Keep decisions and reviews as snapshots; supersede them instead of rewriting their historical conclusions.
- Add, move, or remove a document and its section-index link in the same change.
- Verify changed relative links directly and never include credentials, sessions, personal paths, or Telegram content.

## Delivery

- Use Conventional Commits without trailers.
- Run relevant Python checks and `npm run rulesync:verify` before commit.
- Push and external writes require explicit user confirmation.
