import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

from telegram_mcp import setup_cli
from telegram_mcp.setup_cli import write_credentials


PLUGIN_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"


def test_write_credentials_is_private_and_portable(tmp_path):
    env_file = tmp_path / "data/telegram.env"
    write_credentials(env_file, api_id="12345", api_hash="test-hash")
    text = env_file.read_text(encoding="utf-8")
    assert "TELEGRAM_API_ID=12345" in text
    assert "TELEGRAM_API_HASH=test-hash" in text
    assert f"TELEGRAM_SESSION_NAME={tmp_path / 'data/personal'}" in text
    assert f"TELEGRAM_DOWNLOADS_DIR={tmp_path / 'data/downloads'}" in text
    assert os.stat(env_file).st_mode & 0o777 == 0o600


def test_existing_credentials_require_explicit_replace(tmp_path):
    env_file = tmp_path / "telegram.env"
    write_credentials(env_file, api_id="1", api_hash="first")
    with pytest.raises(FileExistsError, match="reconfigure"):
        write_credentials(env_file, api_id="2", api_hash="second")
    assert "first" in env_file.read_text(encoding="utf-8")


def test_atomic_writer_never_leaves_plaintext_temp_file(tmp_path):
    env_file = tmp_path / "telegram.env"
    write_credentials(env_file, api_id="1", api_hash="hash")
    assert sorted(path.name for path in tmp_path.iterdir()) == ["telegram.env"]


@pytest.mark.parametrize("api_id", ["", "0", "-1", "12x", " 12 "])
def test_write_credentials_rejects_invalid_api_id(tmp_path, api_id):
    with pytest.raises(ValueError, match="API ID"):
        write_credentials(tmp_path / "telegram.env", api_id=api_id, api_hash="hash")


@pytest.mark.parametrize("api_hash", ["", "   ", "line1\nline2", "line1\rline2"])
def test_write_credentials_rejects_invalid_api_hash(tmp_path, api_hash):
    with pytest.raises(ValueError, match="API hash"):
        write_credentials(tmp_path / "telegram.env", api_id="1", api_hash=api_hash)


