# GPT External I/O Bridge

## Publishing GPT changes to GitHub

For text/source changes, use the repository-level `[gpt-git-update]` Issue protocol in `.gpt/GIT_UPDATE_ISSUE.md` whenever direct push authentication is unavailable. Build the unified diff from latest `main`; the Action validates, commits and pushes it. Do not push an old local commit. Use `[gpt-git-binary-update]` for binary files.

`python tools/gpt_io/gpt_io.py git read|update ...` is the unified entry point. The original `.gpt/tools/gpt_git_binary_tool.py` remains supported unchanged during migration.

Drive v0.1 implements request validation only until a Service Account and an explicitly shared automation root are configured. Upload never overwrites; move, replace, and trash require a file ID; replace also requires `expected.file_id`.

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

When the local environment cannot access Drive, open `[gpt-gdrive-request] <request_id>` with the request JSON. Large source bytes use a short-lived Actions artifact referenced by `source_artifact_run_id` and `source_artifact_name`; do not place large Base64 in an Issue and do not commit Drive data to Git. Artifact retention and cleanup follow the producing workflow.
