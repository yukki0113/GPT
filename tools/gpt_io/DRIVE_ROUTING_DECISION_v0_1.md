# Drive routing decision v0.1

## Background

External I/O Bridge 001--003 introduced a common package, Git bridge compatibility, and a Google Drive API adapter with no-overwrite, file-ID, CAS, root-boundary, checksum, and validation safeguards. Unit and Git regression tests passed, but real Drive acceptance was not run.

## Decision

For v0.1, ChatGPT/Work uses the connected native Google Drive connector as the production-standard route for Drive files. Google Docs, Sheets, and Slides use their native tools. GitHub-tracked content continues to use the Git Issue/Actions bridge or direct authenticated Git operations.

The Actions Drive backend in `gdrive/` is retained but is **DEFERRED**, **NOT PRODUCTION-ACCEPTED**, and **NOT THE STANDARD ROUTE**. Its Issue workflow is disabled by default; it runs only when repository variable `GPT_GDRIVE_ACTIONS_BRIDGE_ENABLED` is exactly `true`.

## Rationale and security

The initial Actions design requires a long-lived Service Account JSON key. The current Google Cloud organization policy prevents key creation, and v0.1 does not weaken that policy. Therefore `GPT_GDRIVE_SERVICE_ACCOUNT_JSON` is not a normal operating requirement. Secrets and credential material must never be placed in source, Issues, logs, artifacts, or reports.

Native connector use still requires exact file or folder identity for destructive actions, metadata confirmation before replace/move/delete, no filename-only destructive targeting, and provenance appropriate to the data: file ID, name, parent, size, modified time, hash where available, and source/destination.

## Source-of-truth boundary

The connector does not decide whether GitHub, Drive, or a Google native file is authoritative. Each project's README, CONTEXT, or WORKFLOW defines that contract. Project resolvers resolve logical artifacts; the connector transports files; the deferred backend remains a possible unattended producer/admin transport.

## Future reopening

Reopen Actions-to-Drive work only for a concrete unattended or high-volume need. Prefer GitHub Actions OIDC, Google Workload Identity Federation, and short-lived Service Account impersonation. Do not make long-lived JSON keys the default.

## Compatibility

No Drive adapter, test asset, or Issue protocol is removed. The backend remains available as a base for a future WIF-enabled implementation.
