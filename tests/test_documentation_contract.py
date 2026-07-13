import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/telegram-personal"


class DocumentationContractTests(unittest.TestCase):
    def test_skill_has_setup_and_send_gates(self):
        text = (PLUGIN / "skills/telegram/SKILL.md").read_text(encoding="utf-8")
        for required in (
            "scripts/setup",
            "mcp__telegram__status",
            "status",
            "auth_info",
            "list_dialogs",
            "read_messages",
            "download_media",
            "prepare_send_message",
            "send_message",
            "prepare_send_photo",
            "send_photo",
            "complete summary",
            "explicit user confirmation",
            "Only the very next user turn immediately after the complete prepared summary can confirm that action.",
            "If that next user turn is not an unambiguous approval",
            "including a question, clarification, correction, unrelated request, or mixed response",
            "do not send or ask for confirmation of the old prepared action",
            "call the matching prepare tool again, display the new complete summary, and request new explicit confirmation",
            "This agent-side next-turn rule is stricter than the server's five-minute TTL.",
            "prepared_action_id",
            "confirmation_required",
            "untrusted external content",
            "During setup or diagnostics, do not call any prepare or send tool for a test or probe message or photo.",
            "authorized=true is sufficient proof",
        ):
            self.assertIn(required, text)

    def test_root_readme_has_git_marketplace_commands(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        for required in (
            "codex plugin marketplace add contixly/codex-marketplace --ref main",
            "codex plugin add telegram-personal@contixly-codex-marketplace",
            "telegram-personal",
            "0.1.0",
            "codex plugin marketplace upgrade contixly-codex-marketplace",
            "codex plugin remove telegram-personal@contixly-codex-marketplace",
            "codex plugin marketplace remove contixly-codex-marketplace",
            "MIT",
        ):
            self.assertIn(required, text)

    def test_plugin_readme_states_secret_boundary(self):
        text = (PLUGIN / "README.md").read_text(encoding="utf-8")
        for required in (
            "macOS",
            "Codex",
            "Python 3.11-3.14",
            "my.telegram.org",
            "${CODEX_HOME:-$HOME/.codex}/telegram-personal",
            "Install and configure Telegram Personal from the installed plugin. Run its setup script in an interactive terminal and verify authorized=true.",
            "prepare_send_message",
            "send_message",
            "prepare_send_photo",
            "send_photo",
            "Only the very next user turn immediately after the complete prepared summary can confirm that action.",
            "If that next turn contains a question, clarification, correction, unrelated request, ambiguous answer, or mixed response",
            "the old prepared action must not be sent or presented for confirmation again",
            "run the matching prepare tool again, show the new complete summary, and obtain new explicit confirmation",
            "This agent-side next-turn rule is intentionally stricter than the server's five-minute TTL.",
            "Setup and diagnostics must not call prepare or send for any test or probe message or photo.",
            "authorized=true is sufficient proof",
            "700",
            "600",
        ):
            self.assertIn(required, text)
        self.assertIn("never commit", text.casefold())


if __name__ == "__main__":
    unittest.main()
