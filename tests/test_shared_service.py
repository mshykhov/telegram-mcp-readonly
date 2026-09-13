import plistlib
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from telegram_mcp import shared_service
from telegram_mcp.shared_service import (
    ServiceConfigurationError,
    activate_service,
    install_launch_agent,
    main,
    prepare_service,
    probe_service,
    render_launch_agent,
    resolve_uv,
    validate_private_directory,
    validate_private_file,
    validate_tool_surface,
)

TEMPLATE = (
    Path(__file__).parents[1]
    / "runtime"
    / "launchd"
    / "com.mshykhov.telegram-mcp-readonly.plist.in"
)


def test_render_launch_agent_uses_absolute_uv_and_loopback(tmp_path):
    checkout = tmp_path / "checkout & trusted"
    uv_path = tmp_path / "bin" / "uv"
    log_path = tmp_path / "state" / "service.log"

    rendered = render_launch_agent(
        template_path=TEMPLATE,
        checkout=checkout,
        uv_path=uv_path,
        log_path=log_path,
    )

    plist = plistlib.loads(rendered)
    assert plist["Label"] == "com.mshykhov.telegram-mcp-readonly"
    assert plist["ProgramArguments"] == [
        str(uv_path),
        "--directory",
        str(checkout),
        "run",
        "telegram-mcp",
    ]
    assert plist["WorkingDirectory"] == str(checkout)
    assert plist["EnvironmentVariables"] == {
        "MCP_HOST": "127.0.0.1",
        "MCP_PORT": "8765",
        "MCP_TRANSPORT": "http",
    }
    assert plist["StandardErrorPath"] == str(log_path)
    assert plist["StandardOutPath"] == str(log_path)


def test_render_launch_agent_rejects_missing_template_placeholder(tmp_path):
    template = tmp_path / "broken.plist.in"
    template.write_text("@TELEGRAM_MCP_UV@", encoding="utf-8")

    with pytest.raises(ServiceConfigurationError, match="placeholder"):
        render_launch_agent(
            template_path=template,
            checkout=tmp_path / "checkout",
            uv_path=tmp_path / "uv",
            log_path=tmp_path / "service.log",
        )


def test_validate_private_file_accepts_owner_only_file(tmp_path):
    path = tmp_path / ".env"
    path.write_text("placeholder", encoding="utf-8")
    path.chmod(0o600)

    validate_private_file(path)


def test_validate_private_file_rejects_group_or_world_access(tmp_path):
    path = tmp_path / ".env"
    path.write_text("placeholder", encoding="utf-8")
    path.chmod(0o640)

    with pytest.raises(ServiceConfigurationError, match="owner-only"):
        validate_private_file(path)


def test_validate_private_file_rejects_missing_path(tmp_path):
    with pytest.raises(ServiceConfigurationError, match="missing"):
        validate_private_file(tmp_path / ".env")


def test_validate_private_file_rejects_symlink(tmp_path):
    target = tmp_path / "target"
    target.write_text("placeholder", encoding="utf-8")
    target.chmod(0o600)
    link = tmp_path / ".env"
    link.symlink_to(target)

    with pytest.raises(ServiceConfigurationError, match="symlink"):
        validate_private_file(link)


def test_validate_private_directory_rejects_symlink(tmp_path):
    target = tmp_path / "target"
    target.mkdir(mode=0o700)
    link = tmp_path / ".local"
    link.symlink_to(target, target_is_directory=True)

    with pytest.raises(ServiceConfigurationError, match="symlink"):
        validate_private_directory(link)


def test_resolve_uv_requires_executable_absolute_path(tmp_path):
    executable = tmp_path / "uv"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o700)

    assert resolve_uv(str(executable)) == executable.resolve()


def test_resolve_uv_rejects_non_executable_path(tmp_path):
    executable = tmp_path / "uv"
    executable.write_text("placeholder", encoding="utf-8")
    executable.chmod(0o600)

    with pytest.raises(ServiceConfigurationError, match="executable"):
        resolve_uv(str(executable))


def test_validate_tool_surface_reports_strict_readonly_tools():
    summary = validate_tool_surface(["get_me", "list_chats", "get_messages"])

    assert summary == {
        "get_me_exposed": True,
        "tool_count": 3,
        "write_tools_exposed": [],
    }


@pytest.mark.parametrize(
    ("tools", "message"),
    [
        (["list_chats"], "get_me"),
        (["get_me", "send_message"], "write tools"),
    ],
)
def test_validate_tool_surface_rejects_unsafe_or_incomplete_surface(tools, message):
    with pytest.raises(ServiceConfigurationError, match=message):
        validate_tool_surface(tools)


