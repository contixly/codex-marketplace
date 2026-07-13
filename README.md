# Contixly Codex Marketplace

A public, Git-backed marketplace for reusable Codex plugins. The repository is designed to host multiple independent plugins under `plugins/` without publishing their users' runtime data.

## Install

Add the marketplace and install Telegram Personal:

```bash
codex plugin marketplace add contixly/codex-marketplace --ref main
codex plugin add telegram-personal@contixly-codex-marketplace
```

Restart Codex and open a new task after installation so Codex loads the new plugin snapshot, skill, and MCP server. Then follow the [Telegram Personal setup guide](plugins/telegram-personal/README.md).

## Plugin catalog

| Plugin | Version | Description |
| --- | --- | --- |
| `telegram-personal` | `0.2.0` | Connects a private Telegram account locally, with confirmation-gated message, photo, and document sends. |

## Update

Refresh the Git marketplace snapshot, then reinstall the plugin from that snapshot:

```bash
codex plugin marketplace upgrade contixly-codex-marketplace
codex plugin remove telegram-personal@contixly-codex-marketplace
codex plugin add telegram-personal@contixly-codex-marketplace
```

Restart Codex and open a new task after reinstalling. Telegram credentials, sessions, and downloads remain outside the plugin snapshot, so reinstalling does not delete them.

## Remove

Remove the installed plugin first, then its configured marketplace source:

```bash
codex plugin remove telegram-personal@contixly-codex-marketplace
codex plugin marketplace remove contixly-codex-marketplace
```

These commands do not delete Telegram Personal's separate runtime data directory. See the plugin guide before deleting that directory.

## License

This marketplace is released under the [MIT License](LICENSE).
