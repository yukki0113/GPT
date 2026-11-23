# JRDB Phase 2 — ChatGPT-side DuckDB/Parquet execution (2026-11-23)

## Scope and decisions

- **Central horse-racing first**: preserve canonical `tools/data-storage`, Forecast Reader S0–S4 sampling, eight axes, PACI ability/condition comparison, and prior-year as-of guards.
- SQL runs locally in the ChatGPT-side Python sandbox. **No GitHub Actions run is needed per forecast**.
- Build-time package staging used official PyPI wheels through a one-time GitHub Actions CI. The final, read-only **runtime package is stored on private Google Drive**, not on expiring Actions artifacts. This is an important distinction: *daily execution independent of Actions*, not a promise that an upgradable package supply chain never needs CI.
- **Never upload any JRDB proprietary raw file/Parquet into GitHub**, and never make Drive objects public for convenience.
- Python 3.13 Linux x86-64 only for this first portable package. Python 3.12, Windows/macOS, ARM, memory-limited devices, and future ChatGPT runtime changes require their own wheels and validation. Do not claim this installation is persistent between chat sessions.

## Canonical artifact registry

`tools/data-storage/config/chatgpt_offline_runtime_v1.json`

This registry pins the exact private Drive file ID, archive **SHA-256**, inner package manifest, and independently checked wheel SHAs. The storage folder is `horse-racing/runtime_wheels` in Drive. Only the registered file may be considered eligible for installing executable code.

## Operation: fresh ChatGPT sandbox

1. Read the GitHub `main` runtime registry, this runbook, and the canonical bootstrap script `tools/data-storage/scripts/bootstrap_chatgpt_offline_runtime.py` via connected GitHub. Do **not** substitute earlier conversation memory for live GitHub code.
2. Use the native Drive connector to fetch the registry's exact Drive file ID as a raw ZIP. Materialize the retrieved connector file in the Python runtime. Compare the full archive SHA-256 and size with the registry **before attempting to install**.
3. Verify runtime: CPython 3.13, Linux x86-64, compatible glibc. If unsupported, fail closed and use approved Actions fallback until an explicitly tested wheel is published; do not install mismatched binaries.
4. In a writable scratch directory execute:
   ```bash
   python tools/data-storage/scripts/bootstrap_chatgpt_offline_runtime.py \
     --bundle /path/to/native-drive-downloaded.zip \
     --archive-sha256 <sha256-from-current-registry> \
     --venv /path/to/new-empty-venv
   PYTHONPATH=tools/data-storage /path/to/new-empty-venv/bin/python -m data_storage check-deps
   ```
   The bootstrap validates the outer archive, optional Actions-style single-member wrapper, all official wheel payload SHAs, exact pinned versions, and isolated import/SQL smoke. `pip` is invoked with `--no-index --no-deps`. An already occupied target is **never overwritten**.
5. Use native Drive connectors to retrieve PACI and manifest-bound immutable JRDB Parquet and historical-condition assets, **not** a current archive as post-hoc proof of the pre-race snapshot. Match every asset SHA/size to the correct pre-cutoff authority manifest and create an input receipt.
6. Use the **existing** canonical `Forecast Reader` and `Data Storage` source, untouched S0–S4 rules and historical inputs. Run Reader CLI and compare output audit/status against known acceptance. Continue the established fail-closed contracts and preserve Actions fallback.

The bootstrap script itself is source controlled. A new sandbox still needs the GitHub source and Drive package to be fetched through the connectors; **this is not an implicit ChatGPT runtime feature or automatic installation**.

## Acceptance evidence

Phase 1 successfully upgraded the production pin to DuckDB 2.0.1: PR #2713, main commit `50116c524ad6b435cc9aa3a18f213159ec7a0cff`.

In Phase 2 the sealed DuckDB 2.0.1 wheel was **uploaded to private Drive and downloaded back**, then installed into a *new* Python 3.13 venv via `pip --no-index --no-deps`. Direct official Data Storage SQL returned **481,627** starts / **34,548** races on the actual JRDB 2016–2025 history. The 2026-10-25 京都11R 菊花賞 Reader reproduced the four Phase 1 evidence outputs **byte-for-byte**.

The package with DuckDB+PyArrow successfully passed `data_storage check-deps` and the same four-file real-race replay in a freshly created environment. A third NumPy wheel is included in the final runtime candidate to avoid preinstalled-site-packages dependencies; see the CI logs and the latest pinned registry after final acceptance.

The canonical Reader reports technical `PARTIAL` for eight matched races under both engine versions; this **is not an installation failure**. Scientific sampling gate discrepancy from the older PASS acceptance is independently tracked by GitHub issue #2714.

## Operational limitations and rollback

- ChatGPT tool/runtime configurations vary; no single verified session proves every new chat session can access the exact same Linux Python environment and connector binaries. Future fresh-session validation remains a release acceptance item.
- The archive is restricted to the trusted registered Drive file; no execution of unpinned downloads, unreviewed user-supplied wheels, or arbitrary external scripts.
- Cross-session caching is opportunistic. Always inspect the environment and wheel version; use verified reinstall only if needed. Never silently accept DuckDB 1.1.3 after the 2.0.1 production promotion.
- The fallback remains the existing official `[DATA_STORAGE_FALLBACK]` Actions route, without changing any JRDB logic or publishing private source data.
- A future version upgrade must update both `requirements.txt` and this registry/validator contract **after** the same real-data output parity is requalified.
