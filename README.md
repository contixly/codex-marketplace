# Contixly Codex Marketplace

A public, Git-backed catalog of reusable Codex plugins and custom pets maintained by Contixly. The repository can host independent plugins under `plugins/` and portable pet packages under `pets/`.

## Install the marketplace

Add the marketplace from its public GitHub repository and pin it to `main`:

```bash
codex plugin marketplace add contixly/codex-marketplace --ref main
```

Verify that Codex sees the source and inspect the plugins currently offered by it:

```bash
codex plugin marketplace list
codex plugin list --marketplace contixly-codex-marketplace --available --json
```

Choose a plugin from the catalog below and follow its linked guide. Plugin pages own their installation commands and any required account or service configuration.

## Plugin catalog

| Plugin | Version | Description | Documentation |
| --- | --- | --- | --- |
| `telegram-personal` | `0.2.0` | Connect a private Telegram user account locally, with bounded reads and confirmation-gated message, photo, and document sends. | [Telegram Personal](plugins/telegram-personal/README.md) |

## Pet catalog

Each pet package contains its `pet.json` manifest and a v2 transparent WebP spritesheet. Select **Install** in the desktop app to add a pet, then choose it in **Settings > Pets**.

| Pet | Description | Installation |
| --- | --- | --- |
| `Koda` | A calm, curious midnight-blue pixel cat who focuses deeply, helps eagerly, and stays slightly mischievous. | [Install Koda](codex://pets/install?name=Koda&description=A+calm%2C+curious+midnight-blue+pixel+cat+who+focuses+deeply%2C+helps+eagerly%2C+and+stays+slightly+mischievous.&imageUrl=https%3A%2F%2Fraw.githubusercontent.com%2Fcontixly%2Fcodex-marketplace%2Fmain%2Fpets%2Fkoda%2Fspritesheet.webp&spriteVersionNumber=2) |
| `WALL-E` | A gentle, touching faithful pixel-art WALL-E cleanup robot with weathered binocular eyes and heavy caterpillar tracks. | [Install WALL-E](codex://pets/install?name=WALL-E&description=A+gentle%2C+touching+faithful+pixel-art+WALL-E+cleanup+robot+with+weathered+binocular+eyes+and+heavy+caterpillar+tracks.&imageUrl=https%3A%2F%2Fraw.githubusercontent.com%2Fcontixly%2Fcodex-marketplace%2Fmain%2Fpets%2Fwall-e%2Fspritesheet.webp&spriteVersionNumber=2) |

## Update the marketplace

Refresh the local snapshot before installing a new plugin version:

```bash
codex plugin marketplace upgrade contixly-codex-marketplace
```

Each installed plugin may require a reinstall or additional migration steps. Follow that plugin's linked guide after refreshing the marketplace.

## Remove the marketplace

Remove installed plugins using their individual guides first. Then remove the marketplace source:

```bash
codex plugin marketplace remove contixly-codex-marketplace
```

Removing a marketplace source does not delete service credentials or other runtime data owned by an installed plugin. Review the plugin guide before deleting any external data directory.

## License

This marketplace is released under the [MIT License](LICENSE).
