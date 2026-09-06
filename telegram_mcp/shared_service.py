"""Local lifecycle helpers for one shared strict read-only MCP service."""

from __future__ import annotations

import argparse
import asyncio
import os
import plistlib
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from xml.sax.saxutils import escape

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


LABEL = "com.mshykhov.telegram-mcp-readonly"
DEFAULT_URL = "http://127.0.0.1:8765/mcp"
ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "runtime" / "launchd" / f"{LABEL}.plist.in"
DEFAULT_DATA_DIR = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share")) / (
    "telegram-mcp-readonly"
)
DEFAULT_STATE_DIR = Path(os.getenv("XDG_STATE_HOME", Path.home() / ".local" / "state")) / (
    "telegram-mcp-readonly"
)
DEFAULT_LAUNCH_AGENT = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
TEMPLATE_REPLACEMENTS = {
    "@TELEGRAM_MCP_CHECKOUT@": "checkout",
    "@TELEGRAM_MCP_LOG_PATH@": "log_path",
    "@TELEGRAM_MCP_UV@": "uv_path",
}
KNOWN_WRITE_TOOLS = frozenset(
    {
        "delete_message",
        "delete_messages",
        "edit_message",
        "forward_message",
        "mark_read",
        "send_message",
    }
)


class ServiceConfigurationError(RuntimeError):
    """Raised when the local shared-service boundary is unsafe or incomplete."""


def validate_private_file(path: Path) -> None:
    """Require an existing regular file with no group or world permissions."""
    if path.is_symlink():
        raise ServiceConfigurationError(f"Private file cannot be a symlink: {path}")
    if not path.is_file():
        raise ServiceConfigurationError(f"Required private file is missing: {path}")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise ServiceConfigurationError(f"Private file must be owner-only: {path}")


def validate_private_directory(path: Path) -> None:
    """Require an existing directory with no group or world permissions."""
    if path.is_symlink():
        raise ServiceConfigurationError(f"Private directory cannot be a symlink: {path}")
    if not path.is_dir():
        raise ServiceConfigurationError(f"Required private directory is missing: {path}")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise ServiceConfigurationError(f"Private directory must be owner-only: {path}")


def resolve_uv(executable: str = "uv") -> Path:
    """Resolve an executable uv command to an absolute path."""
    resolved = shutil.which(executable)
    if resolved is None:
        raise ServiceConfigurationError(f"uv executable was not found: {executable}")
    path = Path(resolved).resolve()
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ServiceConfigurationError(f"uv path is not executable: {path}")
    return path


def render_launch_agent(
    template_path: Path,
    checkout: Path,
    uv_path: Path,
    log_path: Path,
) -> bytes:
    """Render and validate the LaunchAgent without reading Telegram secrets."""
    try:
        content = template_path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise ServiceConfigurationError(
            f"LaunchAgent template is missing: {template_path}"
        ) from error

    values = {
        "checkout": checkout.resolve(),
        "log_path": log_path.resolve(),
        "uv_path": uv_path.resolve(),
    }
    missing = sorted(token for token in TEMPLATE_REPLACEMENTS if token not in content)
    if missing:
        raise ServiceConfigurationError(
            f"LaunchAgent template is missing placeholder(s): {', '.join(missing)}"
        )

    for token, value_name in TEMPLATE_REPLACEMENTS.items():
        content = content.replace(token, escape(str(values[value_name])))

    rendered = content.encode("utf-8")
    try:
        plistlib.loads(rendered)
    except Exception as error:
        raise ServiceConfigurationError("Rendered LaunchAgent is not valid plist XML") from error
    return rendered


def validate_tool_surface(tool_names: list[str]) -> dict[str, object]:
    """Reject an incomplete or mutating tool surface and return safe metadata."""
    names = set(tool_names)
    if "get_me" not in names:
        raise ServiceConfigurationError("Shared MCP health check did not expose get_me")
    exposed_writes = sorted(names & KNOWN_WRITE_TOOLS)
    if exposed_writes:
        raise ServiceConfigurationError(
            f"Shared MCP exposed write tools: {', '.join(exposed_writes)}"
        )
    return {
        "get_me_exposed": True,
        "tool_count": len(names),
        "write_tools_exposed": exposed_writes,
    }


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _ensure_private_directory(path: Path) -> None:
    if path.is_symlink():
        raise ServiceConfigurationError(f"Managed directory cannot be a symlink: {path}")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)