def test_write_credentials_sets_exact_defaults_and_restricts_existing_parent(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(mode=0o755)
    data_dir.chmod(0o755)
    env_file = data_dir / "telegram.env"

    write_credentials(env_file, api_id="12345", api_hash="test-hash")

    assert env_file.read_text(encoding="utf-8").splitlines() == [
        "TELEGRAM_API_ID=12345",
        "TELEGRAM_API_HASH=test-hash",
        f"TELEGRAM_SESSION_NAME={data_dir / 'personal'}",
        f"TELEGRAM_DOWNLOADS_DIR={data_dir / 'downloads'}",
        "TELEGRAM_DIALOG_LIMIT_DEFAULT=50",
        "TELEGRAM_MESSAGE_LIMIT_DEFAULT=20",
        "TELEGRAM_MESSAGE_LIMIT_MAX=100",
        "TELEGRAM_UPLOAD_MAX_BYTES=20971520",
    ]
    assert stat.S_IMODE(data_dir.stat().st_mode) == 0o700


def test_explicit_replace_is_atomic_and_private(tmp_path):
    env_file = tmp_path / "telegram.env"
    write_credentials(env_file, api_id="1", api_hash="first")

    write_credentials(env_file, api_id="2", api_hash="second", replace=True)

    assert "TELEGRAM_API_HASH=second" in env_file.read_text(encoding="utf-8")
    assert stat.S_IMODE(env_file.stat().st_mode) == 0o600
    assert sorted(path.name for path in tmp_path.iterdir()) == ["telegram.env"]


def test_failed_replace_preserves_credentials_and_removes_temp_file(tmp_path, monkeypatch):
    env_file = tmp_path / "telegram.env"
    write_credentials(env_file, api_id="1", api_hash="first")

    def fail_replace(source, destination):
        raise OSError("replace failed")

    monkeypatch.setattr(setup_cli.os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        write_credentials(env_file, api_id="2", api_hash="second", replace=True)

    assert "TELEGRAM_API_HASH=first" in env_file.read_text(encoding="utf-8")
    assert sorted(path.name for path in tmp_path.iterdir()) == ["telegram.env"]


def test_main_configures_authorizes_secures_session_and_prints_safe_status(
    tmp_path, monkeypatch, capsys
):
    env_file = tmp_path / "data/telegram.env"
    session_file = env_file.parent / "personal.session"
    prompts = []

    monkeypatch.setattr(setup_cli, "resolve_env_file", lambda: env_file)
    monkeypatch.setattr("builtins.input", lambda prompt: prompts.append(prompt) or "12345")
    monkeypatch.setattr(
        setup_cli.getpass,
        "getpass",
        lambda prompt: prompts.append(prompt) or "private-hash",
    )

    async def fake_authorize():
        assert env_file.exists()
        session_file.write_text("session", encoding="utf-8")
        session_file.chmod(0o644)

    async def fake_collect_status(settings):
        assert settings.env_file == env_file
        assert stat.S_IMODE(session_file.stat().st_mode) == 0o600
        return {
            "authorized": True,
            "api_id_configured": True,
            "api_hash_configured": True,
        }

    monkeypatch.setattr(setup_cli, "authorize", fake_authorize)
    monkeypatch.setattr(setup_cli, "collect_status", fake_collect_status)

    setup_cli.main([])

    output = capsys.readouterr().out
    assert json.loads(output) == {
        "authorized": True,
        "api_id_configured": True,
        "api_hash_configured": True,
    }
    assert "private-hash" not in output
    assert prompts == ["Telegram API ID: ", "Telegram API Hash: "]


def test_main_refuses_existing_credentials_before_prompting(tmp_path, monkeypatch):
    env_file = tmp_path / "telegram.env"
    env_file.write_text("existing", encoding="utf-8")
    monkeypatch.setattr(setup_cli, "resolve_env_file", lambda: env_file)
    monkeypatch.setattr(
        "builtins.input",
        lambda prompt: pytest.fail("must refuse before prompting for credentials"),
    )

    with pytest.raises(FileExistsError, match="reconfigure"):
        setup_cli.main([])


def test_main_exits_nonzero_when_status_is_not_authorized(tmp_path, monkeypatch, capsys):
    env_file = tmp_path / "telegram.env"
    monkeypatch.setattr(setup_cli, "resolve_env_file", lambda: env_file)
    monkeypatch.setattr("builtins.input", lambda prompt: "1")
    monkeypatch.setattr(setup_cli.getpass, "getpass", lambda prompt: "hash")

    async def fake_authorize():
        return None

    async def fake_collect_status(settings):
        return {"authorized": False}

    monkeypatch.setattr(setup_cli, "authorize", fake_authorize)
    monkeypatch.setattr(setup_cli, "collect_status", fake_collect_status)

    with pytest.raises(SystemExit) as exc_info:
        setup_cli.main([])

    assert exc_info.value.code == 1
    assert json.loads(capsys.readouterr().out) == {"authorized": False}


def test_main_reconfigure_replaces_existing_credentials(tmp_path, monkeypatch):
    env_file = tmp_path / "telegram.env"
    write_credentials(env_file, api_id="1", api_hash="first")
    monkeypatch.setattr(setup_cli, "resolve_env_file", lambda: env_file)
    monkeypatch.setattr("builtins.input", lambda prompt: "2")
    monkeypatch.setattr(setup_cli.getpass, "getpass", lambda prompt: "second")

    async def fake_authorize():
        return None

    async def fake_collect_status(settings):
        return {"authorized": True}

    monkeypatch.setattr(setup_cli, "authorize", fake_authorize)
    monkeypatch.setattr(setup_cli, "collect_status", fake_collect_status)

    setup_cli.main(["--reconfigure"])

    assert "TELEGRAM_API_HASH=second" in env_file.read_text(encoding="utf-8")


def test_main_rejects_unknown_arguments():
    with pytest.raises(SystemExit) as exc_info:
        setup_cli.main(["--unknown"])
    assert exc_info.value.code == 2


def _write_executable(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def test_common_reports_unconfigured_runtime_with_config_exit_code(tmp_path):
    common = SCRIPTS_DIR / "common"
    assert common.exists()
    result = subprocess.run(
        ["bash", "-c", 'source "$1"; require_runtime', "_", str(common)],
        env={**os.environ, "CODEX_HOME": str(tmp_path / "codex-home")},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 78
    assert f"Run: {PLUGIN_ROOT}/scripts/setup" in result.stderr


@pytest.mark.parametrize(
    ("launcher", "module"),
    [
        ("telegram-mcp", "telegram_mcp.server"),
        ("telegram-auth", "telegram_mcp.auth"),
        ("telegram-status", "telegram_mcp.status"),
    ],
)
def test_launchers_use_private_runtime_python_and_portable_paths(
    tmp_path, launcher, module
):
    script = SCRIPTS_DIR / launcher
    assert script.exists()
    data_root = tmp_path / "private-data"
    fake_python = data_root / ".venv/bin/python"
    _write_executable(
        fake_python,
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$*\" \"$TELEGRAM_PLUGIN_DATA_DIR\" \"$TELEGRAM_ENV_FILE\" \"$PYTHONPATH\"\n",
    )

    result = subprocess.run(
        [str(script)],
        env={**os.environ, "TELEGRAM_PLUGIN_DATA_DIR": str(data_root)},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        f"-m {module}",
        str(data_root),
        str(data_root / "telegram.env"),
        str(PLUGIN_ROOT / "server"),
    ]


def test_setup_rejects_non_macos_before_running_python(tmp_path):
    script = SCRIPTS_DIR / "setup"
    assert script.exists()
    fake_bin = tmp_path / "bin"
    _write_executable(fake_bin / "uname", "#!/usr/bin/env bash\nprintf 'Linux\\n'\n")
    _write_executable(
        fake_bin / "python3",
        "#!/usr/bin/env bash\nprintf 'python must not run\\n' >&2\nexit 99\n",
    )

    result = subprocess.run(
        [str(script)],
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "TELEGRAM_PLUGIN_DATA_DIR": str(tmp_path / "data"),
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "macOS" in result.stderr
    assert "python must not run" not in result.stderr


@pytest.mark.parametrize("version", ["3 10", "3 15", "4 11"])
def test_setup_rejects_unsupported_python_versions(tmp_path, version):
    script = SCRIPTS_DIR / "setup"
    assert script.exists()
    fake_bin = tmp_path / "bin"
    _write_executable(fake_bin / "uname", "#!/usr/bin/env bash\nprintf 'Darwin\\n'\n")
    _write_executable(
        fake_bin / "python3",
        f"#!/usr/bin/env bash\nprintf '{version}\\n'\n",
    )

    result = subprocess.run(
        [str(script)],
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "TELEGRAM_PLUGIN_DATA_DIR": str(tmp_path / "data"),
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Python 3.11-3.14" in result.stderr


def test_setup_bootstraps_private_venv_and_forwards_arguments(tmp_path):
    script = SCRIPTS_DIR / "setup"
    assert script.exists()
    fake_bin = tmp_path / "bin"
    data_root = tmp_path / "data"
    calls_file = tmp_path / "calls"
    _write_executable(fake_bin / "uname", "#!/usr/bin/env bash\nprintf 'Darwin\\n'\n")
    _write_executable(
        fake_bin / "python3",
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == "-c" ]]; then
  printf '3 14\n'
  exit 0
fi
if [[ "$1" == "-m" && "$2" == "venv" ]]; then
  mkdir -p "$3/bin"
  cat > "$3/bin/python" <<'PYTHON'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$SETUP_CALLS"
PYTHON
  chmod 755 "$3/bin/python"
  exit 0
fi
exit 97
""",
    )

    result = subprocess.run(
        [str(script), "--reconfigure"],
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "TELEGRAM_PLUGIN_DATA_DIR": str(data_root),
            "SETUP_CALLS": str(calls_file),
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert stat.S_IMODE(data_root.stat().st_mode) == 0o700
    assert calls_file.read_text(encoding="utf-8").splitlines() == [
        f"-m pip install -r {PLUGIN_ROOT / 'requirements.txt'}",
        "-m telegram_mcp.setup_cli --reconfigure",
    ]


def test_verify_package_checks_shell_and_runs_pytest_with_server_pythonpath(tmp_path):
    script = SCRIPTS_DIR / "verify-package"
    assert script.exists()
    fake_bin = tmp_path / "bin"
    calls_file = tmp_path / "pytest-call"
    _write_executable(
        fake_bin / "pytest",
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$PYTHONPATH\" \"$*\" > \"$VERIFY_CALLS\"\n",
    )

    result = subprocess.run(
        [str(script)],
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "VERIFY_CALLS": str(calls_file),
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert calls_file.read_text(encoding="utf-8").splitlines() == [
        str(PLUGIN_ROOT / "server"),
        str(PLUGIN_ROOT / "server/tests"),
    ]
