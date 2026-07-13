from pathlib import Path
from stat import S_IMODE

from telegram_mcp.config import (
    TelegramSettings,
    ensure_runtime_directories,
    load_settings,
    resolve_codex_home,
    resolve_data_dir,
    resolve_env_file,
)


def test_runtime_paths_honor_codex_home(tmp_path):
    environ = {"CODEX_HOME": str(tmp_path / "codex-home")}
    assert resolve_codex_home(environ=environ) == tmp_path / "codex-home"
    assert resolve_data_dir(environ=environ) == tmp_path / "codex-home/telegram-personal"
    assert resolve_env_file(environ=environ) == tmp_path / "codex-home/telegram-personal/telegram.env"


def test_runtime_paths_fall_back_to_home(tmp_path):
    assert resolve_codex_home(environ={}, home=tmp_path) == tmp_path / ".codex"


def test_load_settings_uses_portable_defaults(tmp_path):
    env_file = tmp_path / "runtime/telegram.env"
    env_file.parent.mkdir()
    env_file.write_text("TELEGRAM_API_ID=\nTELEGRAM_API_HASH=\n", encoding="utf-8")
    settings = load_settings(env_file)
    assert settings.api_id is None
    assert settings.api_hash_configured is False
    assert settings.session_name == str(env_file.parent / "personal")
    assert settings.downloads_dir == env_file.parent / "downloads"
    assert settings.message_limit_max == 100
    assert settings.download_max_bytes == 20 * 1024 * 1024


def test_load_settings_reads_positive_download_limit(tmp_path):
    env_file = tmp_path / "runtime/telegram.env"
    env_file.parent.mkdir()
    env_file.write_text(
        "TELEGRAM_DOWNLOAD_MAX_BYTES=4096\n",
        encoding="utf-8",
    )

    assert load_settings(env_file).download_max_bytes == 4096


def test_load_settings_is_non_mutating_when_runtime_is_absent(tmp_path):
    env_file = tmp_path / "runtime/telegram.env"

    settings = load_settings(env_file)

    assert settings.env_file == env_file
    assert not env_file.parent.exists()
    assert not settings.downloads_dir.exists()


def test_load_settings_does_not_change_existing_runtime_permissions(tmp_path):
    data_dir = tmp_path / "runtime"
    downloads_dir = data_dir / "downloads"
    downloads_dir.mkdir(parents=True)
    data_dir.chmod(0o755)
    downloads_dir.chmod(0o755)
    env_file = data_dir / "telegram.env"

    settings = load_settings(env_file)

    assert settings.downloads_dir == downloads_dir
    assert S_IMODE(data_dir.stat().st_mode) == 0o755
    assert S_IMODE(downloads_dir.stat().st_mode) == 0o755


def test_ensure_runtime_directories_creates_private_runtime_directories(tmp_path):
    env_file = tmp_path / "runtime/telegram.env"
    settings = load_settings(env_file)

    ensure_runtime_directories(settings)

    assert S_IMODE(env_file.parent.stat().st_mode) == 0o700
    assert S_IMODE(settings.downloads_dir.stat().st_mode) == 0o700


def test_ensure_runtime_directories_restricts_existing_directories(tmp_path):
    data_dir = tmp_path / "runtime"
    downloads_dir = data_dir / "downloads"
    downloads_dir.mkdir(parents=True)
    data_dir.chmod(0o755)
    downloads_dir.chmod(0o755)
    settings = load_settings(data_dir / "telegram.env")

    ensure_runtime_directories(settings)

    assert S_IMODE(data_dir.stat().st_mode) == 0o700
    assert S_IMODE(settings.downloads_dir.stat().st_mode) == 0o700


def test_settings_repr_redacts_hash(tmp_path):
    settings = TelegramSettings(
        env_file=tmp_path / "telegram.env",
        api_id=12345,
        api_hash="private-value",
        session_name=str(tmp_path / "personal"),
        session_file=tmp_path / "personal.session",
        downloads_dir=tmp_path / "downloads",
        dialog_limit_default=50,
        message_limit_default=20,
        message_limit_max=100,
        upload_max_bytes=20 * 1024 * 1024,
    )
    assert "private-value" not in repr(settings)
