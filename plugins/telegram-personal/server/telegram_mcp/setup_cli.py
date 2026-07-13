from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import tempfile
from pathlib import Path
from typing import Sequence

from telegram_mcp.auth import authorize
from telegram_mcp.config import (
    ensure_runtime_directories,
    load_settings,
    resolve_env_file,
)
from telegram_mcp.status import collect_status


_DEFAULT_LINES = (
    "TELEGRAM_DIALOG_LIMIT_DEFAULT=50",
    "TELEGRAM_MESSAGE_LIMIT_DEFAULT=20",
    "TELEGRAM_MESSAGE_LIMIT_MAX=100",
    "TELEGRAM_UPLOAD_MAX_BYTES=20971520",
    "TELEGRAM_DOWNLOAD_MAX_BYTES=20971520",
)


def write_credentials(
    env_file: str | Path,
    api_id: str | int,
    api_hash: str,
    *,
    replace: bool = False,
) -> None:
    """Atomically write private Telegram credentials and portable runtime paths."""
    env_path = Path(env_file).expanduser()
    api_id_text = str(api_id)
    if not api_id_text.isdigit() or int(api_id_text) <= 0:
        raise ValueError("Telegram API ID must be an all-digit positive integer")
    if (
        not isinstance(api_hash, str)
        or not api_hash.strip()
        or any(character in api_hash for character in ("\n", "\r", "\0"))
    ):
        raise ValueError("Telegram API hash must be nonblank and single-line")

    env_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    env_path.parent.chmod(0o700)
    if env_path.exists() and not replace:
        raise FileExistsError(
            f"Telegram credentials already exist at {env_path}; "
            "rerun setup with --reconfigure to replace them"
        )

    lines = (
        f"TELEGRAM_API_ID={api_id_text}",
        f"TELEGRAM_API_HASH={api_hash}",
        f"TELEGRAM_SESSION_NAME={env_path.parent / 'personal'}",
        f"TELEGRAM_DOWNLOADS_DIR={env_path.parent / 'downloads'}",
        *_DEFAULT_LINES,
    )
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=env_path.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            os.chmod(temporary_path, 0o600)
            temporary_file.write("\n".join(lines) + "\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        if env_path.exists() and not replace:
            raise FileExistsError(
                f"Telegram credentials already exist at {env_path}; "
                "rerun setup with --reconfigure to replace them"
            )
        os.replace(temporary_path, env_path)
        env_path.chmod(0o600)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Configure Telegram Personal")
    parser.add_argument(
        "--reconfigure",
        action="store_true",
        help="replace existing Telegram API credentials",
    )
    arguments = parser.parse_args(argv)

    env_file = resolve_env_file()
    if env_file.exists() and not arguments.reconfigure:
        raise FileExistsError(
            f"Telegram credentials already exist at {env_file}; "
            "rerun setup with --reconfigure to replace them"
        )

    api_id = input("Telegram API ID: ")
    api_hash = getpass.getpass("Telegram API Hash: ")
    write_credentials(
        env_file,
        api_id=api_id,
        api_hash=api_hash,
        replace=arguments.reconfigure,
    )

    settings = load_settings(env_file)
    ensure_runtime_directories(settings)
    asyncio.run(authorize())
    if settings.session_file.exists():
        settings.session_file.chmod(0o600)
    payload = asyncio.run(collect_status(settings))
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    if payload.get("authorized") is not True:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
