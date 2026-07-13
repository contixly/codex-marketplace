import asyncio
import json
from datetime import datetime, timezone
from io import BytesIO
from stat import S_IMODE
from types import SimpleNamespace

import pytest
from telethon import types

from telegram_mcp import auth, client as client_module, status
from telegram_mcp.client import (
    create_client,
    dialog_to_payload,
    download_media,
    entity_label,
    list_dialogs,
    message_to_payload,
    read_messages,
    resolve_entity,
    send_document,
    send_message,
    send_photo,
)
from telegram_mcp.config import TelegramSettings
from telegram_mcp.status import build_status_payload, collect_status


def make_settings(
    tmp_path,
    api_id=12345,
    api_hash="test-hash",
    download_max_bytes=20 * 1024 * 1024,
):
    return TelegramSettings(
        env_file=tmp_path / "telegram.env",
        api_id=api_id,
        api_hash=api_hash,
        session_name=str(tmp_path / "personal"),
        session_file=tmp_path / "personal.session",
        downloads_dir=tmp_path / "downloads",
        dialog_limit_default=50,
        message_limit_default=20,
        message_limit_max=100,
        upload_max_bytes=20 * 1024 * 1024,
        download_max_bytes=download_max_bytes,
    )


def test_status_redacts_credentials(tmp_path):
    settings = make_settings(tmp_path)
    payload = build_status_payload(settings, authorized=False)
    assert payload["api_id_configured"] is True
    assert payload["api_hash_configured"] is True
    assert payload["limits"]["download_max_bytes"] == 20 * 1024 * 1024
    assert "test-hash" not in repr(payload)


def test_message_payload_is_bounded_and_omits_media_bytes():
    message = SimpleNamespace(
        id=7,
        date=datetime(2026, 7, 13, tzinfo=timezone.utc),
        sender_id=8,
        text="hello",
        message="fallback",
        media=b"private-media",
    )
    assert message_to_payload(message) == {
        "id": 7,
        "date": "2026-07-13T00:00:00+00:00",
        "sender_id": 8,
        "text": "hello",
        "has_media": True,
    }


class FakeDialogs:
    def __init__(self, dialog):
        self.dialog = dialog

    async def get_entity(self, recipient):
        raise ValueError(recipient)

    async def iter_dialogs(self, limit=None):
        yield self.dialog


def test_entity_resolution_falls_back_to_dialog_name():
    entity = SimpleNamespace(id=42, title="Example Team")
    dialog = SimpleNamespace(name="Example Team", id=-10042, entity=entity, unread_count=0)
    assert asyncio.run(resolve_entity(FakeDialogs(dialog), "Example Team")) is entity


def test_safe_labels_and_dialog_payloads():
    entity = SimpleNamespace(id=42, username="example", title="Example Team")
    dialog = SimpleNamespace(name="Example Team", id=-10042, entity=entity, unread_count=3)
    assert entity_label(entity) == "Example Team @example id=42"
    assert dialog_to_payload(dialog)["unread_count"] == 3


def test_create_client_rejects_missing_credentials(tmp_path):
    settings = make_settings(tmp_path / "runtime", api_id=None, api_hash="")
    with pytest.raises(RuntimeError, match="Run the plugin setup first"):
        create_client(settings)
    assert not settings.session_file.exists()
    assert not settings.session_file.parent.exists()


def test_create_client_secures_fresh_session_before_telethon_opens_it(tmp_path, monkeypatch):
    settings = make_settings(tmp_path / "runtime")
    sentinel = object()

    def fake_telegram_client(session_name, api_id, api_hash):
        assert session_name == settings.session_name
        assert api_id == settings.api_id
        assert api_hash == settings.api_hash
        assert settings.session_file.exists()
        assert S_IMODE(settings.session_file.parent.stat().st_mode) == 0o700
        assert S_IMODE(settings.session_file.stat().st_mode) == 0o600
        return sentinel

    monkeypatch.setattr(client_module, "TelegramClient", fake_telegram_client)

    assert create_client(settings) is sentinel


def test_create_client_corrects_existing_session_permissions_before_open(tmp_path, monkeypatch):
    settings = make_settings(tmp_path / "runtime")
    settings.session_file.parent.mkdir(parents=True)
    settings.session_file.parent.chmod(0o755)
    settings.session_file.write_bytes(b"existing-session")
    settings.session_file.chmod(0o644)

    def fake_telegram_client(session_name, api_id, api_hash):
        assert S_IMODE(settings.session_file.parent.stat().st_mode) == 0o700
        assert S_IMODE(settings.session_file.stat().st_mode) == 0o600
        return object()

    monkeypatch.setattr(client_module, "TelegramClient", fake_telegram_client)

    create_client(settings)


