# GPT External I/O Bridge

## Publishing GPT changes to GitHub

For text/source changes, use the repository-level `[gpt-git-update]` Issue protocol in `.gpt/GIT_UPDATE_ISSUE.md` whenever direct push authentication is unavailable. Build the unified diff from latest `main`; the Action validates, commits and pushes it. Do not push an old local commit. Use `[gpt-git-binary-update]` for binary files.

`python tools/gpt_io/gpt_io.py git read|update ...` is the unified entry point. The original `.gpt/tools/gpt_git_binary_tool.py` remains supported unchanged during migration.

Drive v0.1 implements request validation only until a Service Account and an explicitly shared automation root are configured. Upload never overwrites; move, replace, and trash require a file ID; replace also requires `expected.file_id`.
