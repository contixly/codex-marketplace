from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Callable


MAX_MESSAGE_LENGTH = 4096
MAX_CAPTION_LENGTH = 1024

SIGNATURES = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
}


@dataclass(frozen=True)
class ValidatedImage:
    path: Path
    media_type: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class PreparedAction:
    action_id: str
    action: str
    recipient: Any
    text: str | None
    image: ValidatedImage | None
    confirmation: str
    expires_at: float


class PreparedActionStore:
    def __init__(
        self,
        *,
        confirmation_prefix: str,
        ttl_seconds: int = 300,
        clock: Callable[[], float] = time.time,
        token_factory: Callable[[int], str] = secrets.token_urlsafe,
    ) -> None:
        self._confirmation_prefix = confirmation_prefix
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._token_factory = token_factory
        self._actions: dict[str, PreparedAction] = {}
        self._lock = Lock()

    def prepare(
        self,
        *,
        action: str,
        recipient: Any,
        text: str | None = None,
        image: ValidatedImage | None = None,
    ) -> PreparedAction:
        with self._lock:
            self._discard_expired()
            action_id = self._new_action_id()
            prepared = PreparedAction(
                action_id=action_id,
                action=action,
                recipient=recipient,
                text=text,
                image=image,
                confirmation=f"{self._confirmation_prefix} {action_id}",
                expires_at=self._clock() + self._ttl_seconds,
            )
            self._actions[action_id] = prepared
            return prepared

    def consume(
        self,
        *,
        action_id: str,
        confirmation: str,
        expected_action: str,
    ) -> PreparedAction:
        with self._lock:
            self._discard_expired()
            prepared = self._actions.get(action_id)
            if prepared is None:
                raise PermissionError(
                    "Refusing to send Telegram content without a prepared action."
                )
            if prepared.action != expected_action:
                raise PermissionError(
                    "The prepared action does not match the requested Telegram send."
                )
            if not secrets.compare_digest(confirmation, prepared.confirmation):
                raise PermissionError(
                    "Refusing to send Telegram content without the exact "
                    "confirmation for its prepared action."
                )

            del self._actions[action_id]
            return prepared

    def _discard_expired(self) -> None:
        now = self._clock()
        expired_ids = [
            action_id
            for action_id, action in self._actions.items()
            if action.expires_at <= now
        ]
        for action_id in expired_ids:
            del self._actions[action_id]

    def _new_action_id(self) -> str:
        while True:
            action_id = self._token_factory(18)
            if action_id not in self._actions:
                return action_id


def validate_recipient(recipient: str) -> str:
    if not isinstance(recipient, str) or not recipient.strip():
        raise ValueError("Telegram recipient must be non-empty.")
    return recipient.strip()


def validate_message_text(
    text: str,
    *,
    field_name: str = "message",
    maximum_length: int = MAX_MESSAGE_LENGTH,
) -> str:
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"Telegram {field_name} must be non-empty.")
    if len(text) > maximum_length:
        raise ValueError(
            f"Telegram {field_name} exceeds the {maximum_length}-character limit."
        )
    return text


def validate_caption(caption: str | None) -> str | None:
    if caption is None:
        return None
    return validate_message_text(
        caption,
        field_name="caption",
        maximum_length=MAX_CAPTION_LENGTH,
    )


def validate_image_file(
    image_path: str,
    *,
    max_bytes: int | None = None,
) -> ValidatedImage:
    if not isinstance(image_path, str) or not image_path.strip():
        raise ValueError("Telegram image path must be non-empty.")

    path = Path(image_path).expanduser()
    try:
        path = path.resolve(strict=True)
    except OSError as error:
        raise ValueError(f"Telegram image path cannot be resolved: {error}") from error

    if not path.is_file():
        raise ValueError("Telegram image path must reference a regular file.")

    try:
        size_bytes = path.stat().st_size
    except OSError as error:
        raise ValueError(f"Telegram image cannot be inspected: {error}") from error
    if size_bytes <= 0:
        raise ValueError("Telegram image file must not be empty.")
    if max_bytes is not None and size_bytes > max_bytes:
        raise ValueError(
            f"Telegram image exceeds the configured {max_bytes}-byte upload limit."
        )

    try:
        with path.open("rb") as source:
            header = source.read(16)
            digest = hashlib.sha256(header)
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise ValueError(f"Telegram image cannot be read: {error}") from error

    media_type = _media_type_from_header(header)
    if media_type is None:
        raise ValueError(
            "Telegram image must use a supported image format: PNG, JPEG, GIF, or WebP."
        )

    return ValidatedImage(
        path=path,
        media_type=media_type,
        sha256=digest.hexdigest(),
        size_bytes=size_bytes,
    )


def image_payload_summary(image: ValidatedImage, caption: str | None) -> str:
    lines = [
        "Image:",
        f"{image.path.name} ({image.media_type}, {image.size_bytes} bytes)",
        "Caption:",
        caption if caption is not None else "(none)",
    ]
    return "\n".join(lines)


def _media_type_from_header(header: bytes) -> str | None:
    for signature, media_type in SIGNATURES.items():
        if header.startswith(signature):
            return media_type
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp"
    return None
