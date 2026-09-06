<div align="center">

# Telegram MCP Readonly

**Search and analyze your Telegram account with AI agents without exposing Telegram mutation tools.**

[![Tests](https://github.com/mshykhov/telegram-mcp-readonly/actions/workflows/tests.yml/badge.svg)](https://github.com/mshykhov/telegram-mcp-readonly/actions/workflows/tests.yml)
[![Lint](https://github.com/mshykhov/telegram-mcp-readonly/actions/workflows/python-lint-format.yml/badge.svg)](https://github.com/mshykhov/telegram-mcp-readonly/actions/workflows/python-lint-format.yml)
[![Docker](https://github.com/mshykhov/telegram-mcp-readonly/actions/workflows/docker-build.yml/badge.svg)](https://github.com/mshykhov/telegram-mcp-readonly/actions/workflows/docker-build.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

</div>

Use your full Telegram account as a searchable knowledge source for Codex, Claude, and other Model Context Protocol clients. Find chats by title or username, search message text across the account, read history, inspect contacts and topics, and download media into one private local directory.

> [!IMPORTANT]
> Run `setup_codex_readonly.py` before connecting an agent. It enables the explicit `strict-read-only` allowlist. The codebase retains upstream write-capable tools for compatibility, but strict mode does not register them.

## Why this fork

- Explicit audited allowlist, independent of MCP annotation accuracy
- Search by text, username, phone, or chat title - IDs are optional for discovery
- One loopback service shared by multiple agent clients
- Local file session and credentials with owner-only permissions
- Multi-account support and sanitized Telegram output
- No session string copied into agent configuration

## Read-only boundary

| Available in strict mode | Not exposed in strict mode |
| --- | --- |
| Accounts, chats, folders, topics, contacts | Send, reply, edit, delete, or forward messages |
| Message history and account-wide search | Reactions, read receipts, drafts, or pins that mutate Telegram |
| Participants, admins, links, and metadata | Join, leave, invite, ban, or change members |
| Passive waits for incoming messages | Change profiles, privacy, folders, or chat settings |
| Media download to one configured local directory | Arbitrary local paths or agent-selected filenames |

`download_media_readonly` is the only deliberate local write. It creates generated filenames below `TELEGRAM_READONLY_DOWNLOAD_DIR` with owner-only permissions and never calls a mutating Telegram RPC.

> [!WARNING]
> Strict mode limits the MCP tool surface, not the authority of the underlying Telegram session. A stolen session file can compromise the account. Keep the checkout, `.env`, `.local/`, and the host itself private and trusted.

## Quick start

Requirements: Python 3.10+, [uv](https://docs.astral.sh/uv/), a Telegram account, and API credentials from [my.telegram.org/apps](https://my.telegram.org/apps).

```sh
git clone https://github.com/mshykhov/telegram-mcp-readonly.git
cd telegram-mcp-readonly
uv sync --frozen
uv run python setup_codex_readonly.py
```

The setup opens Telegram QR authorization and creates these ignored local files:

- `.env` with `TELEGRAM_EXPOSED_TOOLS=strict-read-only`
- `.local/telegram-readonly.session`
- `downloads/` for path-confined media downloads

Do not install `telegram-mcp` from PyPI or run it with `uvx`: that package name belongs to a different project. Clone this repository and run it from the checkout.

### Shared service on macOS

A single local service avoids Telethon SQLite lock conflicts when Codex, Claude, or several sessions connect at once.

```sh
uv run telegram-mcp-shared-service check
uv run telegram-mcp-shared-service prepare
uv run telegram-mcp-shared-service activate
uv run telegram-mcp-shared-service status
```

Connect clients to the loopback-only endpoint:

```json
{
  "mcpServers": {
    "telegram-readonly": {
      "type": "http",
      "url": "http://127.0.0.1:8765/mcp"
    }
  }
}
```

The endpoint is unauthenticated and must stay bound to `127.0.0.1`.

## Example prompts

- "Find the chat named Product Team and summarize its last 100 messages."
- "Search all Telegram messages for `incident review` from the last month."
- "Find messages containing this URL and show their chat names and dates."
- "List unread chats, then summarize them without marking anything as read."
- "Download the media from this message into the private download directory."

## Configuration

The safe setup script writes the required values. See [`.env.example`](.env.example) for optional proxy, multi-account, output, and event-feed settings.

For a manual launch, set at minimum:

```dotenv
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_SESSION_NAME=/private/path/telegram-readonly
TELEGRAM_EXPOSED_TOOLS=strict-read-only
TELEGRAM_READONLY_DOWNLOAD_DIR=/private/path/downloads
```

## Documentation

- [Documentation map](docs/README.md)
- [Architecture and trust boundaries](docs/architecture/overview.md)
- [Shared service runbook](docs/runbooks/operate-shared-readonly-service.md)
- [Shared local service plan](docs/plans/2026-08-10-shared-local-mcp-service.md)

## Development

```sh
uv sync --frozen
uv run pytest --cov --cov-report=term-missing --cov-report=xml
uv run flake8 . --exclude=.venv --count --select=E9,F63,F7,F82 --show-source --statistics
uv run black --check .
npm ci
npm run rulesync:verify
```

## Attribution

Based on [chigwell/telegram-mcp](https://github.com/chigwell/telegram-mcp). The strict read-only boundary, local setup, shared service, and security hardening are maintained in this repository.

Licensed under the [Apache License 2.0](LICENSE).
