# Operate the shared read-only service

Use this procedure when Codex, Claude, or multiple agent sessions share the owner-only file session created by `setup_codex_readonly.py`. A per-client stdio declaration is not safe for that topology: the first process owns the Telethon SQLite file and later processes fail MCP initialization with `database is locked`.

The managed service runs one Streamable HTTP endpoint at `http://127.0.0.1:8765/mcp`. It is unauthenticated and must remain loopback-only.

## Preflight

Run from the trusted checkout:

```sh
uv sync --frozen
uv run telegram-mcp-shared-service check
stat -f '%N mode=%Sp' .env .local .local/telegram-readonly.session
```

`.env`, `.local`, and the session file must have no group or world permissions. If local authorization is missing, run `uv run python setup_codex_readonly.py` before continuing. Never print or copy their contents.

## Prepare

Render the owner-only LaunchAgent and create its owner-only log:

```sh
uv run telegram-mcp-shared-service prepare --dry-run
uv run telegram-mcp-shared-service prepare
```

The prepared plist is stored below `${XDG_DATA_HOME:-$HOME/.local/share}/telegram-mcp-readonly/`. The log is `${XDG_STATE_HOME:-$HOME/.local/state}/telegram-mcp-readonly/service.log`. Neither contains Telegram credentials or session contents.

## Configure agent clients

The shared MCP declaration is:

```json
{
  "telegram-readonly": {
    "type": "http",
    "url": "http://127.0.0.1:8765/mcp"
  }
}
```

When Rulesync owns agent configuration, put this declaration only in the top-level `mcpServers` canonical source. Run the repository's Rulesync dry-run before generation for every configured target. Native per-client add commands do not replace that workflow.

Close or reconnect clients that still own a stdio `telegram-mcp` process before activation. Verify the exact process command rather than terminating Python or `uv` processes broadly.

## Activate and verify

```sh
uv run telegram-mcp-shared-service activate --dry-run
uv run telegram-mcp-shared-service activate
uv run telegram-mcp-shared-service status
```

Activation backs up an existing LaunchAgent, installs the new file with mode `0600`, reloads `com.mshykhov.telegram-mcp-readonly`, and initializes MCP. Status succeeds only when `get_me` is exposed and known write tools are absent.

Confirm one listener and one service process without reading its environment:

```sh
lsof -nP -iTCP:8765 -sTCP:LISTEN
ps -axo pid=,ppid=,command= | rg '[t]elegram-mcp|com\.mshykhov\.telegram-mcp-readonly'
```

Reconnect both clients and confirm that `telegram-readonly` reports ready. A harmless `get_me` call may be used as the final live read-only check; do not print its Telegram-derived result into shared logs.

## Diagnose startup

If status fails, inspect only runtime diagnostics:

```sh
launchctl print "gui/$(id -u)/com.mshykhov.telegram-mcp-readonly"
tail -n 100 "${XDG_STATE_HOME:-$HOME/.local/state}/telegram-mcp-readonly/service.log"
```

`database is locked` means an old stdio process still owns the session. Stop only the exact stale `telegram-mcp` process, then reload the LaunchAgent. A bind error on port 8765 means another listener owns the configured endpoint; identify it before changing or terminating anything.

## Recover

Activation stores the previous plist beside the installed file as `com.mshykhov.telegram-mcp-readonly.plist.backup-<UTC timestamp>`. To restore it:

1. Stop the current service with `launchctl bootout "gui/$(id -u)/com.mshykhov.telegram-mcp-readonly"`.
2. Copy the selected backup over `~/Library/LaunchAgents/com.mshykhov.telegram-mcp-readonly.plist` and preserve mode `0600`.
3. Load it with `launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.mshykhov.telegram-mcp-readonly.plist`.
4. Restore the previous canonical Rulesync declaration, run dry-run generation, then generate all configured targets.

Do not rewrite or remove `.env` or the Telegram session during runtime recovery.