def _create_private_checkout(tmp_path):
    checkout = tmp_path / "checkout"
    state = checkout / ".local"
    state.mkdir(parents=True, mode=0o700)
    state.chmod(0o700)
    env_path = checkout / ".env"
    env_path.write_text("TELEGRAM_API_HASH=must-not-leak\n", encoding="utf-8")
    env_path.chmod(0o600)
    session_path = state / "telegram-readonly.session"
    session_path.write_bytes(b"private-session-placeholder")
    session_path.chmod(0o600)
    return checkout


def _create_executable(tmp_path):
    executable = tmp_path / "bin" / "uv"
    executable.parent.mkdir()
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o700)
    return executable


def test_prepare_service_writes_owner_only_runtime_without_secrets(tmp_path):
    checkout = _create_private_checkout(tmp_path)
    uv_path = _create_executable(tmp_path)
    data_dir = tmp_path / "data"
    state_dir = tmp_path / "state"

    prepared = prepare_service(
        checkout=checkout,
        uv_path=uv_path,
        template_path=TEMPLATE,
        data_dir=data_dir,
        state_dir=state_dir,
    )

    content = prepared.read_bytes()
    assert b"must-not-leak" not in content
    assert stat.S_IMODE(prepared.stat().st_mode) == 0o600
    assert stat.S_IMODE(prepared.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(data_dir.stat().st_mode) == 0o700
    log_path = state_dir / "service.log"
    assert stat.S_IMODE(state_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(log_path.stat().st_mode) == 0o600


def test_prepare_service_dry_run_performs_no_writes(tmp_path):
    checkout = _create_private_checkout(tmp_path)
    uv_path = _create_executable(tmp_path)
    data_dir = tmp_path / "data"
    state_dir = tmp_path / "state"

    prepared = prepare_service(
        checkout=checkout,
        uv_path=uv_path,
        template_path=TEMPLATE,
        data_dir=data_dir,
        state_dir=state_dir,
        dry_run=True,
    )

    assert prepared == data_dir / "prepared" / f"{shared_service.LABEL}.plist"
    assert not data_dir.exists()
    assert not state_dir.exists()


def test_prepare_service_preserves_existing_diagnostics(tmp_path):
    checkout = _create_private_checkout(tmp_path)
    uv_path = _create_executable(tmp_path)
    data_dir = tmp_path / "data"
    state_dir = tmp_path / "state"
    state_dir.mkdir(mode=0o700)
    log_path = state_dir / "service.log"
    log_path.write_bytes(b"existing diagnostics")
    log_path.chmod(0o600)

    prepare_service(
        checkout=checkout,
        uv_path=uv_path,
        template_path=TEMPLATE,
        data_dir=data_dir,
        state_dir=state_dir,
    )

    assert log_path.read_bytes() == b"existing diagnostics"


def test_prepare_service_rejects_non_private_session_directory(tmp_path):
    checkout = _create_private_checkout(tmp_path)
    (checkout / ".local").chmod(0o750)

    with pytest.raises(ServiceConfigurationError, match="directory must be owner-only"):
        prepare_service(
            checkout=checkout,
            uv_path=_create_executable(tmp_path),
            template_path=TEMPLATE,
            data_dir=tmp_path / "data",
            state_dir=tmp_path / "state",
            dry_run=True,
        )


@pytest.mark.parametrize("broad_path", [Path("/"), Path.home()])
def test_prepare_service_rejects_broad_managed_path(tmp_path, broad_path):
    checkout = _create_private_checkout(tmp_path)

    with pytest.raises(ServiceConfigurationError, match="broad managed path"):
        prepare_service(
            checkout=checkout,
            uv_path=_create_executable(tmp_path),
            template_path=TEMPLATE,
            data_dir=broad_path,
            state_dir=tmp_path / "state",
            dry_run=True,
        )


def test_prepare_service_rejects_checkout_as_managed_path(tmp_path):
    checkout = _create_private_checkout(tmp_path)

    with pytest.raises(ServiceConfigurationError, match="broad managed path"):
        prepare_service(
            checkout=checkout,
            uv_path=_create_executable(tmp_path),
            template_path=TEMPLATE,
            data_dir=checkout,
            state_dir=tmp_path / "state",
            dry_run=True,
        )


def test_install_launch_agent_backs_up_existing_file(tmp_path):
    prepared = tmp_path / "prepared.plist"
    prepared.write_bytes(b"new")
    prepared.chmod(0o600)
    launch_agent = tmp_path / "LaunchAgents" / "service.plist"
    launch_agent.parent.mkdir()
    launch_agent.write_bytes(b"old")
    launch_agent.chmod(0o600)

    backup = install_launch_agent(prepared, launch_agent)

    assert launch_agent.read_bytes() == b"new"
    assert stat.S_IMODE(launch_agent.stat().st_mode) == 0o600
    assert backup is not None
    assert backup.read_bytes() == b"old"


@pytest.mark.asyncio
async def test_probe_service_initializes_and_validates_tools(monkeypatch):
    class _Transport:
        async def __aenter__(self):
            return "read", "write", lambda: None

        async def __aexit__(self, exc_type, exc_value, traceback):
            return False

    class _Session:
        def __init__(self, read, write):
            assert (read, write) == ("read", "write")

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_value, traceback):
            return False

        async def initialize(self):
            return None

        async def list_tools(self):
            return SimpleNamespace(
                tools=[SimpleNamespace(name="get_me"), SimpleNamespace(name="list_chats")]
            )

    monkeypatch.setattr(shared_service, "streamablehttp_client", lambda **kwargs: _Transport())
    monkeypatch.setattr(shared_service, "ClientSession", _Session)

    assert await probe_service() == {
        "get_me_exposed": True,
        "tool_count": 2,
        "write_tools_exposed": [],
    }


def test_activate_service_reloads_launch_agent_and_checks_health(tmp_path):
    prepared = tmp_path / "prepared.plist"
    prepared.write_bytes(b"new")
    prepared.chmod(0o600)
    launch_agent = tmp_path / "LaunchAgents" / "service.plist"
    calls = []

    def command_runner(arguments, **kwargs):
        calls.append((arguments, kwargs))
        return SimpleNamespace(returncode=0 if arguments[1] == "print" else 0)

    summary = activate_service(
        prepared_plist=prepared,
        launch_agent=launch_agent,
        launchctl="/bin/launchctl",
        command_runner=command_runner,
        health_probe=lambda url: {
            "get_me_exposed": True,
            "tool_count": 50,
            "write_tools_exposed": [],
        },
    )

    commands = [arguments[1] for arguments, _kwargs in calls]
    assert commands == ["print", "bootout", "bootstrap"]
    assert launch_agent.read_bytes() == b"new"
    assert summary["tool_count"] == 50


def test_activate_service_dry_run_does_not_install_or_call_launchctl(tmp_path):
    prepared = tmp_path / "prepared.plist"
    prepared.write_bytes(b"new")
    prepared.chmod(0o600)
    launch_agent = tmp_path / "LaunchAgents" / "service.plist"

    summary = activate_service(
        prepared_plist=prepared,
        launch_agent=launch_agent,
        dry_run=True,
        command_runner=lambda *args, **kwargs: pytest.fail("launchctl was called"),
        health_probe=lambda url: pytest.fail("health probe was called"),
    )

    assert summary == {"dry_run": True}
    assert not launch_agent.exists()


def test_activate_service_restores_previous_agent_after_failed_health(tmp_path):
    prepared = tmp_path / "prepared.plist"
    prepared.write_bytes(b"new")
    prepared.chmod(0o600)
    launch_agent = tmp_path / "LaunchAgents" / "service.plist"
    launch_agent.parent.mkdir()
    launch_agent.write_bytes(b"old")
    launch_agent.chmod(0o600)
    calls = []

    def command_runner(arguments, **kwargs):
        calls.append(arguments[1])
        return SimpleNamespace(returncode=0)

    with pytest.raises(ServiceConfigurationError, match="Failed to activate"):
        activate_service(
            prepared_plist=prepared,
            launch_agent=launch_agent,
            command_runner=command_runner,
            health_probe=lambda url: (_ for _ in ()).throw(ConnectionError("not ready")),
            health_attempts=1,
        )

    assert launch_agent.read_bytes() == b"old"
    assert calls == ["print", "bootout", "bootstrap", "bootout", "bootstrap"]


def test_main_check_validates_source_bundle(tmp_path, capsys):
    uv_path = _create_executable(tmp_path)

    assert main(["check", "--uv", str(uv_path)]) == 0
    assert "checks passed" in capsys.readouterr().out


def test_main_prepare_dry_run_does_not_write_user_state(tmp_path, capsys):
    checkout = _create_private_checkout(tmp_path)
    uv_path = _create_executable(tmp_path)
    data_dir = tmp_path / "data"
    state_dir = tmp_path / "state"

    result = main(
        [
            "prepare",
            "--dry-run",
            "--checkout",
            str(checkout),
            "--uv",
            str(uv_path),
            "--data-dir",
            str(data_dir),
            "--state-dir",
            str(state_dir),
        ]
    )

    assert result == 0
    assert "DRY-RUN" in capsys.readouterr().out
    assert not data_dir.exists()
    assert not state_dir.exists()


def test_main_status_reports_transport_failure_without_traceback(monkeypatch, capsys):
    async def failing_probe(url):
        raise ConnectionError("private transport detail")

    monkeypatch.setattr(shared_service, "probe_service", failing_probe)

    assert main(["status"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "Shared MCP operation failed: ConnectionError\n"
    assert "private transport detail" not in captured.err