def test_payload_helpers_return_only_safe_fields():
    entity = SimpleNamespace(id=42, username="example")
    dialog = SimpleNamespace(name="Example", id=None, entity=entity, unread_count=0)
    message = SimpleNamespace(id=7, date=None, sender_id=None, text=None, message="fallback", media=None)

    assert dialog_to_payload(dialog) == {
        "name": "Example",
        "id": 42,
        "username": "example",
        "entity_type": "SimpleNamespace",
        "unread_count": 0,
    }
    assert message_to_payload(message) == {
        "id": 7,
        "date": None,
        "sender_id": None,
        "text": "fallback",
        "has_media": False,
    }


class FakeOperations:
    def __init__(self, dialogs=(), messages=()):
        self.dialogs = dialogs
        self.messages = messages
        self.iter_dialogs_limit = None
        self.get_messages_calls = []
        self.download_file = None
        self.send_file_call = None

    async def iter_dialogs(self, limit=None):
        self.iter_dialogs_limit = limit
        for dialog in self.dialogs:
            yield dialog

    async def get_entity(self, recipient):
        return f"entity:{recipient}"

    async def get_messages(self, entity, **kwargs):
        self.get_messages_calls.append((entity, kwargs))
        if "ids" in kwargs:
            return self.messages[0] if self.messages else None
        return self.messages

    async def download_media(self, message, file):
        self.download_file = file
        return str(self.downloaded_path)

    async def send_message(self, entity, text):
        self.send_message_call = (entity, text)
        return self.messages[0]

    async def send_file(self, entity, **kwargs):
        self.send_file_call = (entity, kwargs)
        return self.messages[0]


def test_list_dialogs_honors_limit_and_filters_safe_payloads():
    matching = SimpleNamespace(
        name="Example Team",
        id=-10042,
        entity=SimpleNamespace(id=42, username="example"),
        unread_count=3,
    )
    other = SimpleNamespace(
        name="Other",
        id=-10043,
        entity=SimpleNamespace(id=43, username="other"),
        unread_count=0,
    )
    client = FakeOperations(dialogs=[matching, other])

    payloads = asyncio.run(list_dialogs(client, "TEAM", 7))

    assert client.iter_dialogs_limit == 7
    assert payloads == [dialog_to_payload(matching)]


def test_read_messages_resolves_recipient_and_honors_limit():
    message = SimpleNamespace(id=7, date=None, sender_id=8, text="hello", media=None)
    client = FakeOperations(messages=[message])

    payloads = asyncio.run(read_messages(client, "example", 4))

    assert client.get_messages_calls == [("entity:example", {"limit": 4})]
    assert payloads == [message_to_payload(message)]


def test_download_media_secures_runtime_directories_and_returns_absolute_path(tmp_path):
    message = SimpleNamespace(
        id=7,
        media=object(),
        file=SimpleNamespace(size=1024),
    )
    client = FakeOperations(messages=[message])
    data_dir = tmp_path / "runtime"
    downloads_dir = data_dir / "downloads"
    downloads_dir.mkdir(parents=True)
    data_dir.chmod(0o755)
    downloads_dir.chmod(0o755)
    client.downloaded_path = downloads_dir / "photo.jpg"
    settings = make_settings(data_dir)

    path = asyncio.run(download_media(client, settings, "example", 7))

    assert S_IMODE(data_dir.stat().st_mode) == 0o700
    assert S_IMODE(settings.downloads_dir.stat().st_mode) == 0o700
    assert client.download_file == str(settings.downloads_dir)
    assert path == str(client.downloaded_path.resolve())


def test_download_media_rejects_oversized_media_before_writing(tmp_path):
    message = SimpleNamespace(
        id=7,
        media=object(),
        file=SimpleNamespace(size=11),
    )
    client = FakeOperations(messages=[message])
    client.downloaded_path = tmp_path / "downloads" / "large.bin"
    settings = make_settings(tmp_path, download_max_bytes=10)

    with pytest.raises(RuntimeError, match="11 bytes exceeds the configured 10-byte"):
        asyncio.run(download_media(client, settings, "example", 7))

    assert client.download_file is None
    assert not settings.downloads_dir.exists()


