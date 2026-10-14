# JRDB Daily Raw Acquisition Operation v0.2

Status: CURRENT  
Effective: 2026-10-14  
Supersedes: `JRDB_Daily_Raw_Acquisition_Operation_v0_1.md`

## 1. Purpose

2026 current-operation raw acquisition is split into two user-facing commands so that each JRDB family is fetched at the timing when it is actually expected to be available.

This contract covers only the routine acquisition and Google Drive publication of:

- PACI
- SED
- HJC
- SKB

It does not change historical 2010-2025 Warehouse operation, Analysis generation, RaceNote generation, or downstream settlement/research contracts.

This revision adds a formal **late-finalization SED refresh** to the pre-race operation. The ordinary post-race acquisition still captures the first available SED quickly for analysis, while the following pre-race cycle refreshes the preceding race week's SED after JRDB's later update window.

## 2. User-facing commands

The normal ChatGPT/Work requests are:

```text
mmddの開催前取得をお願いします
```

and:

```text
mmdd〜mmddの開催後取得をお願いします
```

The assistant should resolve the current year from the conversation/current operation context. If the request is unambiguous, do not ask the user to restate artifact paths or Drive folder IDs already known to the Project.

## 3. Pre-race acquisition

Request form:

```text
mmddの開催前取得をお願いします
```

### Required work

1. Resolve the target race date.
2. Check the canonical PACI Drive folder for `PACIYYMMDD.zip`.
3. If not already present and validated, fetch the target-date PACI through the authenticated JRDB acquisition route.
4. Validate the PACI ZIP:
   - ZIP readable
   - `testzip() == None`
   - expected members present
   - size recorded
   - SHA-256 recorded
5. Resolve the actual JRA race dates in the immediately preceding race week.
   - Do not assume exactly seven days earlier.
   - Include all race dates in a three-day meeting or other irregular calendar.
   - Use known PACI/Drive inventory or the project schedule source to identify actual race dates.
6. For each preceding-week race date, check the canonical SKB Drive folder first.
7. Fetch only missing `SKBYYMMDD.zip` files.
8. For **every preceding-week race date**, fetch a fresh `SEDYYMMDD.zip` from JRDB even when the canonical Drive SED already exists.
9. Validate every fetched SKB/SED ZIP and record size/SHA-256/member count.
10. For each refreshed SED, compare the newly fetched SHA-256 with the canonical Drive file's current bytes when an existing canonical object is present.
11. Publish with the native connected Google Drive connector:
   - PACI -> canonical `00_raw/PACI` folder
   - SKB -> canonical `00_raw/SKB` folder
   - SED refresh -> canonical `00_raw/SED` folder
12. SED refresh publication rules:
   - if no canonical SED exists, upload the fetched SED as the canonical object;
   - if the canonical SED exists and the fetched bytes are identical, leave the Drive object unchanged;
   - if the canonical SED exists and the fetched bytes differ, replace the raw bytes **in place** using the native Drive file update path so the same Drive file ID is preserved and Drive revision history retains the previous snapshot;
   - do not create a second same-name canonical SED object;
   - do not delete-and-reupload unless in-place replacement is unavailable. If a fallback replacement is ever required, preserve the previous bytes and provenance explicitly before replacing the canonical object.
13. Re-list the Drive target folders and verify the final canonical filename and size. For a changed SED refresh, also confirm the canonical object ID is the expected existing ID when in-place replacement was used.

### Important SKB timing rule

SKB is intentionally **not** part of the immediate post-race acquisition.

JRDB publishes SKB later than SED/HJC. Repeated same-week post-race SKB requests can therefore produce legitimate `NOT_FOUND` responses.

Operationally:

```text
race weekend N
  -> post-race:
       first available SED + HJC
       (early analysis snapshot)

before race weekend N+1
  -> PACI for N+1
  -> recover any missing SKB from race weekend N
  -> re-fetch SED for every race date in weekend N
  -> compare and refresh canonical SED if JRDB revised it
```

A missing SKB during the post-race window is not by itself an acquisition failure.

### SED late-finalization rule

