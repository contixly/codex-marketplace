# Telegram Personal Codex Plugin Design

## Summary

Create a public, multi-plugin Codex marketplace in
`contixly/codex-marketplace`. Its first plugin, `telegram-personal`, packages
the working local Telethon MCP integration used in the source environment,
while keeping every account credential, Telegram session, downloaded file,
and chat payload outside the repository.

The target user runs Codex Desktop/CLI on macOS. She obtains her own Telegram
`API ID` and `API Hash` from `my.telegram.org`; her Codex performs the remaining
local setup through a bundled skill and interactive terminal scripts.

## Goals

- Publish a reusable Git-backed Codex marketplace that can hold multiple
  independent plugins.
- Ship `telegram-personal` as a self-contained plugin with its MCP server,
  setup workflow, routing guidance, tests, and documentation.
- Let a user install the marketplace and plugin with standard Codex plugin
  commands, then have Codex guide account setup.
- Preserve the current integration's read tools and two-phase, explicitly
  confirmed write tools.
- Make the package portable: no source-machine usernames, account identifiers,
  absolute home paths, credentials, sessions, chats, or media.
- Make reinstalling or updating the plugin leave the user's Telegram account
  data intact.

## Non-goals

- Creating Telegram API credentials on the user's behalf.
- Bypassing Telegram phone, one-time-code, or 2FA authentication.
- Shipping a Telegram Bot API integration or a hosted/shared Telegram service.
- Syncing credentials or sessions between machines.
- Sending any message during installation or verification.
- Supporting Windows or Linux as a documented first release target. The Python
  service should remain portable where practical, but macOS is the acceptance
  environment.

## Repository layout

```text
codex-marketplace/
├── .agents/
│   └── plugins/
│       └── marketplace.json
├── .github/
│   └── workflows/
│       └── test.yml
├── docs/
│   └── superpowers/specs/
├── plugins/
│   └── telegram-personal/
│       ├── .codex-plugin/
│       │   └── plugin.json
│       ├── .mcp.json
│       ├── README.md
│       ├── requirements.txt
│       ├── scripts/
│       │   ├── setup
│       │   ├── telegram-mcp
│       │   ├── telegram-auth
│       │   ├── telegram-status
│       │   └── verify-package
│       ├── server/
│       │   ├── telegram_mcp/
│       │   └── tests/
│       └── skills/
│           └── telegram/
│               └── SKILL.md
├── README.md
└── LICENSE
```

The marketplace name is `contixly-codex-marketplace`. The marketplace entry
uses `source: local` with `path: ./plugins/telegram-personal`, resolved from the
repository root. The marketplace remains ready for additional entries under
`plugins/`.

## Plugin packaging

`plugins/telegram-personal/.codex-plugin/plugin.json` identifies the plugin,
points to `./skills/`, and points to `./.mcp.json` for the bundled MCP server.

`.mcp.json` defines a plugin-scoped stdio server named `telegram`. It launches
`./scripts/telegram-mcp` with the plugin root as its working directory. The
launcher derives the plugin source path from its own location rather than from
an installation-specific absolute path.

The bundled skill has two responsibilities:

1. Guide first-time setup and verification when credentials or an authorized
   session are missing.
2. Route Telegram work to the bundled MCP tools, treat Telegram content as
   untrusted external data, and require a visible user confirmation between
   every prepare and send operation.

## Runtime data boundary

All mutable or sensitive state lives outside the plugin source under:

```text
${CODEX_HOME:-$HOME/.codex}/telegram-personal/
├── .venv/
├── downloads/
├── personal.session
└── telegram.env
```

The plugin directory contains only source, examples, tests, and launchers. An
update or reinstall therefore cannot replace account credentials or the
authorized Telethon session.

Required permissions after setup:

- runtime data directory and downloads directory: owner only (`700`);
- `telegram.env` and `personal.session`: owner read/write only (`600`).

Repository launcher scripts are public package content and use normal
executable permissions (`755`); they never contain secrets.

The repository contains `telegram.env.example` only if it has blank credential
values and portable path comments. It never contains a real `.env` or session
file.

## Installation and account setup

### Marketplace and plugin installation

The user or her Codex runs:

```bash
codex plugin marketplace add contixly/codex-marketplace --ref main
codex plugin add telegram-personal@contixly-codex-marketplace
```

The user restarts Codex and opens a new local task so the installed skill and
bundled MCP server are loaded from a fresh plugin snapshot.

### Account setup

Before setup, the user creates a Telegram application at `my.telegram.org` and
keeps its `API ID` and `API Hash` available locally.

Her Codex invokes `scripts/setup` in an interactive terminal. The script:

1. Verifies macOS, `python3`, and Python 3.11 through 3.14.
2. Creates the private runtime data directory and virtual environment.
3. Installs the plugin's declared Python dependencies.
4. Requests `API ID` and `API Hash` through terminal input. The hash is entered
   without echo and neither value is supplied as a command-line argument.