def test_download_media_checks_the_video_variant_telethon_selects_for_photos(tmp_path):
    photo = types.Photo(
        id=1,
        access_hash=2,
        file_reference=b"reference",
        date=None,
        sizes=[types.PhotoSize(type="x", w=100, h=100, size=5)],
        dc_id=4,
        video_sizes=[types.VideoSize(type="v", w=100, h=100, size=11)],
    )
    message = SimpleNamespace(
        id=7,
        media=types.MessageMediaPhoto(photo=photo),
        file=SimpleNamespace(size=5),
        photo=photo,
    )
    client = FakeOperations(messages=[message])
    client.downloaded_path = tmp_path / "downloads" / "animated.mp4"
    settings = make_settings(tmp_path, download_max_bytes=10)

    with pytest.raises(RuntimeError, match="11 bytes exceeds the configured 10-byte"):
        asyncio.run(download_media(client, settings, "example", 7))

    assert client.download_file is None
    assert not settings.downloads_dir.exists()


def test_download_media_checks_document_before_photo_in_web_previews(tmp_path):
    photo = types.Photo(
        id=1,
        access_hash=2,
        file_reference=b"photo-reference",
        date=None,
        sizes=[types.PhotoSize(type="x", w=100, h=100, size=5)],
        dc_id=4,
    )
    document = types.Document(
        id=3,
        access_hash=4,
        file_reference=b"document-reference",
        date=None,
        mime_type="application/octet-stream",
        size=11,
        dc_id=4,
        attributes=[],
    )
    webpage = types.WebPage(
        id=5,
        url="https://example.invalid",
        display_url="example.invalid",
        hash=0,
        photo=photo,
        document=document,
    )
    message = SimpleNamespace(
        id=7,
        media=types.MessageMediaWebPage(webpage=webpage),
        file=SimpleNamespace(size=5),
        photo=photo,
    )
    client = FakeOperations(messages=[message])
    client.downloaded_path = tmp_path / "downloads" / "preview.bin"
    settings = make_settings(tmp_path, download_max_bytes=10)

    with pytest.raises(RuntimeError, match="11 bytes exceeds the configured 10-byte"):
        asyncio.run(download_media(client, settings, "example", 7))

    assert client.download_file is None
    assert not settings.downloads_dir.exists()


def test_download_media_rejects_unknown_size_before_writing(tmp_path):
    message = SimpleNamespace(id=7, media=object(), file=None)
    client = FakeOperations(messages=[message])
    client.downloaded_path = tmp_path / "downloads" / "unknown.bin"
    settings = make_settings(tmp_path)

    with pytest.raises(RuntimeError, match="size is unavailable"):
        asyncio.run(download_media(client, settings, "example", 7))

    assert client.download_file is None
    assert not settings.downloads_dir.exists()


@pytest.mark.parametrize(
    ("message", "error"),
    [
        (None, "was not found"),
        (SimpleNamespace(id=7, media=None), "has no media"),
    ],
)
def test_download_media_rejects_missing_or_medialess_messages(tmp_path, message, error):
    client = FakeOperations(messages=[] if message is None else [message])
    settings = make_settings(tmp_path)
    with pytest.raises(RuntimeError, match=error):
        asyncio.run(download_media(client, settings, "example", 7))


def test_send_helpers_return_safe_payloads_and_send_photo_as_photo():
    message = SimpleNamespace(id=7, date=None, sender_id=8, text="sent", media=object())
    client = FakeOperations(messages=[message])
    image_file = BytesIO(b"exact photo bytes")
    image_file.name = "photo.jpg"

    assert asyncio.run(send_message(client, "example", "hello")) == message_to_payload(message)
    assert asyncio.run(send_photo(client, "example", image_file, "caption")) == message_to_payload(
        message
    )
    assert client.send_message_call == ("entity:example", "hello")
    assert client.send_file_call == (
        "entity:example",
        {"file": image_file, "caption": "caption", "force_document": False},
    )


def test_send_document_preserves_in_memory_file_and_uses_document_mode():
    message = SimpleNamespace(
        id=8,
        date=None,
        sender_id=9,
        text="caption",
        media=object(),
    )
    client = FakeOperations(messages=[message])
    document_file = BytesIO(b"exact document bytes")
    document_file.name = "intent.md"

    payload = asyncio.run(
        send_document(client, "example", document_file, "caption")
    )

    assert payload == message_to_payload(message)
    assert client.send_file_call == (
        "entity:example",
        {
            "file": document_file,
            "caption": "caption",
            "force_document": True,
        },
    )


class FakeStatusClient:
    def __init__(self, authorized=True, me=None, connect_error=None):
        self.authorized = authorized
        self.me = me
        self.connect_error = connect_error
        self.connected = False
        self.disconnected = False

    async def connect(self):
        self.connected = True
        if self.connect_error:
            raise self.connect_error

    async def is_user_authorized(self):
        return self.authorized

    async def get_me(self):
        return self.me

    async def disconnect(self):
        self.disconnected = True


