# P2 Drive ZIP round-trip probe — 2026-11-09

## Status

**Local SQLite+ZIP read/write and Drive connector upload/replace/readback: PASS with synthetic data. Concurrent-write safety: NOT PROVEN / NO-GO.** The original user-uploaded empty DB was not modified. P1-A1 real-data ingestion remains NO-GO.

## Data locations

- Original user-provided empty DB (unmodified): Google Drive file ID `1Y2bmSE21C97KazpQsP40c5g05Ja4ClSA`, `master_duel.sqlite.zip`. SHA-256 ZIP `b99a36a5484b569ea5b386a20c8c4d37b0a882f631a1a6e88bbc96f9a6cdb998`, 1,917 bytes, SQLite 114,688 bytes, schema version 1, 12 tables, no cards.
- Separate **synthetic test** file: Drive file ID `12CxOfFc9irGx2unZAtLPn2gAufntTz6m`, `master_duel_P2_SYNTHETIC_TEST.sqlite.zip`. After in-place update: ZIP SHA-256 `ea22aaf51fb0518642c8fba889206e3ca7f2cc67b34d10a9cb8d2c64cc5cae80`, 2,565 bytes.
- Backup before update: Drive file ID `1NsF8hQ14qAAMlMaiZXjECdD1UnJxth5u`, `master_duel_P2_TEST_BACKUP_before_update.sqlite.zip`, SHA-256 `ee7c0a04acdad49f43c02c5d8df032ec3cf9a5ecc07b37f686d6883f5affc3f2`, 2,378 bytes.
- All reside in the existing Drive parent folder `1QdnvkJ7dNR4Z-HIMuOZenDPm0aStYzfQ`. These IDs are observation identifiers, not permanent path assumptions.
- Source code revision: GitHub main at `23e1e583ecb655a405eb32d0c74f1fa8231df81d`; the P1 SQLite schema v1 is the baseline.

## Directly observed operations

1. Drive connector `get_file_metadata` and `fetch(download_raw_file=true, include_base64=false)` on the original. ZIP contains exactly `master_duel.sqlite`; ZIP CRC, SQLite `integrity_check`, `foreign_key_check`, schema version all PASS.
2. **Copy-only** local test: add synthetic card 001, SR, set owned_count=2 in an audit batch, undo to UNKNOWN; store inventory history. ZIP and re-open checks PASS.
3. Drive connector `upload_file` created the separate test ZIP; raw download returned exactly the original test file's SHA-256 `ee7c...`.
4. Drive connector `upload_file` created backup of test file before updating.
5. Modified local copy of test SQLite: add synthetic card 002 (R), owned_count=1, audit batch; integrity/foreign keys PASS. Drive `update_file(file_uri=...)` replaced **test ID only**, retaining same file ID.
6. Drive connector fetched updated test and backup. Both SHA-256 matched their corresponding pre-upload bytes. Updated test shows 2 synthetic cards; inventory 001 UNKNOWN, inventory 002 KNOWN_POSITIVE 1; total 3 audit history rows, `integrity_check=ok`, no foreign key violations. Backup remained old state (1 card, 2 history rows).
7. Original Drive file metadata again showed unchanged size and original `modified_time=2026-11-09T13:27:51.338Z`. The user-provided original was **not** overwritten.

## Remaining hard limit: concurrent update and CAS

The connector `update_file` exposed for this environment **does not accept an `If-Match` / generation precondition / expected revision token**. Merely re-reading `modifiedTime`, file ID or SHA just before calling it has a race window. Therefore **never claim compare-and-swap, lock safety, or multi-thread automatic CRUD conflict prevention based on this test**.

Until an atomic conditional update/lock or equivalent conflict-safe single-writer workflow is developed, **do not permit unsupervised concurrent writes to the same file**. Practical interim policy:
- Single designated writing work session at a time; other voice threads produce staged structured updates, not direct concurrent Drive modifications.
- Read latest Drive DB, validate SHA/schema, maintain a verified immutable backup, write to a **new snapshot file**, verify independent readback; promote/switch the canonical reference only under controlled single-writer procedure. Existing-file replacement was tested on a disposable test file, **not** approved for unattended updates to the user's authoritative DB.
- If another writer, changed metadata or mismatch is detected, abort and reconcile; even if no mismatch is seen, absence of atomic precondition means race safety is not guaranteed.
- On partial failures, retain original and backup, report state accurately. Do not delete originals/backup without explicit instruction.
- Drive compression sizes here come from nearly empty synthetic DBs and do not predict actual full-catalog ZIP size.

## Next engineering acceptance

Design and test the actual portable P2 `download -> safe ZIP extraction -> SQLite backup API -> CRUD via P1 Store -> integrity -> ZIP -> upload -> independent readback` orchestrator, with replay idempotency, clear error states, and a **documented single-writer policy** or verified conditional-write capability. Prefer tests against a fake Drive adapter before real-data use. Do not put personal inventory or third-party card text in public Git.
