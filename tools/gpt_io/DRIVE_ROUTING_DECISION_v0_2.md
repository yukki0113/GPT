# Drive routing decision v0.2 — scoped public read-only exception

Date: 2026-10-09. Supersedes v0.1 **only** for explicitly public, unauthenticated,
manifest-pinned file downloads. v0.1 is retained as historical rationale.

## Decision

* Private/authenticated Drive read, Drive writes and administration: ChatGPT/Work
  connected native Drive connector remains the standard. GitHub Actions must not
  authenticate to Drive or mutate Drive content/permissions.
* A repository-reviewed manifest may pin **already public** Drive file IDs with
  expected filename and mandatory SHA-256. GitHub Actions and deterministic
  Python runtimes may download **only** via `tools/gpt_io/public_drive/fetch.py`
  using unauthenticated `gdown`.
* Direct `gdown` invocations or ad-hoc `drive.google.com` URLs inside workflows
  are **not** an accepted standard. Existing unauthorized direct calls must be
  migrated explicitly; the exception does not retroactively approve them.
* Drive folder enumeration, unpinned assets, write/upload, OAuth, refresh tokens,
  service-account JSON, browser sessions and cookie injection are outside scope.
* A/B/C/D execution classification remains independent of transport.

## Acceptance contract

Manifest lives with each consumer/project, not in repository-wide policy.
Required: `schema_version=1`, `transport=public_google_drive` and nonempty
`artifacts`, each with unique `artifact_id`, Drive `file_id`, relative
`destination`, matching `expected_name`, and 64-hex `sha256`.
Optional positive `expected_size`. Download to local temporary file,
validate size/hash, atomic local promotion; reject mismatched existing files,
path traversal, and symlink destinations. Fail closed on unavailable, private,
quota-blocked, or changed objects. Produce local provenance receipt.
No local receipt constitutes permission to publish the underlying data.

Keep original Drive source of truth and accepted immutable generation contracts;
the helper is only transport, never a resolver or data interpreter.
`tools/gpt_io/gdrive/` and the old Actions Drive bridge remain discontinued.
Native Google Docs/Sheets/Slides operations remain connected-tool-only.

## Rollout

1. Common helper + offline tests + policy adjustment on isolated branch.
2. RaceNote golden-day manifest and migration of PR #1908's workflow, with
   live unauthenticated public fetch and identical semantic validation.
3. Audit results and promote to main after successful verification.

Security caveat: gdown/public Drive can be throttled or have size restrictions.
No retry may fall back to authenticated/private access or another unreviewed URL.
