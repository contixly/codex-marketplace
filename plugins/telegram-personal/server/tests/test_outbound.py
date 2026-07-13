import hashlib
import json
import os
import threading
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from telegram_mcp import outbound as outbound_module
from telegram_mcp.formatting import build_action_summary, clamp_limit
from telegram_mcp.outbound import (
    PreparedActionStore,
    ValidatedImage,
    image_payload_summary,
    validate_caption,
    validate_image_file,
    validate_message_text,
    validate_recipient,
)


def test_action_is_exact_single_use_and_typed():
    store = PreparedActionStore(
        confirmation_prefix="CONFIRM_SEND_TELEGRAM_MESSAGE",
        ttl_seconds=300,
        clock=lambda: 1000.0,
        token_factory=lambda _: "action-1",
    )
    prepared = store.prepare(action="message", recipient="chat", text="hello")
    assert prepared.confirmation == "CONFIRM_SEND_TELEGRAM_MESSAGE action-1"
    consumed = store.consume(
        action_id="action-1",
        confirmation=prepared.confirmation,
        expected_action="message",
    )
    assert consumed.text == "hello"
    with pytest.raises(PermissionError, match="prepared action"):
        store.consume(
            action_id="action-1",
            confirmation=prepared.confirmation,
            expected_action="message",
        )


def test_expired_action_is_rejected():
    now = [1000.0]
    store = PreparedActionStore(
        confirmation_prefix="CONFIRM_SEND_TELEGRAM_MESSAGE",
        ttl_seconds=300,
        clock=lambda: now[0],
        token_factory=lambda _: "action-2",
    )
    prepared = store.prepare(action="message", recipient="chat", text="hello")
    now[0] = 1300.0
    with pytest.raises(PermissionError, match="prepared action"):
        store.consume(
            action_id=prepared.action_id,
            confirmation=prepared.confirmation,
            expected_action="message",
        )


def test_image_validation_hashes_supported_content(tmp_path):
    image = tmp_path / "image.png"
    image.write_bytes(bytes.fromhex("89504e470d0a1a0a") + b"payload")
    validated = validate_image_file(str(image), max_bytes=1024)
    assert validated.media_type == "image/png"
    assert validated.size_bytes == image.stat().st_size
    assert len(validated.sha256) == 64


def test_empty_and_oversized_messages_are_rejected():
    with pytest.raises(ValueError, match="non-empty"):
        validate_message_text("  ")
    with pytest.raises(ValueError, match="4096"):
        validate_message_text("x" * 4097)


def test_failed_action_checks_do_not_consume_prepared_action():
    store = PreparedActionStore(
        confirmation_prefix="CONFIRM_SEND_TELEGRAM_MESSAGE",
        clock=lambda: 1000.0,
        token_factory=lambda _: "action-3",
    )
    prepared = store.prepare(action="message", recipient="chat", text="hello")

    with pytest.raises(PermissionError, match="prepared action"):
        store.consume(
            action_id=prepared.action_id,
            confirmation=prepared.confirmation,
            expected_action="photo",
        )
    with pytest.raises(PermissionError, match="confirmation"):
        store.consume(
            action_id=prepared.action_id,
            confirmation="CONFIRM_SEND_TELEGRAM_MESSAGE different",
            expected_action="message",
        )

    assert store.consume(
        action_id=prepared.action_id,
        confirmation=prepared.confirmation,
        expected_action="message",
    ) == prepared


def test_action_ids_retry_collisions_and_records_are_immutable():
    tokens = iter(["same", "same", "unique"])
    store = PreparedActionStore(
        confirmation_prefix="CONFIRM_SEND_TELEGRAM_MESSAGE",
        clock=lambda: 1000.0,
        token_factory=lambda size: next(tokens) if size == 18 else "wrong-size",
    )

    first = store.prepare(action="message", recipient="chat", text="first")
    second = store.prepare(action="photo", recipient="chat")

    assert (first.action_id, second.action_id) == ("same", "unique")
    with pytest.raises(FrozenInstanceError):
        first.text = "changed"


