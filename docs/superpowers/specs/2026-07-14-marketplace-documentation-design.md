# Marketplace Documentation Refresh Design

**Date:** 2026-07-14
**Status:** Approved for implementation planning

## Goal

Make the repository documentation suitable for a public, multi-plugin Codex marketplace. The root README becomes the stable marketplace landing page, while each plugin owns its installation and configuration instructions. Telegram Personal gains a beginner-oriented guide for creating the Telegram API application required by its local MTProto client.

## Audience

- Codex users adding the Contixly marketplace for the first time;
- users choosing and installing one plugin from the catalog;
- Telegram Personal users who have never created Telegram API credentials;
- future plugin maintainers adding entries without expanding the root README into a plugin-specific manual.

## Information Architecture

### Root `README.md`

The root page describes the marketplace, not Telegram Personal. It contains:

1. the marketplace purpose and public distribution model;
2. the command for adding `contixly/codex-marketplace` from `main`;
3. commands for listing or verifying the configured marketplace;
4. a plugin catalog with name, version, short description, and a link to each plugin's README;
5. generic marketplace refresh and removal instructions;
6. the repository license.

Plugin installation, update, removal, credentials, runtime state, and recovery details do not belong on this page.

### `plugins/telegram-personal/README.md`

The plugin page owns the complete Telegram Personal lifecycle:

1. prerequisites;
2. plugin installation, update, and removal commands;
3. creation of Telegram API credentials;
4. interactive local setup and account authorization;
5. private runtime data and secret boundaries;
6. read and confirmation-gated write tools;
7. recovery procedures.

The page links back to the root marketplace installation section rather than duplicating the marketplace's role.

## Telegram Application Guide

The guide is written for a first-time user and clearly distinguishes two Telegram integration models:

- Telegram Personal is an MTProto client acting as the user's Telegram account;
- it is not a Telegram Bot API integration, does not require BotFather, and does not accept a bot token.

The documented flow is:

1. Confirm the target account works in an official Telegram application.
2. Open the official [Telegram application management page](https://my.telegram.org/apps).
3. Enter the account phone number in international format.
4. Enter the confirmation code delivered inside Telegram, not an SMS code.
5. Open **API development tools**.
6. If an application already exists for the number, reuse its `App api_id` and `App api_hash`. Telegram currently allows one `api_id` per phone number.
7. Otherwise complete the application form. Suggested non-secret values are:
   - **App title:** `Telegram Personal for Codex`;
   - **Short name:** `codexpersonal`;
   - **Platform:** `Desktop`;
   - **Description:** `Private local integration between Codex and my Telegram account.`
8. If Telegram requires another field, provide accurate information; use only a URL the user controls when a URL is required.
9. Submit the form and locate the numeric `App api_id` and the `App api_hash`.
10. Keep the page open only long enough to enter those values into the plugin's interactive local `scripts/setup` prompt.

The guide links to Telegram's official [Creating your Telegram Application](https://core.telegram.org/api/obtaining_api_id) instructions and [API Terms of Service](https://core.telegram.org/api/terms).

## Secret and Account Boundaries

The documentation must state that the following values are never pasted into Codex chat, committed, placed in issues, or included in terminal transcripts:

- `api_hash` and the local `telegram.env` containing it;
- the Telegram login confirmation code;
- the account's 2FA password;
- `personal.session` and its backups;
- downloaded private media.

The API ID and API hash are entered only into the interactive setup process in the local terminal. Setup success is verified with `authorized=true`; no test message, photo, or document is prepared or sent.

## Public Language Policy

All tracked public Markdown documents use role-based language such as `the user`, `the recipient`, and `the installing user`. References to a specific private recipient are removed from:

- the Telegram Personal README;
- implementation plans and test scenarios under `docs/superpowers/`;
- any other tracked public documentation discovered during the implementation scan.

Examples that need a recipient remain neutral and must not imply that a real person is part of the published plugin contract.

## Verification

Automated documentation contracts will verify that:

1. the root README contains marketplace add, list, upgrade, and removal guidance plus a linked plugin catalog;
2. the root README does not contain Telegram Personal installation, update, removal, credential, or runtime instructions;
3. the Telegram Personal README contains its own install, update, and removal commands;
4. the Telegram guide distinguishes MTProto from BotFather, links official Telegram sources, describes international-format login and in-Telegram confirmation delivery, supplies example form values, and identifies `App api_id` and `App api_hash`;
5. setup and secret-safety rules remain present;
6. tracked Markdown files do not contain the removed private person's name or its known variants.

Repository safety validation, the complete test suite, Markdown review, link/path checks, and `git diff --check` must pass before the implementation is committed.

## Non-goals

- changing plugin runtime behavior, MCP tools, or Telegram authorization code;
- creating Telegram credentials or authorizing a live account during documentation work;
- documenting future plugins that do not yet exist;
- adding screenshots that can become stale or expose account information;
- moving plugin manuals into a separate documentation site.