SED ZIPs also contain the race-level SRB member used for detailed lap analysis. JRDB may revise the same SED backnumber after the first post-race publication, including a Monday update window.

Observed/verified late changes can include:

- optional SRB fields such as pace-up position / track bias / race comment becoming populated;
- RCA being added later;
- SED and SRB member bytes both changing.

Therefore:

- the ordinary post-race SED is an **early analysis snapshot**;
- the following pre-race SED refresh is the routine **late-finalization refresh**;
- canonical Drive `00_raw/SED` should represent the latest verified JRDB backnumber after the refresh;
- the previous canonical bytes must remain recoverable through Drive revision history when a change is applied in place.

This refresh is intentional and is not treated as an unexplained Raw overwrite.

## 4. Post-race acquisition

Request form:

```text
mmdd〜mmddの開催後取得をお願いします
```

A single date may be expressed as the same start/end date or an equivalent single-date request.

### Required work

For every requested race date:

1. Check the canonical SED and HJC Drive folders for existing files.
2. Fetch the first available:
   - `SEDYYMMDD.zip`
   - `HJCYYMMDD.zip`
3. Do **not** request SKB in this operation.
4. Validate each fetched ZIP:
   - ZIP readable
   - `testzip() == None`
   - expected family member(s) present
   - size recorded
   - SHA-256 recorded
5. Publish with the native connected Google Drive connector:
   - SED -> canonical `00_raw/SED` folder
   - HJC -> canonical `00_raw/HJC` folder
6. Re-list Drive and verify filename and size.

The purpose of this operation is to make the first available SED/HJC usable quickly for result analysis. Do not delay ordinary post-race acquisition waiting for later SED finalization.

If a valid canonical SED/HJC already exists from the same post-race operation, do not create a duplicate. The scheduled SED re-fetch happens in the next pre-race operation under Section 3.

## 5. Acquisition and transport boundary

JRDB authenticated acquisition is Actions-native because it requires JRDB secrets.

The standard transport is:

```text
Chat
  -> validated GitHub Issue request
  -> GitHub Actions authenticated JRDB fetch
  -> Actions artifact
  -> GPT downloads artifact
  -> GPT runtime validates raw ZIP
  -> native Google Drive connector upload/update
  -> Drive re-list verification
```

GitHub Actions must not write to Google Drive directly.

Do not use the retired Issue/Actions Drive bridge.

## 6. Drive-first duplicate protection and intentional refresh exception

Before an upstream fetch, check the canonical Drive folder for the requested filename.

For ordinary acquisition families/dates:

- if a valid file already exists, do not create a duplicate Drive object;
- do not refetch merely because the user did not provide a path;
- report that the canonical file already exists when no further action is required.

**Exception:** preceding-week SED during `mmddの開催前取得` is an intentional refresh target. Its existing Drive presence does not suppress the upstream re-fetch.

If an existing file is suspicious, size-mismatched, corrupt, or otherwise fails validation outside the intentional SED refresh path, do not silently overwrite it. Audit the discrepancy first.

## 7. Success criteria

An acquisition request is complete only after:

1. upstream fetch success for files that required fetching;
2. artifact presence;
3. local ZIP validation;
4. manifest SHA/size agreement when the workflow provides them;
5. native Drive upload/update success when publication changed;
6. Drive re-list confirms the exact final filename and size;
7. for a changed pre-race SED refresh, the canonical Drive object reflects the refreshed bytes and the previous snapshot remains recoverable through revision history.

Do not report "Drive保存済み" or "SED更新済み" before the relevant Drive verification is complete.

## 8. Normal command semantics summary

| User request | Acquire now | Publication behavior | Deferred / excluded |
|---|---|---|---|
| `mmddの開催前取得` | target PACI + missing SKB from immediately preceding race week + fresh SED for every preceding-week race date | PACI/SKB normal publish; SED compare-and-refresh canonical if changed | target-date SED/HJC |
| `mmdd〜mmddの開催後取得` | first available SED + HJC for every specified race date | normal duplicate-safe publish | SKB, PACI; later SED finalization waits for next pre-race cycle |

This table is the current default for routine 2026 daily raw operation.
