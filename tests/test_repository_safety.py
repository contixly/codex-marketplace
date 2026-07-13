import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.verify_repository import (
    scan_paths,
    validate_metadata,
    verify_repository,
)


def write_metadata(
    root: Path,
    *,
    marketplace_plugin_name: str = "telegram-personal",
    marketplace_source: str = "./plugins/telegram-personal",
    manifest_name: str = "telegram-personal",
    skills_reference: str = "./skills/",
    mcp_reference: str = "./.mcp.json",
    command_reference: str = "./scripts/telegram-mcp",
    cwd_reference: str = ".",
) -> None:
    plugin_root = root / "plugins/telegram-personal"
    (root / ".agents/plugins").mkdir(parents=True)
    (plugin_root / ".codex-plugin").mkdir(parents=True)
    (plugin_root / "skills").mkdir()
    (plugin_root / "scripts").mkdir()
    (plugin_root / "scripts/telegram-mcp").write_text("#!/bin/sh\n", encoding="utf-8")

    marketplace = {
        "name": "contixly-codex-marketplace",
        "plugins": [
            {
                "name": marketplace_plugin_name,
                "source": {"source": "local", "path": marketplace_source},
            }
        ],
    }
    manifest = {
        "name": manifest_name,
        "skills": skills_reference,
        "mcpServers": mcp_reference,
    }
    mcp = {
        "mcpServers": {
            "telegram": {
                "command": command_reference,
                "cwd": cwd_reference,
            }
        }
    }
    (root / ".agents/plugins/marketplace.json").write_text(
        json.dumps(marketplace), encoding="utf-8"
    )
    (plugin_root / ".codex-plugin/plugin.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    (plugin_root / ".mcp.json").write_text(json.dumps(mcp), encoding="utf-8")


class RepositorySafetyTests(unittest.TestCase):
    def test_safe_source_tree_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "plugin/config.py"
            path.parent.mkdir()
            path.write_text(
                "TELEGRAM_API_HASH is configured at runtime\n", encoding="utf-8"
            )
            self.assertEqual(scan_paths(root, [Path("plugin/config.py")]), [])

    def test_session_env_cache_and_absolute_home_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            absolute_home = "/" + "Users/example/.codex"
            unsafe = {
                Path("personal.session"): "binary-ish",
                Path("telegram.env"): "TELEGRAM_API_HASH=real-value",
                Path("code.py"): f'HOME = "{absolute_home}"',
                Path(".venv/state.txt"): "runtime",
            }
            for relative, content in unsafe.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            errors = scan_paths(root, unsafe)
            self.assertEqual(len(errors), 4)

    def test_missing_tracked_path_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            errors = scan_paths(Path(directory), [Path("missing.py")])
            self.assertEqual(len(errors), 1)
            self.assertIn("cannot read tracked path", errors[0])

    def test_nonblank_example_credentials_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            example = root / "telegram.env.example"
            example.write_text(
                "TELEGRAM_API_ID=12345\nTELEGRAM_API_HASH=example-value\n",
                encoding="utf-8",
            )
            errors = scan_paths(root, [Path("telegram.env.example")])
            self.assertEqual(len(errors), 2)
            self.assertTrue(
                all("nonblank example credential" in error for error in errors)
            )

    def test_publication_scan_rejects_session_env_backup_and_private_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unsafe_bytes = {
                Path("account.session"): b"\xff\xfe\x00session",
                Path("account.session-journal"): b"\xff\xfe\x00journal",
                Path("runtime/telegram.env.backup"): (
                    b"TELEGRAM_API_ID=123456\nTELEGRAM_API_HASH=fake-value\n"
                ),
                Path("notes.txt"): (
                    b"private source account @real_account id=123456789\n"
                ),
            }
            for relative, content in unsafe_bytes.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)

            errors = scan_paths(root, unsafe_bytes)

            self.assertEqual(len(errors), 4)
            for relative in unsafe_bytes:
                matching = [
                    error for error in errors if error.endswith(f": {relative}")
                ]
                self.assertEqual(len(matching), 1)
            self.assertTrue(all("real_account" not in error for error in errors))
            self.assertTrue(all("123456789" not in error for error in errors))

    def test_env_like_files_reject_nonblank_telegram_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env_files = {
                Path(".env"): "TELEGRAM_API_ID=123456\n",
                Path("service.env"): "TELEGRAM_API_HASH=fake-value\n",
                Path("archive.env.copy"): "TELEGRAM_API_ID = 654321\n",
            }
            for relative, content in env_files.items():
                (root / relative).write_text(content, encoding="utf-8")

            errors = scan_paths(root, env_files)

            self.assertEqual(len(errors), 3)
            for relative in env_files:
                self.assertTrue(any(str(relative) in error for error in errors))

    def test_blank_example_and_placeholder_identity_lines_are_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            safe_files = {
                Path("telegram.env.example"): (
                    "TELEGRAM_API_ID=\nTELEGRAM_API_HASH=\n"
                ),
                Path("placeholders.txt"): (
                    "authorized username=example user_id=123456789\n"
                    "private source account @recipient id=123456789\n"
                    "telegram account @real_account id=<id>\n"
                    "documentation: private source account @real_account "
                    "id=123456789\n"
                ),
                Path("source.py"): (
                    'print(f"authorized user_id={user_id} username={username}")\n'
                ),
            }
            for relative, content in safe_files.items():
                (root / relative).write_text(content, encoding="utf-8")

            self.assertEqual(scan_paths(root, safe_files), [])

    def test_valid_metadata_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_metadata(root)
            self.assertEqual(validate_metadata(root), [])

    def test_marketplace_and_manifest_plugin_names_must_agree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_metadata(root, marketplace_plugin_name="different-name")
            errors = validate_metadata(root)
            self.assertTrue(any("plugin name" in error for error in errors))

    def test_metadata_reference_must_stay_inside_plugin_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_metadata(root, skills_reference="../../outside")
            (root / "outside").mkdir()
            errors = validate_metadata(root)
            self.assertTrue(any("outside plugin root" in error for error in errors))

    def test_metadata_reference_must_exist(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_metadata(root, command_reference="./scripts/missing")
            errors = validate_metadata(root)
            self.assertTrue(any("does not exist" in error for error in errors))

    def test_malformed_metadata_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_metadata(root)
            (root / "plugins/telegram-personal/.mcp.json").write_text(
                "{", encoding="utf-8"
            )
            errors = validate_metadata(root)
            self.assertTrue(any("invalid JSON" in error for error in errors))

    def test_repository_scan_uses_only_git_tracked_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_metadata(root)
            safe = root / "safe.txt"
            safe.write_text("safe\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(
                ["git", "-C", str(root), "add", ".agents", "plugins", "safe.txt"],
                check=True,
            )

            untracked = root / "telegram.env"
            untracked.write_text("not scanned\n", encoding="utf-8")
            self.assertEqual(verify_repository(root), [])

            subprocess.run(
                ["git", "-C", str(root), "add", "telegram.env"], check=True
            )
            errors = verify_repository(root)
            self.assertTrue(any("forbidden tracked file" in error for error in errors))

    def test_ci_covers_supported_python_versions_and_package_checks(self):
        repository_root = Path(__file__).resolve().parents[1]
        workflow = (repository_root / ".github/workflows/test.yml").read_text(
            encoding="utf-8"
        )
        for version in ("3.11", "3.12", "3.13", "3.14"):
            self.assertIn(f'"{version}"', workflow)
        self.assertIn("python scripts/verify_repository.py", workflow)
        self.assertIn("bash plugins/telegram-personal/scripts/verify-package", workflow)

    def test_package_verifier_runs_repository_tests_safety_and_json_checks(self):
        repository_root = Path(__file__).resolve().parents[1]
        script = (
            repository_root / "plugins/telegram-personal/scripts/verify-package"
        ).read_text(encoding="utf-8")
        self.assertIn('REPO_ROOT=', script)
        self.assertIn(
            'PYTHONPATH="$PLUGIN_ROOT/server" pytest "$PLUGIN_ROOT/server/tests"',
            script,
        )
        self.assertIn('scripts/verify_repository.py', script)
        self.assertEqual(script.count('-m json.tool'), 3)


if __name__ == "__main__":
    unittest.main()
