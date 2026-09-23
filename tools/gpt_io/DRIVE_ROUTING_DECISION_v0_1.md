# Drive routing decision v0.1

## Background

External I/O Bridge 001--003 introduced a common package, Git bridge compatibility, and a Google Drive API adapter with no-overwrite, file-ID, CAS, root-boundary, checksum, and validation safeguards. Unit and Git regression tests passed, but real Drive acceptance was not run.

## Decision

For v0.1, ChatGPT/Work uses the connected native Google Drive connector as the production-standard route for Drive files. Google Docs, Sheets, and Slides use their native tools. GitHub-tracked content continues to use the Git Issue/Actions bridge or direct authenticated Git operations.

The Actions Drive backend in `gdrive/` is **DISCONTINUED FOR OPERATION**, **NOT PRODUCTION-ACCEPTED**, and **NOT THE STANDARD ROUTE**. Do not enable its Issue workflow and do not configure a Google service-account Secret.

## Rationale and security

The initial Actions design requires a long-lived Service Account JSON key. The current Google Cloud organization policy prevents key creation, and v0.1 does not weaken that policy. Therefore `GPT_GDRIVE_SERVICE_ACCOUNT_JSON` is not a normal operating requirement. Secrets and credential material must never be placed in source, Issues, logs, artifacts, or reports.

Native connector use still requires exact file or folder identity for destructive actions, metadata confirmation before replace/move/delete, no filename-only destructive targeting, and provenance appropriate to the data: file ID, name, parent, size, modified time, hash where available, and source/destination.

## Folder-reference fallback

Drive folder URLs are a convenience input, not evidence of access.  Some native-connector list actions can fail while binding a valid URL before a request reaches Drive (for example, `InvalidActionArgumentsError` or an invalid-URL validation response).  Treat that as a connector input-path failure, **not** as a permission, authentication, or empty-folder result.

For a supplied folder URL, use this read-only resolution sequence before reporting an access problem:

1. Extract the folder ID from `/folders/<ID>`.
2. Resolve the ID with Drive file metadata and confirm that it is a folder.
3. Enumerate direct children with the parent query `'<ID>' in parents and trashed = false`.

Only a Drive response from the metadata or parent-query route may establish that an asset is missing or inaccessible.  Do not request Drive reconnection or reauthentication solely because URL-based folder listing failed.  Record the resolved folder ID and the actual Drive response in an audit/report so later operators can distinguish connector routing failures from repository state.

## Source-of-truth boundary

The connector does not decide whether GitHub, Drive, or a Google native file is authoritative. Each project's README, CONTEXT, or WORKFLOW defines that contract. Project resolvers resolve logical artifacts; the connector transports files; the deferred backend remains a possible unattended producer/admin transport.

## Future reopening

No reopening is planned. Any future reconsideration requires an explicit new decision; do not create or store long-lived Google service-account keys for this repository.

## Compatibility

No Drive adapter, test asset, or Issue protocol is removed. The backend remains available as a base for a future WIF-enabled implementation.
