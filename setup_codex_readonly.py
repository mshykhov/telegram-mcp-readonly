#!/usr/bin/env python3
"""One-time local setup for the Codex strict-read-only Telegram server.

The script deliberately creates a file-based Telethon session and never prints
or stores a portable StringSession. Secrets remain in this checkout's ignored
``.env`` and ``.local`` paths with owner-only permissions.
"""

from __future__ import annotations

import getpass
import os
import re
import tempfile
from pathlib import Path

from dotenv import dotenv_values
from telethon.sync import TelegramClient

from session_string_generator import _qr_login
from telegram_mcp.client_identity import client_identity_kwargs

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"
STATE_DIR = ROOT / ".local"
SESSION_BASENAME = STATE_DIR / "telegram-readonly"
DOWNLOAD_DIR = ROOT / "downloads"

_REMOVE_KEYS = {
    "TELEGRAM_SESSION_STRING",
    "TELEGRAM_SESSION_STRINGS",
}


def _credential(existing: dict[str, object], key: str, *, secret: bool = False) -> str:
    current = str(existing.get(key) or "").strip()
    if current:
        return current
    prompt = f"{key}: "
    return (getpass.getpass(prompt) if secret else input(prompt)).strip()


def _write_env(values: dict[str, str]) -> None:
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    remaining = dict(values)
    output: list[str] = []

    for line in lines:
        match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        if not match:
            output.append(line)
            continue
        key = match.group(1)
        if key in _REMOVE_KEYS:
            continue
        if key in remaining:
            output.append(f"{key}={remaining.pop(key)}")
        else:
            output.append(line)

    if output and output[-1] != "":
        output.append("")
    if remaining:
        output.append("# Managed by setup_codex_readonly.py")
        output.extend(f"{key}={value}" for key, value in remaining.items())

    fd, temporary_name = tempfile.mkstemp(prefix=".env.", dir=ROOT, text=True)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("\n".join(output).rstrip() + "\n")
        temporary_path.chmod(0o600)
        os.replace(temporary_path, ENV_PATH)
        ENV_PATH.chmod(0o600)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def main() -> None:
    existing = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
    if not existing.get("TELEGRAM_API_ID") or not existing.get("TELEGRAM_API_HASH"):
        print("Create an application at https://my.telegram.org/apps, then paste its values.")

    api_id_raw = _credential(existing, "TELEGRAM_API_ID")
    api_hash = _credential(existing, "TELEGRAM_API_HASH", secret=True)
    try:
        api_id = int(api_id_raw)
    except ValueError as error:
        raise SystemExit("TELEGRAM_API_ID must be an integer.") from error
    if not api_hash:
        raise SystemExit("TELEGRAM_API_HASH cannot be empty.")

    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    DOWNLOAD_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    STATE_DIR.chmod(0o700)
    DOWNLOAD_DIR.chmod(0o700)

    client = TelegramClient(
        str(SESSION_BASENAME),
        api_id,
        api_hash,
        **client_identity_kwargs(),
    )
    try:
        client.connect()
        if not client.is_user_authorized():
            _qr_login(client)
        if not client.is_user_authorized():
            raise SystemExit("Telegram authorization did not complete.")
    finally:
        client.disconnect()

    session_file = SESSION_BASENAME.with_suffix(".session")
    if not session_file.exists():
        raise SystemExit(f"Expected Telegram session was not created: {session_file}")
    session_file.chmod(0o600)

    _write_env(
        {
            "TELEGRAM_API_ID": str(api_id),
            "TELEGRAM_API_HASH": api_hash,
            "TELEGRAM_SESSION_NAME": str(SESSION_BASENAME),
            "TELEGRAM_EXPOSED_TOOLS": "strict-read-only",
            "TELEGRAM_READONLY_DOWNLOAD_DIR": str(DOWNLOAD_DIR),
            "TELEGRAM_DEVICE_MODEL": "Codex Telegram Read-only",
            "TELEGRAM_SYSTEM_VERSION": "macOS",
            "TELEGRAM_APP_VERSION": "2.0.1-readonly",
            "TELEGRAM_EVENT_FEED": "0",
        }
    )

    print("\nTelegram authorized locally.")
    print(f"Session: {session_file} (mode 0600)")
    print(f"Config:  {ENV_PATH} (mode 0600)")
    print("No session string was printed or stored in Codex configuration.")


if __name__ == "__main__":
    main()
