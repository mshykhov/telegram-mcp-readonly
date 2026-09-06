# Shared local MCP service

Date: 2026-08-10
Status: accepted

## Context

The strict read-only setup stores Telegram authorization in one owner-only Telethon SQLite session. A stdio MCP declaration starts a separate server process for every agent client or app-server. Concurrent Codex and Claude sessions therefore contend for the same SQLite file, and every process after the first exits during MCP initialization with `database is locked`.

The server already supports stateless Streamable HTTP specifically so many MCP clients can share one long-lived Telegram connection. The global agent configuration is managed by Rulesync and must expose the same MCP inventory to both configured targets.

## Decision

Run one launchd-managed `telegram-mcp` process from the trusted checkout with:

- `MCP_TRANSPORT=http`;
- `MCP_HOST=127.0.0.1`;
- `MCP_PORT=8765`;
- the existing owner-only `.env` and file session;
- the existing `TELEGRAM_EXPOSED_TOOLS=strict-read-only` boundary.

Both Codex and Claude consume `http://127.0.0.1:8765/mcp` from the top-level Rulesync `mcpServers` inventory. Target blocks may preserve native header or format differences, but neither target owns a separate Telegram declaration.

The standalone Telegram repository owns the local service installer, LaunchAgent template, health check, and recovery documentation. The agent configuration repository owns only the shared endpoint declaration and inventory documentation.

## Components and flow

1. The installer validates the trusted checkout, executable, owner-only `.env`, owner-only session, and loopback endpoint configuration.
2. It renders an owner-local LaunchAgent whose working directory is the checkout and whose program uses the resolved absolute `uv` path.
3. launchd keeps exactly one Telegram MCP process alive.
4. The process opens the file session once, connects to Telegram, and serves stateless Streamable HTTP on loopback.
5. Codex and Claude connect to the same `/mcp` endpoint and never open the SQLite session themselves.

## Safety and failure handling

- The HTTP listener remains loopback-only and unauthenticated. The installer rejects non-loopback hosts.
- Credentials and session contents stay outside Git, plist files, client configuration, logs, and command arguments.
- Runtime files and logs are owner-only. Logs must not contain Telegram message content or credential values.
- Installation is staged before activation. Health verification requires MCP initialization and the strict read-only tool surface.
- Migration stops the old stdio holder before activating the singleton. Existing agent clients must reconnect after the Rulesync declaration changes.
- A failed health check leaves diagnostics available and does not rewrite the Telegram session.

## Alternatives considered

### Keep stdio and copy the session per client

Rejected. It duplicates authorization state, remains fragile as clients multiply, and can trigger Telegram auth-key collision behavior.

### Run the shared service in Docker

Supported by the project but not selected for the local agent runtime. It adds a Docker Desktop dependency and a second packaging boundary where launchd can run the pinned checkout directly.

### Run the HTTP process manually

Rejected. Manual lifecycle management makes agent startup depend on terminal state and does not recover the service after login or process failure.

## Verification contract

- Installer tests cover loopback enforcement, absolute executable resolution, owner-only output, and deterministic LaunchAgent rendering.
- Existing Python tests continue to cover stateless HTTP and strict read-only exposure.
- A live health check initializes `/mcp`, lists tools, confirms `get_me` is exposed, and confirms known write tools remain absent.
- Rulesync dry-run and generation produce the same `telegram-readonly` HTTP URL for Codex and Claude.
- A fresh Codex app-server and Claude MCP status check both report the server ready while one Telegram MCP process owns the session.
