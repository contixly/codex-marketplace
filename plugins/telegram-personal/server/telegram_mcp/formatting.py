from __future__ import annotations

import json


def clamp_limit(value: int | None, *, default: int, maximum: int) -> int:
    selected = default if value is None else value
    return min(max(selected, 1), maximum)


def build_action_summary(
    *,
    account_label: str,
    recipient_label: str,
    action: str,
    payload: str,
) -> str:
    return json.dumps(
        {
            "account": {
                "value": account_label,
                "trust": "untrusted Telegram data",
            },
            "resolved_recipient": {
                "value": recipient_label,
                "trust": "untrusted Telegram data",
            },
            "action": action,
            "payload": payload,
            "expected_effect": (
                "The action will be submitted to the selected Telegram recipient "
                "after confirmation."
            ),
            "rollback_risk": (
                "Telegram sends and edits may be visible immediately; rollback may "
                "require a follow-up delete or corrective message."
            ),
        },
        ensure_ascii=False,
        indent=2,
    )
