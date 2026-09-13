# Telegram MCP Readonly

[![Tests](https://github.com/mshykhov/telegram-mcp-readonly/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/mshykhov/telegram-mcp-readonly/actions/workflows/tests.yml)
[![Docker](https://github.com/mshykhov/telegram-mcp-readonly/actions/workflows/docker-build.yml/badge.svg?branch=main)](https://github.com/mshykhov/telegram-mcp-readonly/actions/workflows/docker-build.yml)
[![Security](https://github.com/mshykhov/telegram-mcp-readonly/actions/workflows/security.yml/badge.svg?branch=main)](https://github.com/mshykhov/telegram-mcp-readonly/actions/workflows/security.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

Search Telegram chats and messages from any [MCP](https://modelcontextprotocol.io/) client. Read conversation history and download attachments without sending messages or changing chats.

[Quick start](#install) · [Client setup](#connect-an-mcp-client) · [Documentation](docs/README.md) · [Security](SECURITY.md)

## What it does

| Capability | Included |
| --- | --- |
| Search | Messages across chats, account-wide search, folder filters |
| Read | History, topics, rich messages, custom emoji metadata, profiles |
| Attachments | Downloads confined to one configured directory |
| Connect | Stdio for one client; a shared local HTTP service for several clients |
| Protect | Explicit read-only allowlist, private session setup, sanitized results |

## Install

You need Python 3.10+, [uv](https://docs.astral.sh/uv/), a Telegram account, and API credentials from [my.telegram.org/apps](https://my.telegram.org/apps).

```sh
git clone https://github.com/mshykhov/telegram-mcp-readonly.git
cd telegram-mcp-readonly
uv sync --frozen
uv run python setup_readonly.py
```

Sign in by scanning the QR code with Telegram. Read-only mode is enabled by default. Keep the generated `.env` and session files private.

Clone this repository: the `telegram-mcp` package on PyPI is a different project.

## Connect an MCP client

For one local client, configure a stdio server:

```json
{
  "mcpServers": {
    "telegram-readonly": {
      "command": "uv",
      "args": [
        "--directory",
        "/full/path/to/telegram-mcp-readonly",
        "run",
        "telegram-mcp"
      ]
    }
  }
}
```

## Configuration and documentation

The setup script writes the required configuration. See [`.env.example`](.env.example) for optional proxy, multi-account, event-feed, and device settings. The [documentation map](docs/README.md) includes the [shared-service runbook](docs/runbooks/operate-shared-readonly-service.md) for macOS installations shared by several clients.

## Dependency updates

[Renovate](renovate.json) uses the [shared update policy](https://github.com/mshykhov/renovate-config) for Python dependencies and `uv.lock`, npm tooling, Docker images, and GitHub Actions. Minor, patch, and pin updates merge automatically after all required CI checks pass against the current `main`. Major updates require dashboard approval and manual merging; weekly lock-file maintenance also stays manual. MCP stays below v2 until a reviewed migration.

## Fork maintenance

This fork adds the audited read-only tool boundary, confined attachment downloads, QR setup, and a shared local service. The original upstream commits retain their authors and dates. Upstream changes through [`5d7f0a7`](https://github.com/chigwell/telegram-mcp/commit/5d7f0a7) are integrated, including rich-message reading, custom emoji metadata, safer error logging, and session locks.

New upstream tools remain excluded from strict mode until reviewed. Voice transcription and its cache are disabled in strict mode, including automatic transcription during history reads.

## Attribution and license

This project is based on [chigwell/telegram-mcp](https://github.com/chigwell/telegram-mcp) and is licensed under the [Apache License 2.0](LICENSE).
