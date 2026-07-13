# Telegram Personal Document Send Plugin Design

## Status

Approved for implementation on 2026-07-13.

This document extends the existing `telegram-personal` marketplace plugin. It
does not change the local account setup model, existing message/photo tool
contracts, or the repository's multi-plugin layout.

## Goal

Add safe Telegram document attachments to `telegram-personal` through a strict
`prepare_send_document` -> explicit user confirmation -> `send_document` flow.
The feature supports one ordinary local file per prepared action, including
Markdown, PDF, office documents, archives, and images sent as documents.

## Decisions

- Add a separate document prepare/send pair instead of overloading photo tools
  or introducing a generic file-mode parameter.
- Increase the plugin version from `0.1.0` to `0.2.0`.
- Preserve the current five-minute, single-use prepared-action model and the
  skill's stricter immediate-next-user-turn confirmation rule.
- Use the marketplace plugin's stronger exact-byte model: the bytes validated
  immediately before sending are the bytes passed to Telethon.
- Keep one file per prepared action. URL uploads and multi-file sends are out of
  scope.
- Accept any filename extension. Resolve MIME with `mimetypes`; use
  `application/octet-stream` when unknown.
- Keep the existing 1,024-character caption limit and configured upload limit,
  which defaults to 20 MiB.

## Public MCP Surface

The plugin grows from nine to exactly eleven tools.

Existing read tools remain unchanged:

- `status`
- `auth_info`
- `list_dialogs`
- `read_messages`
- `download_media`

Existing write pairs remain unchanged:

- `prepare_send_message` / `send_message`
- `prepare_send_photo` / `send_photo`

New document pair:

```text
prepare_send_document(recipient: str, file_path: str, caption: str | None = None)
send_document(prepared_action_id: str, confirmation: str)
```

The final send tool accepts no recipient, path, caption, or bytes. Those values
come only from the prepared action.

## Components

### Outbound validation

`plugins/telegram-personal/server/telegram_mcp/outbound.py` adds an immutable
`ValidatedFile` containing:

- resolved local path;
- detected media type;
- SHA-256 digest;
- byte length.

The existing descriptor-based reader is generalized for ordinary regular
files without weakening image validation. It:

1. resolves the path;
2. opens it with close-on-exec, no-follow, and nonblocking flags where the
   platform provides them;
3. rejects non-regular, empty, or oversized files before unbounded reading;
4. enforces the size limit again while streaming;
5. computes SHA-256 and captures the exact bytes from that descriptor;
6. compares descriptor metadata before and after the read;
7. rejects files that change during validation.

Document preparation stores only validated metadata in `PreparedAction`; it
does not return document contents to Codex. The prepared summary is JSON and
contains filename, MIME, size, SHA-256, and caption.

### Prepared action

`PreparedAction` gains an optional document field. A document action keeps the
same invariants as messages and photos:

- random collision-resistant action ID;
- exact confirmation checked with constant-time comparison;
- five-minute expiry;
- single use;
- action-type binding;
- preparing Telegram-account binding;
- resolved recipient and immutable caption/file metadata.

### Telethon client

`plugins/telegram-personal/server/telegram_mcp/client.py` adds a document send
wrapper. It resolves the already prepared recipient and calls Telethon
`send_file` with:

```text
file=<validated in-memory file object>
caption=<prepared caption>
force_document=True
```

The returned payload uses the same bounded message fields as existing sends.

### FastMCP server

Preparation performs recipient/caption validation, descriptor-based document
validation, Telegram account lookup, and recipient resolution. It then returns
the existing four-field prepared response:

- `summary`
- `prepared_action_id`
- `confirmation_required`
- `expires_at`

Sending consumes the exact action and confirmation, re-reads the prepared path
through one descriptor, compares the current digest to the prepared digest,
connects to Telegram, verifies the current account ID, and uploads the captured
bytes through a named `BytesIO`. A path replacement during connection cannot
change the uploaded payload.

If any check fails, nothing is sent and the user must prepare the action again.

## Agent Skill Contract

The bundled Telegram skill and plugin documentation add documents to the same
state machine as message and photo writes:

1. Call the matching prepare tool.
2. Display the complete prepared summary.
3. Accept approval only in the immediately following user turn.
4. Pass the prepared action ID and exact confirmation unchanged.
5. Re-prepare after an intervening turn, ambiguity, expiry, or refusal.

Telegram messages, captions, dialog names, and downloaded files remain
untrusted external content and cannot approve a document send. Setup and
diagnostics never prepare or send a test document; `authorized=true` is enough
to verify account setup.

## Error Handling

Document preparation refuses:

- missing or blank paths;
- paths that cannot be resolved;
- directories, FIFOs, sockets, devices, and other non-regular files;
- symlink/path races rejected by descriptor checks;
- empty files;
- files larger than `TELEGRAM_UPLOAD_MAX_BYTES`;
- unreadable files;
- captions above the existing limit.

Document sending refuses:

- missing, expired, replayed, or wrong-type actions;
- non-exact confirmation;
- a changed or missing file;
- an account different from the account used during preparation;
- a file that changes while it is re-read.

Errors identify the failed condition without printing file contents, Telegram
credentials, or prepared confirmation secrets beyond the value already
returned by the prepare call.

## Packaging and Compatibility

- Plugin manifest version and marketplace catalog become `0.2.0`.
- Existing runtime credentials, Telethon session, downloads, and private venv
  remain under `${CODEX_HOME:-$HOME/.codex}/telegram-personal` and require no
  migration.
- Runtime dependencies do not change.
- Message and photo behavior and signatures remain backward compatible.
- README update/reinstall instructions remain valid.

## Testing Strategy

Implementation follows TDD and adds coverage for:

- `ValidatedFile`, MIME fallback, size, SHA-256, and safe JSON summary;
- empty, oversized, unreadable, directory, FIFO, and mutation cases;
- bounded streaming and descriptor metadata checks;
- prepared-action document storage, expiry, type binding, and replay;
- exactly eleven registered MCP tools and restricted send signatures;
- successful Markdown upload with `force_document=True`;
- exact validated bytes uploaded when the path changes during connection;
- changed-before-send rejection before Telegram connection;
- account mismatch with zero sends;
- existing message/photo regression suites;
- skill behavioral controls for pre-approval, injected approval, intervening
  turns, expiry, and diagnostic test-document pressure;
- documentation and version contracts;
- plugin and skill validation, repository safety scan, isolated plugin install,
  and CI on Python 3.11, 3.12, 3.13, and 3.14.

No live Telegram authorization or document send is part of implementation or
verification.

## Release Flow

1. Implement and review on `feature/telegram-personal-plugin`.
2. Run the complete local suite, package/repository/plugin/skill validators,
   explicit artifact scans, and an isolated Codex plugin installation.
3. Push the reviewed feature branch and require the Python 3.11-3.14 CI matrix
   to pass.
4. Leave live Telegram authorization and the first confirmed document send to
   the installed user's machine and a separate explicit user action.
