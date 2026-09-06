# Shared Local MCP Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace per-client stdio Telegram MCP processes with one launchd-managed loopback Streamable HTTP service consumed by both configured agent clients.

**Architecture:** The Telegram repository owns a testable Python installer, LaunchAgent template, health check, and runbook. The agent-config repository keeps `telegram-readonly` in the top-level Rulesync inventory but changes its transport to `http://127.0.0.1:8765/mcp`, then generates both target configurations.

**Tech Stack:** Python 3.10+, plist/launchd, FastMCP Streamable HTTP, pytest, Rulesync 16.7.0, Node test runner.

**Status:** Completed on 2026-08-10. Live verification found one launchd-managed listener, 50 strict read-only tools, successful Codex initialization, and a connected Claude client. Telegram tests passed with 91.28% coverage; agent-config verification passed all 16 tests and both Rulesync generation checks.

---

### Task 1: Define the local service contract with failing tests

**Files:**
- Create: `tests/test_shared_service.py`
- Create: `runtime/launchd/com.mshykhov.telegram-mcp-readonly.plist.in`
- Create: `telegram_mcp/shared_service.py`

- [x] **Step 1: Write failing tests for deterministic rendering and preflight safety**

The tests must call the intended public helpers and assert:

```python
def test_render_launch_agent_uses_absolute_uv_and_loopback(tmp_path):
    rendered = render_launch_agent(
        template_path=TEMPLATE,
        checkout=tmp_path / "checkout",
        uv_path=tmp_path / "bin" / "uv",
        log_path=tmp_path / "state" / "service.log",
    )
    plist = plistlib.loads(rendered)
    assert plist["EnvironmentVariables"] == {
        "MCP_HOST": "127.0.0.1",
        "MCP_PORT": "8765",
        "MCP_TRANSPORT": "http",
    }
    assert plist["ProgramArguments"][0].startswith("/")


def test_validate_private_file_rejects_group_or_world_access(tmp_path):
    path = tmp_path / ".env"
    path.write_text("placeholder")
    path.chmod(0o640)
    with pytest.raises(ServiceConfigurationError, match="owner-only"):
        validate_private_file(path)
```

Add tests for missing files, non-executable `uv`, XML-sensitive checkout paths, required template placeholders, and strict write-tool exclusion in the health result.

- [x] **Step 2: Run the focused test and verify RED**

Run: `uv run pytest tests/test_shared_service.py -q`

Expected: collection fails because `telegram_mcp.shared_service` and its template do not exist.

### Task 2: Implement the installer and health check

**Files:**
- Create: `telegram_mcp/shared_service.py`
- Create: `runtime/launchd/com.mshykhov.telegram-mcp-readonly.plist.in`
- Modify: `pyproject.toml`
- Test: `tests/test_shared_service.py`

- [x] **Step 1: Implement the tested service helpers**

Expose these interfaces:

```python
class ServiceConfigurationError(RuntimeError):
    pass


def validate_private_file(path: Path) -> None: ...
def resolve_uv(executable: str = "uv") -> Path: ...
def render_launch_agent(
    template_path: Path,
    checkout: Path,
    uv_path: Path,
    log_path: Path,
) -> bytes: ...
async def probe_service(url: str = "http://127.0.0.1:8765/mcp") -> dict[str, object]: ...
def main(argv: list[str] | None = None) -> int: ...
```

`prepare` validates local private state and atomically writes the rendered plist to an owner-only prepared directory. `activate` backs up an existing user LaunchAgent, installs mode `0600`, uses `launchctl bootout/bootstrap`, and waits on `probe_service`. `check` validates source assets without user-scope writes. `status` performs only the MCP health probe. `--checkout` may select the persistent trusted checkout during worktree verification. No credential or session value may enter the plist, log message, or exception.

- [x] **Step 2: Add the CLI entry point**

Add:

```toml
telegram-mcp-shared-service = "telegram_mcp.shared_service:main"
```

- [x] **Step 3: Run the focused test and verify GREEN**

Run: `uv run pytest tests/test_shared_service.py -q`

Expected: all focused tests pass.

- [x] **Step 4: Run source-only dry-run checks**

Run:

