from __future__ import annotations

import asyncio
import json
from typing import Any

from telegram_mcp.client import create_client
from telegram_mcp.config import TelegramSettings, load_settings, resolve_env_file


def build_status_payload(
    settings: TelegramSettings,
    authorized: bool,
    me: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "env_file": str(settings.env_file),
        "api_id_configured": settings.api_id is not None,
        "api_hash_configured": settings.api_hash_configured,
        "session_exists": settings.session_file.exists(),
        "authorized": authorized,
        "me": me,
        "downloads_dir": str(settings.downloads_dir),
        "limits": {
            "dialog_limit_default": settings.dialog_limit_default,
            "message_limit_default": settings.message_limit_default,
            "message_limit_max": settings.message_limit_max,
        },
    }


async def collect_status(settings: TelegramSettings) -> dict[str, Any]:
    if settings.api_id is None or not settings.api_hash:
        return build_status_payload(settings, authorized=False)

    client = create_client(settings)
    try:
        await client.connect()
        authorized = await client.is_user_authorized()
        me = _me_to_payload(await client.get_me()) if authorized else None
        return build_status_payload(settings, authorized=authorized, me=me)
    finally:
        await client.disconnect()


def main() -> None:
    settings = load_settings(resolve_env_file())
    payload = asyncio.run(collect_status(settings))
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _me_to_payload(me: Any) -> dict[str, Any]:
    return {
        "id": getattr(me, "id", None),
        "username": getattr(me, "username", None),
        "first_name": getattr(me, "first_name", None),
        "last_name": getattr(me, "last_name", None),
    }


if __name__ == "__main__":
    main()
