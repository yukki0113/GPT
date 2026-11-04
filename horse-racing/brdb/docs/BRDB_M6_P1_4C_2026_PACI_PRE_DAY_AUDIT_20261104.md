# BRDB M6 P1-4c — 2026 daily PACI pre-day Drive evidence inventory (2026-11-04)

## Decision

**PASS — research-only storage-provenance candidate inventory (14 daily archives / 4,945 KYI declarations).**
**HOLD — pre-race predictive validation, historical 2016–2025 as-of cohort, and BRDB CURRENT / Blood Score promotion.**

This report documents a newly located 2026 source class and deliberately does not re-label the P0-2/P1-3 annual selected-pedigree static mart as historically as-of-safe.

## Location and historical discovery outcome

The native Google Drive connector located the established JRDB Raw `00_raw/PACI` folder by listing the known `00_raw` parent (`1bKflbSiIyzrU7IcBSp4xrExRi_X5daUL`) and then listing its PACI subfolder (ID `1zFajenPU5jxInZCcmqZzkgiaYil3MD8r`).

- Direct listing returned **93** daily PACI ZIP files, all named `PACI26YYMMDD` for the 2026 calendar year (standard `PACIyymmdd.zip` convention, e.g. `PACI261101.zip`).
- No 2016–2025 daily PACI ZIP was found **within this canonical folder**. This is a scoped inventory finding, **not proof of nonexistence elsewhere**.
- The sibling UKC folder holds year-level UKC archives already audited in P1-4b. The sibling SED folder holds 2026 daily archives plus historical year-level SED ZIPs. Neither is evidence of historical PACI delivery timing.
- Google Drive keyword searches alone returned misses for `PACI160105.zip`, `PACI170105.zip`, `PACI250105.zip`; those searches are not used as evidence of absence.

## Independent provider metadata gates for 2026 daily PACI

For the **17** PACI ZIPs dated 2026-09-19 or later, native Drive `files.get` provider metadata was independently read (created and modified timestamps), and revision history was checked for the 14 accepted dates. A ZIP is a conservative **Drive pre-calendar-day stored candidate** only when BOTH `created_time` AND `modified_time` are earlier than 00:00 JST on the nominal race date, and exactly one revision is currently listed.

- **14 ZIPs PASS** this strict storage-date gate: 2026-09-19, 09-20, 09-26, 09-27, 10-03, 10-04, 10-10, 10-11, 10-12, 10-17, 10-18, 10-24, 10-31, 11-01.
- `PACI260921.zip` and `PACI260922.zip` are **WITHHELD**, because both were uploaded on 2026-09-22, after the relevant calendar-day cutoff.
- `PACI261025.zip` is **WITHHELD**, because its last modification was on 2026-10-25 JST, even though originally uploaded on 2026-10-23.
- Drive listed exactly **one revision** for each of the accepted 14 ZIPs, with revision modification time matching file metadata. This supports the provider storage-history assessment but is not a signed contemporaneous source snapshot or JRDB distribution receipt.

## Private actual archive verification

The accepted 14 original ZIPs were downloaded **only into the private ChatGPT runtime** via the native connected Drive connector. The original ZIP bytes and row-level JRDB records were **not sent to GitHub**.

| Check | Observed result |
|---|---:|
| Accepted PACI ZIPs | 14 |
| All ZIPs pass CRC | 14 / 14 |
| ZIP files with 14 members each | 14 / 14 |
| Date-matched UKC and KYI present | 14 / 14 |
| UKC observation records | 4,945 |
| KYI declared entrants | 4,945 |
| UKC vs KYI canonical blood-registration-number equality **in record order** | 4,945 / 4,945 |
| UKC profile data_date equal to target day | 4,945 / 4,945 |
| UKC future profile data_date | 0 |
| Current audit SHA-256 of ZIP and both UKC/KYI members | 14 / 14 |
| Historically pre-race JRDB distribution log | **NOT VERIFIED** |
| Confirmed actual starters | **NOT ESTABLISHED** |

Parser identities follow existing canonical JRDB `jrdb_raw.raw_field(..., 11, 8)` for KYI and `jrdb_ukc.parse_ukc_record` for UKC. No new JRDB fixed-width parser is introduced.

The local private source SHA manifest and row-level extracts must remain outside this public repository; public records contain aggregate counts, safe dates, and audit code only. The aggregate JSON (without horse names or horse IDs) has SHA-256 `e486532938b4366a58e28282de073b253cb305938298aeb755cd21ef76c2e4f0`.

## Evidence grades and restrictions

1. **Drive storage availability before calendar day (provider metadata):** supported for 14 files. A present ZIP SHA was computed at audit time. The study did **not** recover an independent pre-race log that cryptographically signed those same ZIP bytes.
2. **JRDB official provider distribution timestamp:** not independently verified. ZIP embedded timestamps and target-day UKC `data_date` do not establish release time.
3. **UKC/KYI canonical identity membership in the present archived ZIP:** 4,945/4,945 confirmed; these are KYI **declared entrants**, not necessarily actual starters.
4. **2016–2025 static pedigree as-of status:** unchanged, `STATIC_LATER_SELECTED_SNAPSHOT_NOT_ASOF_VERIFIED`. **0** historical P0-2 entries become predictive-safe.
5. **2026 candidate evaluation:** may be developed as a separately scoped, SHA-pinned, day-cutoff-conservative experiment, but **not** combined with the 2016–2025 multi-year holdout as an already validated predictive feature.
6. **P1-5/P1-6/P1-7 predictive status:** remains HOLD pending a frozen appropriately dated cohort, independently verified member/feature availability and sufficient test-period support; no scoring, ranking or publication.

The committed `src/audit_brdb_paci_pre_day_inventory.py` is a deterministic private-file validator. A caller-supplied manifest has **no authority by itself** to attest Drive timestamps; the connected provider's metadata must be fetched independently and frozen. The script deliberately emits `prediction_safe=false` and `pre_race_release_time_proven=false`.

## Reproduction (private runtime)

```bash
python horse-racing/brdb/src/audit_brdb_paci_pre_day_inventory.py \
  --archive-root <PRIVATE_14_ZIP_DIRECTORY> \
  --private-manifest <PRIVATE_PROVIDER_METADATA_AND_SHA_MANIFEST.json> \
  --out <PRIVATE_AGGREGATE_OUTPUT_DIR>

python -m unittest discover -s horse-racing/brdb/tests \
  -p 'test_audit_brdb_paci_pre_day_inventory.py' -v
```

No BRDB CURRENT, frozen Review v0.1, RaceNote, PWA, publishing pipeline, source archives, nor predictive logic was changed.
