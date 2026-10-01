# Direct-Drive Actions workflows — legacy reference

Status: **DISCONTINUED FOR OPERATION / NON-RUNNABLE REFERENCE**

These workflow files were moved out of `.github/workflows/` on 2026-10-01 after the repository-wide Drive transport audit. Each contained one or more obsolete Actions-side Drive transport dependencies such as `gdown`, direct `drive.google.com` access, Google Drive API authentication, or `GPT_GDRIVE_*` secrets.

They are retained here only to preserve implementation history and project-specific logic while preventing GitHub Actions from discovering or executing them.

Current production route:

```text
Drive
-> GPT connected native Google Drive connector
-> GPT runtime
-> canonical GitHub module
-> local deterministic execution
-> optional native Drive connector write-back
```

Do not move these files back into `.github/workflows/` or re-enable their Drive transport. If a project still needs the computation, preserve the business logic but redesign the transport according to `.gpt/GITHUB_OPERATION_POLICY.md` and `tools/gpt_io/DRIVE_ROUTING_DECISION_v0_1.md`.

The repository-wide audit covered all workflow files present under `.github/workflows/` at the time of migration.