```sh
uv run telegram-mcp-shared-service check
uv run telegram-mcp-shared-service prepare --dry-run --checkout "$HOME/IdeaProjects/telegram-mcp-readonly"
```

Expected: validation succeeds without writing a LaunchAgent or starting a process.

### Task 3: Document operation and ownership

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture/overview.md`
- Modify: `docs/runbooks/README.md`
- Create: `docs/runbooks/operate-shared-readonly-service.md`

- [x] **Step 1: Document setup, migration, status, and recovery**

The runbook must use the project CLI commands, keep the listener on loopback, explain the stdio SQLite-lock failure, require Rulesync for client configuration, and describe exact rollback through the timestamped LaunchAgent backup.

- [x] **Step 2: Update living architecture and README**

Record `telegram_mcp/shared_service.py` as owner of local lifecycle and make shared HTTP the recommended strict read-only agent setup. Keep generic direct client commands clearly separate from the managed Rulesync workflow.

- [x] **Step 3: Verify relative links and Markdown whitespace**

Run: `git diff --check`

Expected: exit 0, with every new index link resolving to a tracked file.

### Task 4: Migrate the canonical shared Rulesync declaration

**Files in sibling repository `../agent-config`:**
- Modify: `global/.rulesync/mcp.jsonc`
- Modify: `docs/reference/mcp-inventory.md`
- Modify: `docs/runbooks/verify-global-mcp.md`
- Modify: `tests/mcp-contract.test.mjs`

- [x] **Step 1: Write a failing contract test**

Assert the top-level declaration, not a target-only override:

```javascript
assert.deepEqual(mcp.mcpServers["telegram-readonly"], {
  type: "http",
  url: "http://127.0.0.1:8765/mcp",
});
```

Run: `node --test tests/mcp-contract.test.mjs`

Expected: FAIL because the canonical declaration is still stdio.

- [x] **Step 2: Change only the canonical shared declaration and living docs**

Replace the stdio command with the loopback URL, preserve the same server name, and describe the Telegram repository as owner of the LaunchAgent runtime.

- [x] **Step 3: Verify RED becomes GREEN and run Rulesync dry-run**

Run:

```sh
node --test tests/mcp-contract.test.mjs
npm run rulesync:check
```

Expected: the contract test passes and dry-run reports only the intended generated Codex and Claude MCP transport changes.

- [x] **Step 4: Generate all configured targets**

Run: `npm run rulesync:generate`

Expected: installed Codex and Claude declarations both contain `http://127.0.0.1:8765/mcp`.

### Task 5: Activate and verify the singleton

**Files:**
- User LaunchAgent: `~/Library/LaunchAgents/com.mshykhov.telegram-mcp-readonly.plist`
- Owner-local runtime state: `~/.local/share/telegram-mcp-readonly/`
- Owner-local log: `~/.local/state/telegram-mcp-readonly/service.log`

- [x] **Step 1: Integrate the Telegram branch into the trusted main checkout**

Run relevant tests and merge the implementation commit so the LaunchAgent points at the persistent checkout rather than the temporary worktree.

- [x] **Step 2: Prepare the service from the trusted checkout**

Run: `uv run telegram-mcp-shared-service prepare`

Expected: owner-only prepared plist with no credential values.

- [x] **Step 3: Release the old stdio session holder and activate**

Resolve the exact `telegram-mcp` child of the shared Codex app-server, stop only that process, then run `uv run telegram-mcp-shared-service activate`. Restart the approved relay only after current work is committed and recoverable.

- [x] **Step 4: Verify one runtime and both clients**

Run the service `status`, count matching processes/listeners, run the Rulesync verification suite, query a fresh Codex app-server status, and run `claude mcp get telegram-readonly`. Success requires one listening Telegram MCP process, 50 strict read-only tools, `get_me` present, known write tools absent, and both clients ready.

- [x] **Step 5: Run final repository verification**

Telegram repository:

```sh
uv run pytest --cov --cov-report=term-missing --cov-report=xml
uv run flake8 . --exclude=.venv --count --select=E9,F63,F7,F82 --show-source --statistics
uv run black --check .
npm ci
npm run rulesync:verify
```

Agent-config repository:

```sh
npm run verify
```

Expected: all commands exit 0 before commits or completion claims.
