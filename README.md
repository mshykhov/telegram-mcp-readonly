# Telegram MCP Readonly

Search Telegram chats and messages from any [MCP](https://modelcontextprotocol.io/) client. Read conversation history and download attachments without sending messages or changing chats.

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

## Attribution and license

This project is based on [chigwell/telegram-mcp](https://github.com/chigwell/telegram-mcp) and is licensed under the [Apache License 2.0](LICENSE).
