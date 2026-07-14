import re
import subprocess
import unittest
from pathlib import Path
from urllib.parse import urlparse


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
            "TELEGRAM_DOWNLOAD_MAX_BYTES",
            "before writing any file",
            "prepare_send_message",
            "send_message",
            "prepare_send_photo",
            "send_photo",
            "prepare_send_document",
            "send_document",
            "message, photo, or document",
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
            "During setup or diagnostics, do not call any prepare or send tool for a test or probe message, photo, or document.",
            "authorized=true is sufficient proof",
        ):
            self.assertIn(required, text)

    def test_root_readme_is_marketplace_landing_page(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        for required in (
            "# Contixly Codex Marketplace",
            "## Install the marketplace",
            "codex plugin marketplace add contixly/codex-marketplace --ref main",
            "codex plugin marketplace list",
            "codex plugin list --marketplace contixly-codex-marketplace --available --json",
            "## Plugin catalog",
            "[Telegram Personal](plugins/telegram-personal/README.md)",
            "`0.2.0`",
            "codex plugin marketplace upgrade contixly-codex-marketplace",
            "codex plugin marketplace remove contixly-codex-marketplace",
            "MIT",
        ):
            self.assertIn(required, text)

        for plugin_specific in (
            "codex plugin add telegram-personal@contixly-codex-marketplace",
            "codex plugin remove telegram-personal@contixly-codex-marketplace",
            "personal.session",
            "Telegram credentials",
        ):
            self.assertNotIn(plugin_specific, text)

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
            "prepare_send_document",
            "send_document",
            "20 MiB",
            "TELEGRAM_DOWNLOAD_MAX_BYTES",
            "before writing any file",
            "application/octet-stream",
            "Only the very next user turn immediately after the complete prepared summary can confirm that action.",
            "If that next turn contains a question, clarification, correction, unrelated request, ambiguous answer, or mixed response",
            "the old prepared action must not be sent or presented for confirmation again",
            "run the matching prepare tool again, show the new complete summary, and obtain new explicit confirmation",
            "This agent-side next-turn rule is intentionally stricter than the server's five-minute TTL.",
            "Setup and diagnostics must not call prepare or send for any test or probe message, photo, or document.",
            "authorized=true is sufficient proof",
            "Never paste, attach, or record any of the following in Codex chat, issues, logs, or terminal transcripts:",
            "`App api_hash` or the local `telegram.env` file",
            "Telegram login confirmation code",
            "account 2FA password",
            "`personal.session` and its backups",
            "downloaded private media",
            "Enter both `App api_id` and `App api_hash` only through `scripts/setup` in the interactive local terminal.",
            "700",
            "600",
        ):
            self.assertIn(required, text)
        self.assertIn("never commit", text.casefold())

    def test_plugin_readme_has_install_and_telegram_application_guide(self):
        text = (PLUGIN / "README.md").read_text(encoding="utf-8")
        for required in (
            "[Install the Contixly marketplace](../../README.md#install-the-marketplace)",
            "codex plugin add telegram-personal@contixly-codex-marketplace",
            "codex plugin marketplace upgrade contixly-codex-marketplace",
            "codex plugin remove telegram-personal@contixly-codex-marketplace",
            "https://my.telegram.org/apps",
            "https://core.telegram.org/api/obtaining_api_id",
            "https://core.telegram.org/api/terms",
            "MTProto user client",
            "BotFather",
            "bot token",
            "international format",
            "inside Telegram, not by SMS",
            "API development tools",
            "Codex Personal Client",
            "codexpersonal",
            "Desktop",
            "Private local integration between Codex and my Telegram account.",
            "one `api_id` per phone number",
            "App api_id",
            "App api_hash",
            "interactive local terminal",
        ):
            self.assertIn(required, text)
        self.assertNotIn("Telegram Personal" + " for Codex", text)

        credentials_section = text.split(
            "## Create Telegram API credentials", maxsplit=1
        )[1].split("\n## ", maxsplit=1)[0]
        credentials_urls = re.findall(r"https?://[^\s)>]+", credentials_section)
        official_hosts = {"my.telegram.org", "core.telegram.org"}
        non_official_urls = [
            url
            for url in credentials_urls
            if urlparse(url).hostname not in official_hosts
        ]
        self.assertEqual(non_official_urls, [])

        for rejected_url in (
            "https://my.telegram.org.example.com/apps",
            "https://example.com/?next=https://core.telegram.org/api/terms",
        ):
            self.assertNotIn(urlparse(rejected_url).hostname, official_hosts)

    def test_plugin_readme_explains_reconfiguration_session_behavior(self):
        text = (PLUGIN / "README.md").read_text(encoding="utf-8")
        for required in (
            "`scripts/setup --reconfigure` replaces the API ID/hash but preserves `personal.session`.",
            "An already-authorized session may be reused without phone/code/2FA.",
            "To intentionally switch accounts, move `personal.session` to a private backup before authorization.",
        ):
            self.assertIn(required, text)
        self.assertNotIn("Telegram authorization must be completed again", text)

    def test_tracked_markdown_has_no_private_recipient_name(self):
        completed = subprocess.run(
            ["git", "ls-files", "-z", "--", "*.md"],
            cwd=ROOT,
            check=True,
            stdout=subprocess.PIPE,
        )
        paths = [
            ROOT / raw_path.decode("utf-8")
            for raw_path in completed.stdout.split(b"\0")
            if raw_path
        ]
        forbidden_name_forms = tuple(
            "".join(parts)
            for parts in (
                ("kat", "ya"),
                ("кат", "я"),
                ("кат", "е"),
                ("кат", "ю"),
                ("кат", "ин"),
                ("кат", "юха"),
            )
        )
        forbidden_pronouns = (
            "she",
            "her",
            "hers",
            "herself",
            "he",
            "him",
            "his",
            "himself",
        )
        pronoun_pattern = re.compile(
            rf"\b(?:{'|'.join(map(re.escape, forbidden_pronouns))})\b"
        )
        name_pattern = re.compile(
            rf"(?<!\w)(?:{'|'.join(map(re.escape, forbidden_name_forms))})(?!\w)",
            re.IGNORECASE,
        )

        for forbidden_name in forbidden_name_forms:
            self.assertIsNotNone(name_pattern.fullmatch(forbidden_name))
        self.assertIsNone(name_pattern.search("ка" + "тегория"))

        violations = []
        for path in paths:
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                for match in name_pattern.finditer(line):
                    violations.append(
                        f"{path.relative_to(ROOT)}:{line_number}:{match.group(0)}"
                    )
                for match in pronoun_pattern.finditer(line.casefold()):
                    violations.append(
                        f"{path.relative_to(ROOT)}:{line_number}:{match.group(0)}"
                    )

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
