# EdgeDB v0.5 PWA preview

This branch adds a separate research preview. It does not change `current_manifest.json`, STANDARD Query, the daily production Action, Current Publish, or the public `newspaper.html` route. The public `special_memos` data remains available for compatibility; the preview route hides its old display column.

## Sources and boundary

- Candidate inventory: `config/edgedb/v0_5/frozen/v05_positive_value_frozen_cohort.json`, exactly 1,620 candidates; SHA-256 `a85a7ee86dc21b6e081fd5a637245b06a2ba23eef2e22628a14468b004e2cdc9`.
- OOS diagnostic data: existing Actions run `37614611257`, artifact `11478468034` (`edgedb-v05-2026-oos-eval-pr-1898`); ZIP SHA-256 `f10034cf6d2d730dcb3d76b6c9be41c90d36e61e49c94b70ab7458f296eb9f13`. The preview requires this exact ZIP; the CSV is not copied into Git.
- Matcher: existing `jrdb_edge_v05_2026_pre_race_match_freeze.py` condition matcher. Its candidate inventory and gates are unchanged.
- Facts: the same PACI as Newspaper Base plus existing canonical Analysis current root. Only exact previous-race links dated before the target may supply T3 or T4 transition conditions.
- Frozen 2026 OOS evaluation ends on 2026-10-04. To avoid displaying future evaluation facts in a historical preview, the target date must be later than this endpoint.

The daily current-facts source does not expose complete prior starts/blinker history or verified pre-race target going. T4 first-use conditions, T5 first-use conditions, and T6 going conditions therefore remain `UNKNOWN/UNAVAILABLE` and cannot match. T4 surface-transition candidates may match when the exact prior link resolves. All 1,620 candidate definitions remain intact. The audit records these omissions and marks `source_status.edge_v05.state=PARTIAL`. A source, exact-join, or query error yields `ERROR` while preserving the Base package and its other addons. No legacy Edge result is substituted.

## Dry run

Use an existing audited Newspaper Base day and its PACI. Download the immutable OOS artifact with GitHub Actions before running:

```bash
gh api repos/yukki0113/GPT/actions/artifacts/11478468034/zip > /tmp/v05-oos.zip
python horse-racing/jrdb/src/jrdb_newspaper_edge_v05_preview.py \
  --base-day /path/to/base-day --output-dir /path/to/v05-preview-day \
  --paci /path/to/PACI.zip --analysis-root /path/to/canonical-analysis-current \
  --oos-artifact-zip /tmp/v05-oos.zip
```

The script checks the downloaded ZIP SHA before reading it. It writes a separate `day-package.json`, never a Current Publish path.

Open `pwa/newspaper-v05-preview.html` and manually import that package. The page uses a separate OPFS file and an unpublished current URL. It does not fetch or overwrite the public current newspaper.

`horse.addons.edge_v05.candidate_ids` holds the matches. Each race has one `edge_v05_candidates` dictionary for its matched IDs, rather than repeating condition and OOS text in every horse row. The existing race schema accepts these additive fields. The preview displays `○` for at least one ID and opens all matched candidates in a modal, with two initially visible.

The 2026 tiers and ROI are historical research diagnostics. They do not affect matching, RaceNote, marks, or betting recommendations. `CONTRADICTED` remains visible in the expandable list.

## Remaining source work before full T1–T6 coverage

Connect a complete, verified, strictly prior-date start/blinker history for T4/T5, including the earlier 2026 races and ambiguity checks already used by the frozen replay. Connect a timestamped pre-race going source for T6. Do not use target SED result going. Then run a real PACI/Analysis dry run and inspect PC and phone layouts before proposing any public display cutover.