def _resolve_managed_directory(path: Path, *, checkout: Path) -> Path:
    resolved = path.expanduser().resolve()
    broad_paths = {Path("/"), Path.home().resolve(), checkout.resolve()}
    if resolved in broad_paths:
        raise ServiceConfigurationError(f"Refusing broad managed path: {resolved}")
    return resolved


def _write_private_file(path: Path, content: bytes) -> None:
    if path.is_symlink():
        raise ServiceConfigurationError(f"Managed file cannot be a symlink: {path}")
    _ensure_private_directory(path.parent)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def prepare_service(
    *,
    checkout: Path,
    uv_path: Path,
    template_path: Path = TEMPLATE_PATH,
    data_dir: Path,
    state_dir: Path,
    dry_run: bool = False,
) -> Path:
    """Validate local state and stage an owner-only LaunchAgent."""
    checkout = checkout.resolve()
    uv_path = resolve_uv(str(uv_path))
    data_dir = _resolve_managed_directory(data_dir, checkout=checkout)
    state_dir = _resolve_managed_directory(state_dir, checkout=checkout)
    validate_private_file(checkout / ".env")
    validate_private_directory(checkout / ".local")
    validate_private_file(checkout / ".local" / "telegram-readonly.session")

    prepared_dir = data_dir / "prepared"
    prepared_plist = prepared_dir / f"{LABEL}.plist"
    log_path = state_dir / "service.log"
    rendered = render_launch_agent(
        template_path=template_path,
        checkout=checkout,
        uv_path=uv_path,
        log_path=log_path,
    )
    if dry_run:
        return prepared_plist

    _ensure_private_directory(data_dir)
    _ensure_private_directory(state_dir)
    if log_path.exists():
        validate_private_file(log_path)
    else:
        _write_private_file(log_path, b"")

    temporary_dir = Path(tempfile.mkdtemp(prefix=".prepare.", dir=data_dir))
    temporary_dir.chmod(0o700)
    try:
        staged_plist = temporary_dir / f"{LABEL}.plist"
        _write_private_file(staged_plist, rendered)
        if prepared_dir.exists():
            backup = data_dir / f"prepared.backup-{_timestamp()}"
            os.replace(prepared_dir, backup)
        os.replace(temporary_dir, prepared_dir)
    finally:
        if temporary_dir.exists():
            shutil.rmtree(temporary_dir)

    validate_private_file(prepared_plist)
    return prepared_plist


def install_launch_agent(prepared_plist: Path, launch_agent: Path) -> Path | None:
    """Install a prepared plist atomically and retain the previous file."""
    validate_private_file(prepared_plist)
    if launch_agent.is_symlink():
        raise ServiceConfigurationError(f"LaunchAgent cannot be a symlink: {launch_agent}")
    if launch_agent.parent.is_symlink():
        raise ServiceConfigurationError(
            f"LaunchAgent directory cannot be a symlink: {launch_agent.parent}"
        )
    launch_agent.parent.mkdir(mode=0o700, parents=True, exist_ok=True)

    backup = None
    if launch_agent.exists():
        backup = launch_agent.with_name(f"{launch_agent.name}.backup-{_timestamp()}")
        shutil.copy2(launch_agent, backup)
        backup.chmod(0o600)
    _write_private_file(launch_agent, prepared_plist.read_bytes())
    return backup


async def probe_service(url: str = DEFAULT_URL) -> dict[str, object]:
    """Initialize the local MCP endpoint and validate its exposed tool names."""
    async with streamablehttp_client(
        url=url,
        timeout=5,
        sse_read_timeout=5,
    ) as (read_stream, write_stream, _get_session_id):
        async with ClientSession(read_stream, write_stream) as session:
            await asyncio.wait_for(session.initialize(), timeout=5)
            result = await asyncio.wait_for(session.list_tools(), timeout=5)
    return validate_tool_surface([tool.name for tool in result.tools])


def _probe_once(url: str) -> dict[str, object]:
    return asyncio.run(probe_service(url))


def _wait_for_health(
    url: str,
    health_probe: Callable[[str], dict[str, object]],
    *,
    attempts: int = 60,
) -> dict[str, object]:
    last_error = None
    for attempt in range(attempts):
        try:
            return health_probe(url)
        except Exception as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(0.25)
    raise ServiceConfigurationError(
        f"Shared MCP did not become healthy after {attempts} attempts: "
        f"{type(last_error).__name__}"
    ) from last_error