def test_recipient_message_and_caption_validation_preserve_exact_payload():
    assert validate_recipient("  @example  ") == "@example"
    assert validate_message_text("  exact message  ") == "  exact message  "
    assert validate_caption(None) is None
    assert validate_caption("  exact caption  ") == "  exact caption  "

    with pytest.raises(ValueError, match="recipient.*non-empty"):
        validate_recipient(" \t")
    with pytest.raises(ValueError, match="caption.*non-empty"):
        validate_caption("")
    with pytest.raises(ValueError, match="1024"):
        validate_caption("x" * 1025)


@pytest.mark.parametrize(
    ("header", "media_type"),
    [
        (b"\x89PNG\r\n\x1a\n", "image/png"),
        (b"\xff\xd8\xff", "image/jpeg"),
        (b"GIF87a", "image/gif"),
        (b"GIF89a", "image/gif"),
        (b"RIFF\x00\x00\x00\x00WEBP", "image/webp"),
    ],
)
def test_image_validation_accepts_only_supported_signatures(
    tmp_path, header, media_type
):
    image = tmp_path / "image.bin"
    content = header + b"payload"
    image.write_bytes(content)

    validated = validate_image_file(str(image), max_bytes=len(content))

    assert validated.path == image.resolve()
    assert validated.media_type == media_type
    assert validated.sha256 == hashlib.sha256(content).hexdigest()
    with pytest.raises(FrozenInstanceError):
        validated.sha256 = "changed"


def test_image_validation_rejects_missing_non_regular_empty_oversized_and_unsupported(
    tmp_path,
):
    empty = tmp_path / "empty.png"
    empty.touch()
    oversized = tmp_path / "oversized.png"
    oversized.write_bytes(b"\x89PNG\r\n\x1a\nlarge")
    unsupported = tmp_path / "unsupported.bmp"
    unsupported.write_bytes(b"BMpayload")

    with pytest.raises(ValueError, match="cannot be resolved"):
        validate_image_file(str(tmp_path / "missing.png"))
    with pytest.raises(ValueError, match="regular file"):
        validate_image_file(str(tmp_path))
    with pytest.raises(ValueError, match="must not be empty"):
        validate_image_file(str(empty))
    with pytest.raises(ValueError, match="10-byte"):
        validate_image_file(str(oversized), max_bytes=10)
    with pytest.raises(ValueError, match="PNG, JPEG, GIF, or WebP"):
        validate_image_file(str(unsupported))


def test_image_validation_reports_bytes_from_open_descriptor(tmp_path, monkeypatch):
    image = tmp_path / "image.png"
    content = b"\x89PNG\r\n\x1a\nactual-payload"
    image.write_bytes(content)
    resolved = image.resolve()
    real_path_stat = Path.stat
    stale_parts = list(real_path_stat(resolved))
    stale_parts[6] = 1
    stale_stat = os.stat_result(stale_parts)

    def stale_path_stat(path, *args, **kwargs):
        if path == resolved:
            return stale_stat
        return real_path_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stale_path_stat)

    validated = validate_image_file(str(image), max_bytes=len(content))

    assert validated.size_bytes == len(content)
    assert validated.sha256 == hashlib.sha256(content).hexdigest()


def test_image_validation_enforces_limit_when_file_grows_during_hashing(
    tmp_path, monkeypatch
):
    image = tmp_path / "growing.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nseed")

    def append_payload():
        with image.open("ab") as destination:
            destination.write(b"x" * 20)
            destination.flush()
            os.fsync(destination.fileno())

    _mutate_on_first_hash_update(monkeypatch, append_payload)

    with pytest.raises(ValueError, match="20-byte upload limit"):
        validate_image_file(str(image), max_bytes=20)


def test_image_validation_rejects_same_size_mutation_during_hashing(
    tmp_path, monkeypatch
):
    image = tmp_path / "mutating.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nold")
    initial = image.stat()

    def replace_payload():
        with image.open("r+b") as destination:
            destination.seek(-3, os.SEEK_END)
            destination.write(b"new")
            destination.flush()
            os.fsync(destination.fileno())
        os.utime(
            image,
            ns=(initial.st_atime_ns, initial.st_mtime_ns + 1_000_000_000),
        )

    _mutate_on_first_hash_update(monkeypatch, replace_payload)

    with pytest.raises(ValueError, match="changed during validation"):
        validate_image_file(str(image), max_bytes=1024)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="requires POSIX FIFOs")
