#!/usr/bin/env python3
"""Verify that tracked marketplace content is safe to publish."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Iterable
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any


FORBIDDEN_NAMES = {"telegram.env", "personal.session", "personal.session-journal"}
FORBIDDEN_PARTS = {".venv", "__pycache__", ".pytest_cache", "downloads"}
FORBIDDEN_TEXT = ("/" + "Users/",)
EXAMPLE_ENV_NAMES = {"telegram.env.example"}
EXAMPLE_CREDENTIAL_KEYS = {"TELEGRAM_API_ID", "TELEGRAM_API_HASH"}
IDENTITY_PLACEHOLDERS = {
    "account",
    "example",
    "none",
    "null",
    "recipient",
    "test",
    "user",
}

_IDENTITY_PREFIX = re.compile(
    r"^\s*(?:authorized|private source account|telegram account)\b",
    re.IGNORECASE,
)
_TELEGRAM_HANDLE = re.compile(r"(?<![A-Za-z0-9_])@([A-Za-z][A-Za-z0-9_]{4,31})\b")
_LABELED_TELEGRAM_HANDLE = re.compile(
    r"\b(?:username|handle)\s*[:=]\s*@?([A-Za-z][A-Za-z0-9_]{4,31})\b",
    re.IGNORECASE,
)
_TELEGRAM_ACCOUNT_ID = re.compile(
    r"\b(?:user_id|account_id|id)\s*[:=]\s*\d{6,15}\b",
    re.IGNORECASE,
)

MARKETPLACE_PATH = Path(".agents/plugins/marketplace.json")
PLUGIN_ROOT_PATH = Path("plugins/telegram-personal")
PLUGIN_MANIFEST_PATH = PLUGIN_ROOT_PATH / ".codex-plugin/plugin.json"
MCP_CONFIG_PATH = PLUGIN_ROOT_PATH / ".mcp.json"


def scan_paths(root: Path, relative_paths: Iterable[Path]) -> list[str]:
    """Return publication-safety errors for the supplied repository paths."""

    errors: list[str] = []
    resolved_root = root.resolve()
    for relative in relative_paths:
        if _is_forbidden_runtime_filename(relative.name):
            errors.append(f"forbidden tracked file: {relative}")
            continue
        if any(part in FORBIDDEN_PARTS for part in relative.parts):
            errors.append(f"forbidden tracked path: {relative}")
            continue

        if relative.is_absolute():
            errors.append(f"tracked path is not repository-relative: {relative}")
            continue

        path = root / relative
        try:
            resolved_path = path.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            errors.append(f"cannot read tracked path {relative}: {error}")
            continue

        if not _is_within(resolved_path, resolved_root):
            errors.append(f"tracked path escapes repository root: {relative}")
            continue
        if not resolved_path.is_file():
            errors.append(f"tracked path is not a file: {relative}")
            continue

        try:
            data = path.read_bytes()
        except OSError as error:
            errors.append(f"cannot read tracked path {relative}: {error}")
            continue

        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue

        for forbidden in FORBIDDEN_TEXT:
            if forbidden in text:
                errors.append(f"forbidden source-machine path in: {relative}")
                break

        if _is_env_like_filename(relative.name):
            for line in text.splitlines():
                key, separator, value = line.partition("=")
                if separator and key.strip() in EXAMPLE_CREDENTIAL_KEYS and value.strip():
                    label = (
                        "nonblank example credential"
                        if relative.name in EXAMPLE_ENV_NAMES
                        else "nonblank Telegram credential"
                    )
                    errors.append(
                        f"{label} {key.strip()} in: {relative}"
                    )

        if _contains_private_telegram_identity(text):
            errors.append(f"possible private Telegram account identity in: {relative}")

    return errors


def _is_forbidden_runtime_filename(name: str) -> bool:
    if name in FORBIDDEN_NAMES:
        return True
    if fnmatchcase(name, "*.session") or fnmatchcase(name, "*.session-*"):
        return True
    return name.startswith("telegram.env.") and name not in EXAMPLE_ENV_NAMES


def _is_env_like_filename(name: str) -> bool:
    return name == ".env" or fnmatchcase(name, "*.env") or ".env." in name


def _contains_private_telegram_identity(text: str) -> bool:
    for line in text.splitlines():
        if not _IDENTITY_PREFIX.search(line) or not _TELEGRAM_ACCOUNT_ID.search(line):
            continue
        handles = [
            *(_TELEGRAM_HANDLE.findall(line)),
            *(_LABELED_TELEGRAM_HANDLE.findall(line)),
        ]
        if any(handle.casefold() not in IDENTITY_PLACEHOLDERS for handle in handles):
            return True
    return False


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _read_json(
    root: Path, relative: Path, errors: list[str]
) -> dict[str, Any] | None:
    path = root / relative
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        errors.append(f"cannot read metadata {relative}: {error}")
        return None
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        errors.append(f"invalid JSON in {relative}: {error}")
        return None

    if not isinstance(value, dict):
        errors.append(f"metadata root must be an object: {relative}")
        return None
    return value


def _resolve_reference(
    *,
    base: Path,
    allowed_root: Path,
    reference: Any,
    label: str,
    errors: list[str],
    expected_kind: str,
) -> Path | None:
    if not isinstance(reference, str) or not reference.strip():
        errors.append(f"{label} must be a nonempty relative path")
        return None

    relative = Path(reference)
    if relative.is_absolute():
        errors.append(f"{label} must be relative to the plugin root")
        return None

    allowed = allowed_root.resolve()
    candidate = (base / relative).resolve()
    if not _is_within(candidate, allowed):
        errors.append(f"{label} resolves outside plugin root: {reference}")
        return None
    if not candidate.exists():
        errors.append(f"{label} does not exist: {reference}")
        return None
    if expected_kind == "file" and not candidate.is_file():
        errors.append(f"{label} is not a file: {reference}")
        return None
    if expected_kind == "directory" and not candidate.is_dir():
        errors.append(f"{label} is not a directory: {reference}")
        return None
    return candidate


def validate_metadata(root: Path) -> list[str]:
    """Validate marketplace, plugin, and MCP metadata references."""

    errors: list[str] = []
    marketplace = _read_json(root, MARKETPLACE_PATH, errors)
    manifest = _read_json(root, PLUGIN_MANIFEST_PATH, errors)
    mcp_config = _read_json(root, MCP_CONFIG_PATH, errors)
    if marketplace is None or manifest is None or mcp_config is None:
        return errors

    plugin_root = (root / PLUGIN_ROOT_PATH).resolve()
    if not plugin_root.is_dir():
        errors.append(f"plugin root does not exist: {PLUGIN_ROOT_PATH}")
        return errors

    manifest_name = manifest.get("name")
    if not isinstance(manifest_name, str) or not manifest_name:
        errors.append("plugin manifest name must be a nonempty string")

    entries = marketplace.get("plugins")
    entry: dict[str, Any] | None = None
    if not isinstance(entries, list):
        errors.append("marketplace plugins must be an array")
    else:
        objects = [item for item in entries if isinstance(item, dict)]
        matching = [item for item in objects if item.get("name") == manifest_name]
        if len(matching) == 1:
            entry = matching[0]
        elif len(matching) > 1:
            errors.append(f"marketplace has duplicate plugin name: {manifest_name}")
        elif len(objects) == 1:
            entry = objects[0]
            errors.append(
                "marketplace plugin name does not agree with plugin manifest name"
            )
        else:
            errors.append(
                "marketplace has no unique plugin entry matching the plugin manifest name"
            )

    if entry is not None:
        source = entry.get("source")
        if not isinstance(source, dict):
            errors.append("marketplace plugin source must be an object")
        else:
            if source.get("source") != "local":
                errors.append("marketplace plugin source type must be local")
            source_target = _resolve_reference(
                base=root,
                allowed_root=plugin_root,
                reference=source.get("path"),
                label="marketplace plugin source path",
                errors=errors,
                expected_kind="directory",
            )
            if source_target is not None and source_target != plugin_root:
                errors.append(
                    "marketplace plugin source path must identify the plugin root"
                )
        if entry.get("name") != manifest_name:
            errors.append(
                "marketplace plugin name does not agree with plugin manifest name"
            )

    _resolve_reference(
        base=plugin_root,
        allowed_root=plugin_root,
        reference=manifest.get("skills"),
        label="plugin skills reference",
        errors=errors,
        expected_kind="directory",
    )
    manifest_mcp = _resolve_reference(
        base=plugin_root,
        allowed_root=plugin_root,
        reference=manifest.get("mcpServers"),
        label="plugin MCP reference",
        errors=errors,
        expected_kind="file",
    )
    if manifest_mcp is not None and manifest_mcp != (root / MCP_CONFIG_PATH).resolve():
        errors.append("plugin MCP reference must identify the bundled .mcp.json")

    servers = mcp_config.get("mcpServers")
    if not isinstance(servers, dict) or not servers:
        errors.append("MCP metadata must define at least one server")
    else:
        for server_name, server in servers.items():
            if not isinstance(server, dict):
                errors.append(f"MCP server {server_name!r} must be an object")
                continue
            _resolve_reference(
                base=plugin_root,
                allowed_root=plugin_root,
                reference=server.get("command"),
                label=f"MCP server {server_name!r} command",
                errors=errors,
                expected_kind="file",
            )
            _resolve_reference(
                base=plugin_root,
                allowed_root=plugin_root,
                reference=server.get("cwd"),
                label=f"MCP server {server_name!r} cwd",
                errors=errors,
                expected_kind="directory",
            )

    return errors


def _tracked_paths(root: Path) -> list[Path]:
    completed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git ls-files failed: {detail or 'unknown error'}")
    return [
        Path(os.fsdecode(raw_path))
        for raw_path in completed.stdout.split(b"\0")
        if raw_path
    ]


def verify_repository(root: Path) -> list[str]:
    """Return all tracked-content and metadata errors for a repository."""

    try:
        tracked_paths = _tracked_paths(root)
    except (OSError, RuntimeError) as error:
        errors = [str(error)]
    else:
        errors = scan_paths(root, tracked_paths)
    errors.extend(validate_metadata(root))
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = verify_repository(root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("repository safety verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
