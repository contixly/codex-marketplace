from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


DEFAULT_DIALOG_LIMIT = 50
DEFAULT_MESSAGE_LIMIT = 20
DEFAULT_MESSAGE_LIMIT_MAX = 100
DEFAULT_UPLOAD_MAX_BYTES = 20 * 1024 * 1024


def resolve_codex_home(
    *, environ: Mapping[str, str] | None = None, home: str | Path | None = None
) -> Path:
    values = os.environ if environ is None else environ
    configured = values.get("CODEX_HOME")
    if configured:
        return Path(configured).expanduser()
    base_home = Path.home() if home is None else Path(home)
    return base_home / ".codex"


def resolve_data_dir(
    *, environ: Mapping[str, str] | None = None, home: str | Path | None = None
) -> Path:
    values = os.environ if environ is None else environ
    configured = values.get("TELEGRAM_PLUGIN_DATA_DIR")
    if configured:
        return Path(configured).expanduser()
    return resolve_codex_home(environ=values, home=home) / "telegram-personal"


def resolve_env_file(
    *, environ: Mapping[str, str] | None = None, home: str | Path | None = None
) -> Path:
    values = os.environ if environ is None else environ
    configured = values.get("TELEGRAM_ENV_FILE")
    if configured:
        return Path(configured).expanduser()
    return resolve_data_dir(environ=values, home=home) / "telegram.env"


@dataclass(frozen=True)
class TelegramSettings:
    env_file: Path
    api_id: int | None
    api_hash: str = field(repr=False)
    session_name: str
    session_file: Path
    downloads_dir: Path
    dialog_limit_default: int
    message_limit_default: int
    message_limit_max: int
    upload_max_bytes: int = DEFAULT_UPLOAD_MAX_BYTES

    @property
    def api_hash_configured(self) -> bool:
        return bool(self.api_hash)


def load_settings(env_file: str | Path | None = None) -> TelegramSettings:
    env_path = Path(env_file) if env_file is not None else resolve_env_file()
    env_path = env_path.expanduser()
    data_dir = env_path.parent
    values = _read_dotenv(env_path)
    session_name = values.get("TELEGRAM_SESSION_NAME") or str(data_dir / "personal")
    downloads_dir = Path(values.get("TELEGRAM_DOWNLOADS_DIR") or data_dir / "downloads").expanduser()
    return TelegramSettings(
        env_file=env_path,
        api_id=_optional_int(values.get("TELEGRAM_API_ID")),
        api_hash=values.get("TELEGRAM_API_HASH") or "",
        session_name=session_name,
        session_file=Path(session_name + ".session").expanduser(),
        downloads_dir=downloads_dir,
        dialog_limit_default=_int_or_default(values.get("TELEGRAM_DIALOG_LIMIT_DEFAULT"), DEFAULT_DIALOG_LIMIT),
        message_limit_default=_int_or_default(values.get("TELEGRAM_MESSAGE_LIMIT_DEFAULT"), DEFAULT_MESSAGE_LIMIT),
        message_limit_max=_int_or_default(values.get("TELEGRAM_MESSAGE_LIMIT_MAX"), DEFAULT_MESSAGE_LIMIT_MAX),
        upload_max_bytes=_positive_int_or_default(values.get("TELEGRAM_UPLOAD_MAX_BYTES"), DEFAULT_UPLOAD_MAX_BYTES),
    )


def ensure_runtime_directories(settings: TelegramSettings) -> None:
    """Create and restrict runtime directories before an operation stores data."""
    _ensure_private_directory(settings.env_file.parent)
    _ensure_private_directory(settings.downloads_dir)


def _ensure_private_directory(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)


def _read_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        result[key] = value
    return result


def _optional_int(value: str | None) -> int | None:
    return int(value) if value else None


def _int_or_default(value: str | None, default: int) -> int:
    return int(value) if value else default


def _positive_int_or_default(value: str | None, default: int) -> int:
    parsed = int(value) if value else default
    return parsed if parsed > 0 else default
