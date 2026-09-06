import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from telegram_mcp.tools import chats, media, messages


async def _no_op(*args, **kwargs):
    return None


class FolderDialogsClient:
    def __init__(self):
        self.calls = []

    async def get_dialogs(self, *args, **kwargs):
        self.calls.append({"args": args, "kwargs": kwargs})
        return []


@pytest.mark.asyncio
async def test_list_chats_passes_custom_folder_to_telegram(monkeypatch):
    client = FolderDialogsClient()
    monkeypatch.setattr(chats, "get_client", lambda account=None: client)
    monkeypatch.setattr(chats, "ensure_connected", _no_op)

    result = await chats.list_chats(folder_id=7, limit=50)

    assert result == "No chats found matching the criteria."
    assert client.calls == [
        {
            "args": (),
            "kwargs": {"limit": 50, "archived": None, "folder": 7},
        }
    ]


@pytest.mark.asyncio
async def test_list_chats_rejects_conflicting_archive_and_folder(monkeypatch):
    client = FolderDialogsClient()
    monkeypatch.setattr(chats, "get_client", lambda account=None: client)
    monkeypatch.setattr(chats, "ensure_connected", _no_op)

    result = await chats.list_chats(folder_id=7, archived=True)

    assert result == "Use either folder_id or archived, not both."
    assert client.calls == []


class FakeGlobalMessage:
    def __init__(self, message_id, text, chat_name):
        self.id = message_id
        self.message = text
        self.date = f"2026-08-0{message_id}T12:00:00Z"
        self.chat_id = -1000 - message_id
        self.chat = None
        self.input_chat = None
        self._chat_name = chat_name

    def _finish_init(self, client, entities, input_chat):
        self.chat = SimpleNamespace(title=self._chat_name)
        self.input_chat = SimpleNamespace(peer=self.chat_id)


class FolderSearchClient:
    def __init__(self, result):
        self.result = result
        self.requests = []

    async def __call__(self, request):
        self.requests.append(request)
        return self.result


@pytest.mark.asyncio
async def test_search_global_uses_server_side_folder_filter(monkeypatch):
    first = FakeGlobalMessage(1, "alpha", "Work")
    second = FakeGlobalMessage(2, "beta", "Family")
    result = SimpleNamespace(messages=[first, second], users=[], chats=[], next_rate=0)
    client = FolderSearchClient(result)
    monkeypatch.setattr(messages, "get_client", lambda account=None: client)
    monkeypatch.setattr(messages, "ensure_connected", _no_op)
    monkeypatch.setattr(messages, "get_sender_info", lambda message: "Alice")

    payload_text = await messages.search_global(
        query="roadmap",
        page=2,
        page_size=1,
        folder_id=9,
    )
    payload = json.loads(payload_text.split("\n\n")[0])

    assert len(client.requests) == 1
    request = client.requests[0]
    assert request.q == "roadmap"
    assert request.folder_id == 9
    assert request.limit == 2
    assert payload["results"] == [
        {
            "chat_name": "Family",
            "chat_id": -1002,
            "id": 2,
            "sender": "Alice",
            "date": "2026-08-02T12:00:00Z",
            "text": "beta",
        }
    ]


class MediaDownloadClient:
    async def get_messages(self, entity, ids):
        return SimpleNamespace(media=object())

    async def download_media(self, message, file):
        final_path = Path(file).with_suffix(".jpg")
        final_path.write_bytes(b"image")
        return str(final_path)


@pytest.mark.asyncio
async def test_readonly_download_is_confined_to_configured_directory(monkeypatch, tmp_path):
    client = MediaDownloadClient()
    monkeypatch.setenv("TELEGRAM_READONLY_DOWNLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(media, "get_client", lambda account=None: client)

    async def resolve_entity(chat_id, cl):
        return SimpleNamespace(id=chat_id)

    monkeypatch.setattr(media, "resolve_entity", resolve_entity)

    result = await media.download_media_readonly(chat_id=-100123, message_id=42)
    payload = json.loads(result)
    downloaded = Path(payload["path"])

    assert payload["downloaded"] is True
    assert downloaded.parent == tmp_path.resolve()
    assert downloaded.read_bytes() == b"image"
    assert downloaded.stat().st_mode & 0o777 == 0o600
