# Newspaper day request v2

`[JRDB_NEWSPAPER_DAY_REQUEST]` Issue body is a JSON object. Required: `date` (YYYYMMDD), and exactly one PACI route: positive integer `raw_run_id` plus `artifact_name` equal to `jrdb-raw-YYYYMMDD`, or nonempty `paci_drive_file_id`. `revision` is an integer >=1, default 1. Unknown extra keys, including all legacy `analysis_*` keys, are ignored and not propagated to the normalized request or environment. No Analysis generation, manifest, artifact or Drive bundle is required. PACI rights/access and existing audited complete-history gates remain required.

Minimal example: `{"date":"20261102","paci_drive_file_id":"<verified PACI ID>"}`. Artifact example: `{"date":"20261102","revision":2,"raw_run_id":123,"artifact_name":"jrdb-raw-20261102"}`. Do not invent input IDs.

The production parser lives in `jrdb_newspaper_day_issue.yml`; the regression executes that exact script with both routes and legacy extras. Router/command callers must use this contract. Existing immutable request JSON files remain historical evidence; their unused Analysis fields are harmless. New outputs omit retired EdgeDB and Training Edge fields. No production Release or Pages changes occur as part of this code PR.
