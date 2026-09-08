# GPT External I/O Bridge

## v0.1 routing status

- **Git backend:** PRODUCTION / STANDARD.
- **Google Drive native connector route:** PRODUCTION / STANDARD FOR CHATGPT-WORK.
- **Google Drive Actions backend:** DEFERRED / NOT REAL-DRIVE E2E ACCEPTED.

Use connected native Google Drive tools for normal Drive operations. Google Docs, Sheets and Slides must use their native tools. The Actions backend remains in the repository as a future unattended-automation foundation; it is disabled unless repository variable `GPT_GDRIVE_ACTIONS_BRIDGE_ENABLED` is exactly `true`.

`GPT_GDRIVE_SERVICE_ACCOUNT_JSON` is not a standard setup requirement. The current JSON-key implementation is deferred because the environment's key-creation policy does not permit adopting long-lived Service Account keys. If unattended Actions-to-Drive automation becomes necessary, reopen the backend with GitHub Actions OIDC, Google Workload Identity Federation, and short-lived Service Account impersonation credentials.

See `tools/gpt_io/DRIVE_ROUTING_DECISION_v0_1.md` for the architecture decision and safety contract.

## Publishing GPT changes to GitHub

For text/source changes, use the repository-level `[gpt-git-update]` Issue protocol in `.gpt/GIT_UPDATE_ISSUE.md` whenever direct push authentication is unavailable. Build the unified diff from latest `main`; the Action validates, commits and pushes it. Do not push an old local commit. Use `[gpt-git-binary-update]` for binary files.

`python tools/gpt_io/gpt_io.py git read|update ...` is the unified binary entry point. The original `.gpt/tools/gpt_git_binary_tool.py` remains supported unchanged during migration.

Before GPT / Work creates an Issue-driven Actions request, follow `.gpt/ISSUE_REQUEST_CONTRACTS.md`. The shared validator is:

```bash
python .gpt/tools/gpt_issue_preflight.py \
  --title "[gpt-git-update] update docs" \
  --body-file /tmp/issue-body.md \
  --repo-root .
```

The implementation lives at `tools/gpt_io/git/issue_preflight.py`. It validates the three common GPT-Git Issue protocols and supports project-specific simple key/value contracts with repeated `--required-key` options. In `[gpt-git-update]` mode, `--repo-root` enables `git apply --check` so malformed or stale patches can be rejected before an Actions run is created.

The deferred Actions implementation retains request validation. Upload never overwrites; move, replace, and trash require a file ID; replace also requires `expected.file_id`.

## Google Drive backend

The bridge transfers stored bytes (SQLite, ZIP, CSV, XLSX, JSON and similar files). It does not edit Google Docs, Sheets or Slides, and never decides whether Git or Drive is the source of truth.

Authentication uses `GPT_GDRIVE_SERVICE_ACCOUNT_JSON`; writes are limited to descendants of `GPT_GDRIVE_AUTOMATION_ROOT_ID`. Share only the dedicated automation root with the Service Account. Secrets must remain in GitHub Actions secrets and must not be placed in source, Issues, logs, artifacts, or reports.

The automation root itself is an allowed destination; no operation may cross above or outside it.

Upload is no-overwrite. `move`, `replace`, and `trash` require an exact file ID. Replace also requires matching `expected.file_id` and optionally checks expected size and modified time. `verify: true` re-downloads uploaded/replaced bytes and compares size and SHA-256 before success.

Optional `format_validation` accepts `zip` (CRC) or `xlsx` (ZIP CRC plus workbook structure).

Use a JSON request file:

```bash
python tools/gpt_io/gpt_io.py gdrive upload --request request.json
python tools/gpt_io/gpt_io.py gdrive download --request request.json
```

`[gpt-gdrive-request]` is for the deferred Actions backend only, not the standard GPT/Work route. Large source bytes use a short-lived Actions artifact referenced by `source_artifact_run_id` and `source_artifact_name`; do not place large Base64 in an Issue and do not commit Drive data to Git.
