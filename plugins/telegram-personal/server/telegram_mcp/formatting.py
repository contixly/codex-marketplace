from __future__ import annotations


def clamp_limit(value: int | None, *, default: int, maximum: int) -> int:
    if value is None:
        return default
    return min(max(value, 1), maximum)


def build_action_summary(
    *,
    account_label: str,
    recipient_label: str,
    action: str,
    payload: str,
) -> str:
    return "\n".join(
        [
            f"Account: {account_label}",
            f"Recipient: {recipient_label}",
            f"Action: {action}",
            "Payload:",
            payload,
            "Expected effect: The action will be submitted to the selected "
            "Telegram recipient after confirmation.",
            "Risk/rollback: Telegram sends and edits may be visible immediately; "
            "rollback may require a follow-up delete or corrective message.",
        ]
    )
