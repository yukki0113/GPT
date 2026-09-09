# PWA deploy trigger note

`gpt_git_update_issue.yml` pushes to `main` with the workflow `GITHUB_TOKEN`.
GitHub suppresses recursive workflow runs for pushes made by that token, so a successful
`[gpt-git-update]` touching `horse-racing/jrdb/pwa/**` does not by itself start
`JRDB PWA Pages` even though the Pages workflow listens to `push`.

After Issue-driven PWA code changes, trigger `JRDB PWA Pages` with `workflow_dispatch` or a user-token push.

2026-09-09: direct user-token refresh issued after Newspaper shell v24 update.
2026-09-09: direct user-token refresh issued after Newspaper trouble flag shell v25 update.
