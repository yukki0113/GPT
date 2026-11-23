# Phase 3 — Shared runtime dependency monitoring and controlled promotion

Established: 2026-11-23. Scope: shared tooling `GPT/tools/runtime_wheels`, starting with the currently approved JRDB runtime. This is **not** a JRDB-only dependency policy.

## Production baseline

The source of truth for the actual ChatGPT offline-runtime versions, Drive file ID, package SHAs and archive SHA is `tools/data-storage/config/chatgpt_offline_runtime_v1.json`; the shared Data Storage supported dependency range/pin is `tools/data-storage/requirements.txt` plus `pyproject.toml` and `data_storage/dependencies.py`.

At setup, DuckDB `2.0.1`, PyArrow `25.0.1`, NumPy `2.2.4` are approved **as a tested combination**, not as independent automatic upgrades. The original offline bundle remains private at `GPT/tools/runtime_wheels`. Do not modify or overwrite it when testing candidate combinations.

## Scheduled monitoring

- `.github/workflows/shared_runtime_dependency_watch.yml` checks **once weekly Monday 09:35 Asia/Tokyo** and may be triggered manually. Monitoring is a lightweight Actions-native control-plane task; **normal Forecast Reader analysis remains local in ChatGPT with no Actions launch**.
- `tools/data-storage/scripts/check_runtime_dependency_updates.py` uses official PyPI JSON release data (stable, not yanked, published binary wheel available). It compares with exact approved offline-runtime baseline from GitHub. It intentionally does **not** install a package or edit any registry.
- A CPython 3.13 Linux x86_64 wheel filename hint is only an indicative preflight. Full supported tag, glibc minimum, NumPy ABI, `Requires-Python`, provenance and cryptographic checks are required separately.
- When a newer version appears, create one distinct `[DEPENDENCY_WATCH]` review Issue per package and version. Check existing open Issues first. No notification when there is no change; failure of PyPI retrieval/response should fail the workflow and must not be interpreted as `NO_UPDATES`.
- Upload a timestamped JSON review receipt to the Actions run for 90 days. Each Issue includes the approved baseline, candidate, source link and approval gates.
- DuckDB LTS support cannot safely be deduced from version numbers or from PyPI. A reviewer checks the [official DuckDB release calendar](https://duckdb.org/release_calendar), release notes and support window.
- Official PyPI JSON API description: https://docs.pypi.org/api/json/ .

## Mandatory promotion decision gate

An Issue is a review request, **not** authorization to upgrade. Candidate remains isolated from `main` and the approved Drive wheel.

| Gate | Requirement |
| --- | --- |
| Eligibility | Stable non-yanked; security notice and upstream release notes inspected; DuckDB support/LTS explicitly assessed. |
| Compatibility | Supported Python, Linux CPU/ABI/glibc tags; user-space offline bootstrap; dependencies and any breaking SQL/API differences. |
| Shared tests | `check-deps`, Data Storage tests and JRDB Common Reader / Forecast Reader tests in isolated environments; checks on Python 3.12/3.13 as applicable. |
| Real data | Fixed immutable PACI/Analysis/Warehouse input with SHA, no future leakage. Compare same Reader source and source bytes old vs candidate DuckDB. |
| Scientific parity | Exact S0–S4 selected race keys, 8-axis numerators/denominators/missing, previous-run joins, target as-of guard and Evidence Bundle hashes. Investigate every difference rather than loosening contract. |
| Performance | Run repeated warmed tests, record wall time, peak memory and storage I/O. A claimed speedup without measurement is not an approval argument. |
| Packaging | Official wheel hashes and isolated installer negative tests, new *private* Drive artifact; never overwrite the previous bundle. |
| Rollback | Previous pinned requirements and immutable Drive artifact retained; include both SHA and main commit in promotion decision. |
| Approval | **User review/approval is required before production pin and registry promotion**. Report PASS/PARTIAL/BLOCKED explicitly; no automatic merge. |
| Post-merge | Confirm production `main`, `check-deps`, Forecast Reader CI and Drive file readback. |

The current Forecast Reader 8/10 case can produce `PARTIAL` under both DuckDB 1.1.3 and 2.0.1 (Issue #2714). Do not rewrite that pre-existing acceptance status as part of a dependency promotion.

## Release choreography

1. Detection creates `[DEPENDENCY_WATCH]` Issue with candidate evidence, no binaries or repo changes.
2. In a review branch, pin the **candidate** exact dependencies for testing; do not change current main. Run isolated unit/smoke and fixed real-data acceptance tests.
3. Prepare a proposed promotion PR with results, verified wheel hashes, new private Drive file ID, explicit rollback and owner signoff request. Draft only until approval.
4. After approval, merge atomic consistency changes to `requirements.txt`, `pyproject.toml`, `data_storage/dependencies.py`, wheel exporter / offline bootstrap expected versions, runtime registry, and runbooks. Avoid mixed old/new binaries.
5. Retain the prior Drive bundle for rollback, perform after-merge readback and close the corresponding review Issue with evidence.

**No autonomous or unattended production upgrade.** Do not let Dependabot, an Actions schedule, or the monitoring script alter production pins or wheel blobs. No JRDB-licensed data in GitHub logs, Issues, artifacts or a public repository.

## Boundaries and future refinements

- The first monitor covers three packages constituting the verified offline runtime. Other Data Storage dependencies (PyYAML, gdown, cryptography) remain pinned/ranged as before; expand only after identifying their runtime vs ingestion responsibilities.
- New thread / non-CPython 3.13 / non-Linux x86_64 validation is still a separate acceptance requirement.
- If the monitoring workflow itself cannot access official PyPI, the run fails and operators investigate; do not silently mark everything up-to-date.
- Security-critical upstream advisories require expedited human review; weekly stable-version discovery alone is **not** continuous vulnerability monitoring or a CVE database.
