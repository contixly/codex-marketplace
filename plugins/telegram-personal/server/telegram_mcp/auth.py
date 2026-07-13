from __future__ import annotations

import asyncio
from typing import Any

from telegram_mcp.client import create_client
from telegram_mcp.config import load_settings, resolve_env_file


async def authorize() -> None:
    settings = load_settings(resolve_env_file())
    client = create_client(settings)

    async with client:
        me = await client.get_me()

    print(f"authorized user_id={_user_id(me)} username={_username(me)}")


def main() -> None:
    asyncio.run(authorize())


def _user_id(me: Any) -> Any:
    return getattr(me, "id", None)


def _username(me: Any) -> Any:
    return getattr(me, "username", None)


if __name__ == "__main__":
    main()