def test_collect_status_includes_bounded_identity_and_disconnects(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)
    settings.session_file.touch()
    me = SimpleNamespace(
        id=42,
        username="example",
        first_name="Example",
        last_name="User",
        phone="private",
    )
    client = FakeStatusClient(me=me)
    monkeypatch.setattr(status, "create_client", lambda current: client)

    payload = asyncio.run(collect_status(settings))

    assert client.connected is True
    assert client.disconnected is True
    assert payload["authorized"] is True
    assert payload["me"] == {
        "id": 42,
        "username": "example",
        "first_name": "Example",
        "last_name": "User",
    }


def test_collect_status_disconnects_when_connect_fails(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)
    settings.session_file.touch()
    client = FakeStatusClient(connect_error=RuntimeError("offline"))
    monkeypatch.setattr(status, "create_client", lambda current: client)

    with pytest.raises(RuntimeError, match="offline"):
        asyncio.run(collect_status(settings))

    assert client.disconnected is True


def test_collect_status_with_missing_credentials_does_not_create_client(tmp_path, monkeypatch):
    settings = make_settings(tmp_path, api_id=None, api_hash="")
    monkeypatch.setattr(
        status,
        "create_client",
        lambda current: pytest.fail("client must not be created without credentials"),
    )
    assert asyncio.run(collect_status(settings))["authorized"] is False


def test_collect_status_with_missing_session_is_non_mutating(tmp_path, monkeypatch):
    settings = make_settings(tmp_path / "runtime")
    monkeypatch.setattr(
        status,
        "create_client",
        lambda current: pytest.fail("status must not create a client without a session"),
    )

    payload = asyncio.run(collect_status(settings))

    assert payload["authorized"] is False
    assert payload["session_exists"] is False
    assert not settings.session_file.exists()
    assert not settings.session_file.parent.exists()


def test_status_main_uses_portable_env_file_and_prints_utf8_json(tmp_path, monkeypatch, capsys):
    env_file = tmp_path / "telegram.env"
    settings = make_settings(tmp_path)

    async def fake_collect_status(current):
        assert current is settings
        return {"authorized": True, "name": "Пример"}

    monkeypatch.setattr(status, "resolve_env_file", lambda: env_file)
    monkeypatch.setattr(status, "load_settings", lambda path: settings if path == env_file else None)
    monkeypatch.setattr(status, "collect_status", fake_collect_status)

    status.main()

    output = capsys.readouterr().out
    assert json.loads(output) == {"authorized": True, "name": "Пример"}
    assert "Пример" in output


class FakeAuthClient:
    def __init__(self, me, session_file=None):
        self.me = me
        self.session_file = session_file
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        self.exited = True
        if self.session_file is not None:
            self.session_file.parent.mkdir(parents=True, exist_ok=True)
            self.session_file.touch(exist_ok=True)
            self.session_file.chmod(0o644)

    async def get_me(self):
        return self.me


def test_authorize_uses_portable_env_file_and_prints_bounded_identity(tmp_path, monkeypatch, capsys):
    env_file = tmp_path / "telegram.env"
    settings = make_settings(tmp_path)
    client = FakeAuthClient(SimpleNamespace(id=42, username="example", phone="private"))
    monkeypatch.setattr(auth, "resolve_env_file", lambda: env_file)
    monkeypatch.setattr(auth, "load_settings", lambda path: settings if path == env_file else None)
    monkeypatch.setattr(auth, "create_client", lambda current: client)

    asyncio.run(auth.authorize())

    assert client.entered is True
    assert client.exited is True
    assert capsys.readouterr().out == "authorized user_id=42 username=example\n"


def test_authorize_reasserts_session_permissions_after_interactive_client_exit(
    tmp_path, monkeypatch, capsys
):
    env_file = tmp_path / "runtime" / "telegram.env"
    settings = make_settings(env_file.parent)
    client = FakeAuthClient(
        SimpleNamespace(id=42, username="example"),
        session_file=settings.session_file,
    )
    monkeypatch.setattr(auth, "resolve_env_file", lambda: env_file)
    monkeypatch.setattr(auth, "load_settings", lambda path: settings)
    monkeypatch.setattr(auth, "create_client", lambda current: client)

    asyncio.run(auth.authorize())

    assert S_IMODE(settings.session_file.parent.stat().st_mode) == 0o700
    assert S_IMODE(settings.session_file.stat().st_mode) == 0o600
    assert capsys.readouterr().out == "authorized user_id=42 username=example\n"