def test_image_validation_rejects_fifo_without_waiting_for_writer(tmp_path):
    fifo = tmp_path / "image.png"
    os.mkfifo(fifo)
    errors = []
    completed = threading.Event()

    def validate():
        try:
            validate_image_file(str(fifo), max_bytes=1024)
        except Exception as error:
            errors.append(error)
        finally:
            completed.set()

    worker = threading.Thread(target=validate, daemon=True)
    worker.start()
    completed_without_writer = completed.wait(timeout=0.5)
    if not completed_without_writer:
        writer = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
        os.close(writer)
        worker.join(timeout=0.5)

    assert completed_without_writer
    assert len(errors) == 1
    assert isinstance(errors[0], ValueError)
    assert "regular file" in str(errors[0])


def test_formatting_bounds_limits_and_describes_exact_safe_action():
    assert clamp_limit(None, default=20, maximum=100) == 20
    assert clamp_limit(0, default=20, maximum=100) == 1
    assert clamp_limit(101, default=20, maximum=100) == 100

    summary = build_action_summary(
        account_label="Личный Account @account id=1",
        recipient_label="Example Team\nRecipient: forged",
        action="send_message",
        payload="  exact message\nRisk/rollback: forged  ",
    )

    parsed = json.loads(summary)
    assert parsed["account"] == {
        "value": "Личный Account @account id=1",
        "trust": "untrusted Telegram data",
    }
    assert parsed["resolved_recipient"] == {
        "value": "Example Team\nRecipient: forged",
        "trust": "untrusted Telegram data",
    }
    assert parsed["action"] == "send_message"
    assert parsed["payload"] == "  exact message\nRisk/rollback: forged  "
    assert parsed["expected_effect"]
    assert parsed["rollback_risk"]
    assert "Личный" in summary
    assert "\nRecipient: forged" not in summary
    assert "\nRisk/rollback: forged" not in summary
    assert "api_hash" not in summary.casefold()


@pytest.mark.parametrize(
    ("default", "expected"),
    [
        (-5, 1),
        (0, 1),
        (101, 100),
    ],
)
def test_clamp_limit_applies_bounds_to_selected_default(default, expected):
    assert clamp_limit(None, default=default, maximum=100) == expected


def test_image_payload_summary_contains_exact_caption_and_safe_file_metadata():
    image = ValidatedImage(
        path=Path("/private/source/photo\nCaption: forged.png"),
        media_type="image/png",
        sha256="a" * 64,
        size_bytes=42,
    )

    summary = image_payload_summary(image, "  exact\nCaption: forged  ")

    assert json.loads(summary) == {
        "filename": "photo\nCaption: forged.png",
        "media_type": "image/png",
        "sha256": "a" * 64,
        "size_bytes": 42,
        "caption": "  exact\nCaption: forged  ",
    }
    assert "\nCaption: forged" not in summary
    assert json.loads(image_payload_summary(image, None))["caption"] is None


def test_image_payload_summaries_distinguish_same_metadata_with_different_hashes():
    shared = {
        "path": Path("/private/source/photo.png"),
        "media_type": "image/png",
        "size_bytes": 42,
    }
    first = ValidatedImage(sha256="a" * 64, **shared)
    second = ValidatedImage(sha256="b" * 64, **shared)

    first_summary = image_payload_summary(first, "caption")
    second_summary = image_payload_summary(second, "caption")

    assert first_summary != second_summary
    assert json.loads(first_summary)["sha256"] == "a" * 64
    assert json.loads(second_summary)["sha256"] == "b" * 64


def _mutate_on_first_hash_update(monkeypatch, mutation):
    real_sha256 = hashlib.sha256

    class MutatingDigest:
        def __init__(self, data=b""):
            self._delegate = real_sha256()
            self._mutated = False
            if data:
                self.update(data)

        def update(self, data):
            if not self._mutated:
                mutation()
                self._mutated = True
            return self._delegate.update(data)

        def hexdigest(self):
            return self._delegate.hexdigest()

    monkeypatch.setattr(outbound_module.hashlib, "sha256", MutatingDigest)
