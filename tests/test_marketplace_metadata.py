import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE = ROOT / ".agents/plugins/marketplace.json"
PLUGIN_ROOT = ROOT / "plugins/telegram-personal"


class MarketplaceMetadataTests(unittest.TestCase):
    def test_marketplace_points_to_telegram_plugin(self):
        payload = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
        self.assertEqual(payload["name"], "contixly-codex-marketplace")
        self.assertEqual(payload["interface"]["displayName"], "Contixly Codex Marketplace")
        self.assertEqual(len(payload["plugins"]), 1)
        entry = payload["plugins"][0]
        self.assertEqual(entry["name"], "telegram-personal")
        self.assertEqual(entry["source"], {"source": "local", "path": "./plugins/telegram-personal"})
        self.assertEqual(entry["policy"], {"installation": "AVAILABLE", "authentication": "ON_INSTALL"})
        self.assertEqual(entry["category"], "Productivity")

    def test_plugin_manifest_exposes_skill_and_mcp(self):
        payload = json.loads((PLUGIN_ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["name"], "telegram-personal")
        self.assertEqual(payload["version"], "0.2.0")
        self.assertEqual(payload["author"]["name"], "Contixly")
        self.assertEqual(payload["skills"], "./skills/")
        self.assertEqual(payload["mcpServers"], "./.mcp.json")

    def test_mcp_manifest_uses_portable_launcher(self):
        payload = json.loads((PLUGIN_ROOT / ".mcp.json").read_text(encoding="utf-8"))
        server = payload["mcpServers"]["telegram"]
        self.assertEqual(server["command"], "./scripts/telegram-mcp")
        self.assertEqual(server["cwd"], ".")
        self.assertEqual(server["startup_timeout_sec"], 30)
        self.assertEqual(server["tool_timeout_sec"], 120)
        self.assertEqual(server["default_tools_approval_mode"], "prompt")


if __name__ == "__main__":
    unittest.main()
