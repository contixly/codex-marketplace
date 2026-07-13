from __future__ import annotations

from pathlib import Path
from typing import Any

from telethon import TelegramClient

from telegram_mcp.config import TelegramSettings


DIALOG_RESOLVE_LIMIT = 1000
MESSAGE_FIELDS = {"id", "date", "sender_id", "text", "has_media"}
DIALOG_FIELDS = {"name", "id", "username", "entity_type", "unread_count"}


def create_client(settings: TelegramSettings) -> TelegramClient:
    if settings.api_id is None or not settings.api_hash:
        raise RuntimeError("Telegram API credentials are missing. Run the plugin setup first.")
    secure_session_file(settings)
    return TelegramClient(settings.session_name, settings.api_id, settings.api_hash)


def secure_session_file(settings: TelegramSettings) -> None:
    session_file = settings.session_file
    session_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    session_file.parent.chmod(0o700)
    session_file.touch(mode=0o600, exist_ok=True)
    session_file.chmod(0o600)


def entity_label(entity: Any) -> str:
    parts: list[str] = []

    display_name = _first_present(
        getattr(entity, "title", None),
        getattr(entity, "name", None),
        _joined_name(
            getattr(entity, "first_name", None),
            getattr(entity, "last_name", None),
        ),
    )
    if display_name:
        parts.append(str(display_name))

    username = getattr(entity, "username", None)
    if username:
        parts.append(f"@{username}")

    entity_id = getattr(entity, "id", None)
    if entity_id is not None:
        parts.append(f"id={entity_id}")

    return " ".join(parts) if parts else "unknown"


async def resolve_entity(client: Any, recipient: Any) -> Any:
    try:
        return await client.get_entity(recipient)
    except Exception as original_error:
        if isinstance(recipient, str) and recipient.lstrip("-").isdigit():
            try:
                return await client.get_entity(int(recipient))
            except Exception:
                pass
        if isinstance(recipient, str):
            normalized = recipient.strip().lstrip("@").casefold()
            async for dialog in client.iter_dialogs(limit=DIALOG_RESOLVE_LIMIT):
                entity = getattr(dialog, "entity", None)
                candidates = (
                    getattr(dialog, "name", None),
                    getattr(dialog, "id", None),
                    getattr(entity, "id", None),
                    getattr(entity, "username", None),
                    getattr(entity, "title", None),
                )
                if any(
                    str(value).strip().lstrip("@").casefold() == normalized
                    for value in candidates
                    if value is not None
                ):
                    return entity
        raise original_error


def message_to_payload(message: Any) -> dict[str, Any]:
    return {
        "id": getattr(message, "id", None),
        "date": _date_to_payload(getattr(message, "date", None)),
        "sender_id": getattr(message, "sender_id", None),
        "text": _message_text(message),
        "has_media": bool(getattr(message, "media", None)),
    }


def dialog_to_payload(dialog: Any) -> dict[str, Any]:
    entity = getattr(dialog, "entity", None)
    return {
        "name": getattr(dialog, "name", None),
        "id": _first_present(
            getattr(dialog, "id", None),
            getattr(entity, "id", None),
        ),
        "username": getattr(entity, "username", None),
        "entity_type": type(entity).__name__ if entity is not None else None,
        "unread_count": getattr(dialog, "unread_count", 0),
    }


async def list_dialogs(client: Any, query: str | None, limit: int) -> list[dict[str, Any]]:
    query_text = (query or "").casefold()
    results: list[dict[str, Any]] = []
    async for dialog in client.iter_dialogs(limit=limit):
        payload = dialog_to_payload(dialog)
        if _matches_dialog_query(payload, query_text):
            results.append(payload)
    return results


async def read_messages(client: Any, recipient: str, limit: int) -> list[dict[str, Any]]:
    entity = await resolve_entity(client, recipient)
    messages = await client.get_messages(entity, limit=limit)
    return [message_to_payload(message) for message in messages]


async def download_media(
    client: Any,
    settings: TelegramSettings,
    recipient: str,
    message_id: int,
) -> str:
    entity = await resolve_entity(client, recipient)
    message = await client.get_messages(entity, ids=message_id)
    if message is None:
        raise RuntimeError(f"Telegram message {message_id} was not found.")
    if not getattr(message, "media", None):
        raise RuntimeError(f"Telegram message {message_id} has no media to download.")

    settings.downloads_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = await client.download_media(message, file=str(settings.downloads_dir))
    if not path:
        raise RuntimeError(f"Telegram media download failed for message {message_id}.")
    return str(Path(path).expanduser().resolve())


async def send_message(client: Any, recipient: Any, text: str) -> dict[str, Any]:
    entity = await resolve_entity(client, recipient)
    sent_message = await client.send_message(entity, text)
    return message_to_payload(sent_message)


async def send_photo(
    client: Any,
    recipient: Any,
    image_path: str,
    caption: str | None,
) -> dict[str, Any]:
    entity = await resolve_entity(client, recipient)
    sent_message = await client.send_file(
        entity,
        file=image_path,
        caption=caption,
        force_document=False,
    )
    return message_to_payload(sent_message)


def _matches_dialog_query(payload: dict[str, Any], query_text: str) -> bool:
    if not query_text:
        return True
    values = [
        payload.get("name"),
        payload.get("username"),
        payload.get("id"),
    ]
    return any(query_text in str(value).casefold() for value in values if value is not None)


def _message_text(message: Any) -> str | None:
    text = getattr(message, "text", None)
    if text is not None:
        return text
    return getattr(message, "message", None)


def _date_to_payload(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _joined_name(*values: Any) -> str | None:
    parts = [str(value) for value in values if value]
    return " ".join(parts) if parts else None
