# Architecture overview

## Components

| Component | Responsibility |
|-----------|----------------|
| `main.py` | Compatibility entrypoint, installation provenance check, and package API re-exports |
| `telegram_mcp/runtime.py` | Shared FastMCP instance, Telegram clients, account and proxy discovery, validation, file safety, exposure modes, and strict read-only allowlist |
| `telegram_mcp/runner.py` | Client connection lifecycle and stdio, Streamable HTTP, or SSE startup |
| `telegram_mcp/shared_service.py` | Owner-local LaunchAgent preparation, activation, loopback MCP health checks, and strict tool-surface validation |
| `telegram_mcp/tools/` | FastMCP tools grouped by account, chat, contact, event, folder, group, media, message, and profile domain |
| `telegram_mcp/install_guard.py` | Refusal of ambiguous installs using the unrelated `telegram-mcp` PyPI distribution |
| `sanitize.py` | Sanitization and structured formatting of Telegram-controlled output |
| `setup_readonly.py` | One-time local QR authorization and owner-only strict read-only state setup |

## Server flow

1. `main.py` verifies installation provenance, then exposes the modular package through the historical entrypoint.
2. Importing `telegram_mcp.tools` registers domain functions on the shared `FastMCP` instance created in `runtime.py`.
3. `runner.main()` configures allowed filesystem roots and applies `TELEGRAM_EXPOSED_TOOLS` before opening a transport.
4. The runner connects every configured Telegram account, warms entity caches in the background, and starts stdio, Streamable HTTP, or legacy SSE.
5. A tool resolves its account and Telegram entity through shared runtime helpers, calls Telethon, sanitizes Telegram-controlled data, and returns structured content.

## Strict read-only boundary

`strict-read-only` is the default `TELEGRAM_EXPOSED_TOOLS` mode. It ignores MCP tool annotations and retains only names in `STRICT_READ_ONLY_TOOLS`. The allowlist covers account, chat, folder, topic, contact, search, history, metadata, and passive wait operations. Known mutations such as sending, editing, deleting, forwarding, reacting, marking read, archiving, inviting, changing profiles, and changing folders are removed before the server starts.

`download_media_readonly` is the single deliberate local write in that surface. It accepts no caller-provided path, generates a unique name below `TELEGRAM_READONLY_DOWNLOAD_DIR`, resolves the destination against that root, and applies owner-only permissions. Boundary tests assert both the allowed surface and excluded mutations.

Strict mode also disables voice transcription and transcript-cache access inside message reads, even when `TELEGRAM_TRANSCRIBE=auto` is configured. New upstream photo and transcription tools remain outside the audited allowlist.

## State and secrets

The runtime reads Telegram credentials and session configuration from environment variables and the ignored `.env` file. It supports one account, labelled multi-account sessions, and a locked pool of interchangeable sessions for concurrent clients.

The local strict read-only setup creates `.local/telegram-readonly.session`, `downloads/`, and `.env` with owner-only permissions. It uses QR authorization and does not print or store a portable session string in client configuration. All of these paths remain outside version control.

For concurrent agent clients, the local service manager renders an owner-only LaunchAgent that runs the trusted checkout over loopback Streamable HTTP. One process owns the Telethon SQLite session; clients share the HTTP endpoint and never open that file directly. The rendered plist contains only executable, checkout, log, transport, host, and port values.

The runner acquires an exclusive local session lock before connecting and releases it on exit. This also prevents a second server from connecting the same session during a restart. Keep the default exclusive lock for file-backed sessions and use the shared HTTP service for multiple clients.

## External boundaries

- Telethon connects to Telegram through MTProto, optionally through configured SOCKS, HTTP, or MTProxy settings.
- Stdio is the default MCP transport. Streamable HTTP and SSE bind to configured host and port values; shared HTTP deployment should remain loopback-only unless transport security is configured deliberately.
- The managed strict read-only service fixes the listener at `127.0.0.1:8765` and validates that `get_me` is present while known write tools remain absent before reporting healthy.
- Telegram messages, names, titles, buttons, and other returned content are untrusted. Runtime sanitization and MCP user-audience annotations preserve that boundary.
- The PyPI distribution name belongs to an unrelated project. Trusted execution comes from a checkout or an explicit git/file install whose provenance the startup guard can verify.
