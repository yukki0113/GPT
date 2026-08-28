# RaceNote Archive Router E2E 状態

## 対象

- 日付: 2025-08-24
- 会場: 新潟
- R: 11R
- 比較: RaceNote Archive preferred backend vs annual Raw fallback

## 実データ E2E

Issue: `#163`

Run: `33129910768`

検証結果:

```text
Archive path
  used_backend = racenote_archive
  archive_resolution_status = used
  coverage_mode = full_month
  publication_status = publishable

Raw fallback path
  used_backend = historical_raw_cache_or_fetch

final RaceNote
  schema_version = 1.0
  semantic_match = true
  semantic_sha256 = b28b415e4c99235e73ff71695f3f7856eca6fd529106448da63b1aeabf170b16
```

実行時間（同一run・同一Analysis/Mart・同一Raw cache）:

- Archive Router: 9.592282 sec
- Raw Router: 10.035356 sec

`byte_exact_match = false` は `metadata.generated_at` の差を含むため合否基準にしない。Archive schema v1.0のsemantic hash規則どおり、`metadata.generated_at` を除いた全フィールド一致を正式基準としPASSした。

## Full-month publication

Issue: `#164`

2025-08 shard:

- Release tag: `jrdb-racenote-archive-202508-v1.0`
- asset: `jrdb_racenote_archive_202508_v1_0.sqlite`
- SHA-256: `1e82e02a184da707ee4c2ea13da53933d25ddcfbf39cdbe27dd8357f109b2263`
- size: 6,852,608 bytes
- race_count: 360
- full scan: 360 / 360 PASS
- coverage_mode: `full_month`
- publication_status: `publishable`

## Resolver validation

Issue: `#165`

`resolve_racenote_archive_release.py` が上記Releaseを対象月から自動探索し、SQLite実体をvalidationした結果:

- status: `resolved`
- SHA-256: publish時と一致
- coverage_mode: `full_month`
- publication_status: `publishable`
- race_count: 360

## Normal RaceNote request integration

Issue: `#166`

通常の `[RACENOTE_REQUEST]` にArchive path/tag/raw_urlsを渡さず実行した結果:

- archive_resolution_status: `resolved`
- archive_tag: `jrdb-racenote-archive-202508-v1.0`
- used_backend: `racenote_archive`
- task_exit_code: 0
- collect_exit_code: 0

これにより、2025-08について次のproduction flowを実データで確認済み。

```text
[RACENOTE_REQUEST]
 -> target monthからlatest compatible Release探索
 -> SQLite metadata / integrity validation
 -> publishable full-month Archive採用
 -> base v0.2 restore
 -> current production Analysis/Mart enrichment
 -> final RaceNote v1.0
```

Archive未整備・resolver失敗・validation拒否時は従来のannual Raw / PACI fallbackを維持する。
