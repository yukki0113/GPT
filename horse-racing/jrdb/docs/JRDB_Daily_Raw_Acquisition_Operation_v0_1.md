# JRDB Daily Raw Acquisition Operation v0.1

Status: CURRENT  
Effective: 2026-10-01

## 1. Purpose

2026 current-operation raw acquisition is split into two user-facing commands so that each JRDB family is fetched at the timing when it is actually expected to be available.

This contract covers only the routine acquisition and Google Drive publication of:

- PACI
- SED
- HJC
- SKB

It does not change historical 2010-2025 Warehouse operation, Analysis generation, RaceNote generation, or downstream settlement/research contracts.

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
8. Validate each fetched SKB ZIP and record size/SHA-256/member count.
9. Publish outputs with the native connected Google Drive connector:
   - PACI -> canonical `00_raw/PACI` folder
   - SKB -> canonical `00_raw/SKB` folder
10. Re-list the Drive target folders and verify the uploaded filename and size.

### Important SKB timing rule

SKB is intentionally **not** part of the immediate post-race acquisition.

JRDB publishes SKB later than SED/HJC. Repeated same-week post-race SKB requests can therefore produce legitimate `NOT_FOUND` responses.

Operationally:

```text
race weekend N
  -> post-race: SED + HJC only

before race weekend N+1
  -> PACI for N+1
  -> recover any missing SKB from race weekend N
```

A missing SKB during the post-race window is not by itself an acquisition failure.

## 4. Post-race acquisition

Request form:

```text
mmdd〜mmddの開催後取得をお願いします
```

A single date may be expressed as the same start/end date or an equivalent single-date request.

### Required work

For every requested race date:

1. Check the canonical SED and HJC Drive folders for existing files.
2. Fetch:
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
  -> native Google Drive connector upload
  -> Drive re-list verification
```

GitHub Actions must not write to Google Drive directly.

Do not use the retired Issue/Actions Drive bridge.

## 6. Drive-first duplicate protection

Before an upstream fetch, check the canonical Drive folder for the requested filename.

If a valid file already exists:

- do not create a duplicate Drive object;
- do not refetch merely because the user did not provide a path;
- report that the canonical file already exists when no further action is required.

If an existing file is suspicious, size-mismatched, corrupt, or otherwise fails validation, do not silently overwrite it. Audit the discrepancy first.

## 7. Success criteria

An acquisition request is complete only after:

1. upstream fetch success for files that required fetching;
2. artifact presence;
3. local ZIP validation;
4. manifest SHA/size agreement when the workflow provides them;
5. native Drive upload success;
6. Drive re-list confirms the exact filename and size.

Do not report "Drive保存済み" before step 6.

## 8. Normal command semantics summary

| User request | Acquire now | Deferred / excluded |
|---|---|---|
| `mmddの開催前取得` | target PACI + missing SKB from immediately preceding race week | SED/HJC for target date |
| `mmdd〜mmddの開催後取得` | SED + HJC for every specified race date | SKB, PACI |

This table is the current default for routine 2026 daily raw operation.