def activate_service(
    *,
    prepared_plist: Path,
    launch_agent: Path = DEFAULT_LAUNCH_AGENT,
    launchctl: str = "/bin/launchctl",
    url: str = DEFAULT_URL,
    dry_run: bool = False,
    command_runner: Callable[..., object] = subprocess.run,
    health_probe: Callable[[str], dict[str, object]] = _probe_once,
    health_attempts: int = 60,
) -> dict[str, object]:
    """Install, reload, and health-check the singleton LaunchAgent."""
    validate_private_file(prepared_plist)
    if dry_run:
        return {"dry_run": True}

    backup = install_launch_agent(prepared_plist, launch_agent)
    domain = f"gui/{os.getuid()}"
    service = f"{domain}/{LABEL}"
    try:
        loaded = command_runner(
            [launchctl, "print", service],
            check=False,
            capture_output=True,
            text=True,
        )
        if getattr(loaded, "returncode", 1) == 0:
            command_runner(
                [launchctl, "bootout", service],
                check=True,
                capture_output=True,
                text=True,
            )
        command_runner(
            [launchctl, "bootstrap", domain, str(launch_agent)],
            check=True,
            capture_output=True,
            text=True,
        )
        return _wait_for_health(url, health_probe, attempts=health_attempts)
    except Exception as error:
        command_runner(
            [launchctl, "bootout", service],
            check=False,
            capture_output=True,
            text=True,
        )
        if backup is not None:
            _write_private_file(launch_agent, backup.read_bytes())
            command_runner(
                [launchctl, "bootstrap", domain, str(launch_agent)],
                check=False,
                capture_output=True,
                text=True,
            )
        elif launch_agent.exists():
            launch_agent.unlink()
        raise ServiceConfigurationError(
            "Failed to activate shared Telegram MCP service"
        ) from error


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage one loopback strict read-only Telegram MCP service."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="Validate repository-owned service assets.")
    check.add_argument("--uv", default="uv")

    prepare = subparsers.add_parser("prepare", help="Stage an owner-only LaunchAgent.")
    prepare.add_argument("--checkout", type=Path, default=ROOT)
    prepare.add_argument("--uv", default="uv")
    prepare.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    prepare.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    prepare.add_argument("--dry-run", action="store_true")

    activate = subparsers.add_parser("activate", help="Install and start the LaunchAgent.")
    activate.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    activate.add_argument("--launch-agent", type=Path, default=DEFAULT_LAUNCH_AGENT)
    activate.add_argument("--launchctl", default="/bin/launchctl")
    activate.add_argument("--url", default=DEFAULT_URL)
    activate.add_argument("--dry-run", action="store_true")

    status = subparsers.add_parser("status", help="Initialize MCP and validate its tool surface.")
    status.add_argument("--url", default=DEFAULT_URL)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the local service manager without exposing private state values."""
    arguments = _build_parser().parse_args(argv)
    try:
        if arguments.command == "check":
            uv_path = resolve_uv(arguments.uv)
            render_launch_agent(
                template_path=TEMPLATE_PATH,
                checkout=ROOT,
                uv_path=uv_path,
                log_path=DEFAULT_STATE_DIR / "service.log",
            )
            print("Shared Telegram MCP service checks passed.")
            return 0

        if arguments.command == "prepare":
            prepared = prepare_service(
                checkout=arguments.checkout,
                uv_path=resolve_uv(arguments.uv),
                template_path=TEMPLATE_PATH,
                data_dir=arguments.data_dir,
                state_dir=arguments.state_dir,
                dry_run=arguments.dry_run,
            )
            prefix = "DRY-RUN: would prepare" if arguments.dry_run else "Prepared"
            print(f"{prefix} {prepared}")
            return 0

        if arguments.command == "activate":
            summary = activate_service(
                prepared_plist=(arguments.data_dir / "prepared" / f"{LABEL}.plist"),
                launch_agent=arguments.launch_agent,
                launchctl=arguments.launchctl,
                url=arguments.url,
                dry_run=arguments.dry_run,
            )
            prefix = "DRY-RUN: would activate" if arguments.dry_run else "Activated"
            print(f"{prefix} {LABEL}: {summary}")
            return 0

        summary = asyncio.run(probe_service(arguments.url))
        print(f"Shared Telegram MCP healthy: {summary}")
        return 0
    except ServiceConfigurationError as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception as error:
        print(f"Shared MCP operation failed: {type(error).__name__}", file=sys.stderr)
        return 1
