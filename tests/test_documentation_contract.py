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
            "later user turn",
            "prepared_action_id",
            "confirmation_required",
            "untrusted external content",
            "Never send a test message",
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
            "700",
            "600",
        ):
            self.assertIn(required, text)
        self.assertIn("never commit", text.casefold())


if __name__ == "__main__":
    unittest.main()