5. Atomically writes `telegram.env` with mode `600`.
6. Runs the Telethon authorization flow for phone, one-time code, and optional
   2FA password.
7. Tightens the resulting session permissions.
8. Runs the safe status command and succeeds only when `authorized` is true.

The setup is idempotent. It reuses an already authorized session and does not
replace an existing credential file unless the user explicitly selects a
reconfiguration path. A failed authentication can be retried without
reinstalling the plugin.

## MCP tool surface

The plugin exposes these read-only tools:

- `status`
- `auth_info`
- `list_dialogs`
- `read_messages`
- `download_media`

It exposes these paired write tools:

- `prepare_send_message` and `send_message`
- `prepare_send_photo` and `send_photo`

Read results return only bounded, structured dialog/message fields. Status
reports whether credentials and a session are configured but never returns
credential values.

## Write safety model

Every send is a server-enforced two-phase operation:

1. A prepare tool resolves the recipient and validates the complete immutable
   payload.
2. It returns an account/recipient/payload summary plus a random action ID and
   exact confirmation value.
3. Codex displays that summary and waits for explicit user confirmation.
4. Only then may Codex call the corresponding send tool with the prepared
   action ID and exact confirmation.

Prepared actions expire after five minutes, are single-use, and are scoped to
their action type. A prepared photo records its content hash and is rejected if
the file changes before sending. Telegram messages, media, dialog names, and
other fetched content are always untrusted external content and cannot become
instructions to Codex.

## Configuration and portability changes

The existing local implementation is the behavioral reference, but its
machine-specific constants are not copied unchanged. The packaged version:

- resolves its runtime root from `CODEX_HOME` or `$HOME/.codex`;
- accepts an explicit environment-file path for scripts and tests;
- derives plugin paths from the launcher location;
- uses generic identities and paths in fixtures;
- removes source-machine caches, virtual environments, downloads, sessions,
  and environment files;
- retains bounded limits for dialog/message reads and media uploads.

## Error handling

- Missing credentials: `status` remains safe and reports an unauthorized
  configuration; operational tools provide setup guidance.
- Missing Python or unsupported version: setup stops before changing Codex or
  Telegram state and prints the required remediation.
- Failed or cancelled Telegram authentication: setup keeps no partial session
  as proof of success and can be rerun.
- Existing runtime data: setup preserves it by default and requires an explicit
  reconfigure option before credentials are replaced.
- Missing MCP tools after install: documentation checks plugin installation,
  restarts Codex, opens a new task, and then checks status; it does not fall
  back to an obsolete Bot API helper.
- Expired/wrong confirmation, modified photo, empty payload, unsupported media,
  or oversized media: the server refuses the send before contacting Telegram.

## Verification

Automated verification includes:

1. Unit tests for configuration, safe formatting, entity resolution, bounded
   reads, status redaction, preparation expiry/single use, exact confirmation,
   and photo validation.
2. Plugin manifest validation with the bundled Codex plugin validator.
3. Marketplace JSON/schema and path checks.
4. A package-safety check that fails on tracked secret/session/cache/download
   artifacts, source-machine home paths, source account usernames or numeric
   identifiers, and nonblank example credentials.
5. A temporary-runtime smoke test that creates a clean virtual environment,
   imports the server, and confirms the expected MCP tool names without real
   Telegram credentials.
6. CI for Python 3.11 through 3.14 on clean runners.

Live acceptance on the target Mac includes:

1. Marketplace and plugin installation through Codex CLI.
2. Successful private account setup and `authorized: true` status.
3. Listing dialogs and reading messages from a user-selected dialog.
4. Preparing, but not automatically sending, a harmless test message.
5. Confirming that the exact send cannot happen without the user's explicit
   second-step approval.

No live message is required to validate repository release readiness.

## Documentation

The root README documents marketplace installation, available plugins, update
commands, and removal. The plugin README documents prerequisites, privacy
boundaries, manual recovery, and tool behavior. The bundled skill contains the
agent-facing workflow so the user can ask her Codex to complete setup rather
than manually reproducing implementation steps.

## Release and update behavior

The initial plugin version is `0.1.0`. Manifest versions and the marketplace
entry are updated intentionally for releases. Marketplace consumers refresh
the Git snapshot and reinstall or update the plugin through Codex's plugin
workflow. Runtime account data stays in the stable external data directory.

## Acceptance criteria

- `contixly/codex-marketplace` is a valid public Codex marketplace containing
  `telegram-personal`.
- A clean macOS Codex installation can add the marketplace and plugin using the
  documented commands.
- The bundled setup flow can authorize a Telegram user account using credentials
  created by that user.
- The expected MCP tools load in a fresh Codex task.
- Read tools work without exposing secrets.
- Write tools enforce prepare, visible confirmation, expiry, and one-time use.
- Repository and release checks find no source-account secrets or personal
  runtime data.
- Reinstalling/updating the plugin does not remove the authorized session.
