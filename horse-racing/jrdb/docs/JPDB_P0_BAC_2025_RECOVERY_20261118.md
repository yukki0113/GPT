# JPDB P0 — BAC 2025/12/13・12/14 欠損復旧・正本保全監査
- 実査日: 2026-11-18 JST
- 親監査: `JPDB_P0_RECENT_WINDOW_VERIFICATION_20261118.md`
- データ方針（ユーザー確定）: **JPDBの通常集計・保存対象は2023-01-01以降**。2021〜2022の延長案は採用せず、Course Profile現行epochとの不整合を避ける。期間端とas-ofは引き続き遵守。更新頻度は未決定。
- 判定: **BAC欠損のデータ復旧候補 PASS / accepted Warehouseとの再出版・canonical切替 NOT DONE**。

## 1. 既存年間BAC欠損の現認
2025年年間正本 `BAC_2025.zip`（Drive file ID `1k1HagEAM0BjwEVD0bT1sz1PwEMQy3btg`, SHA256 `aeab5d807c12640b908152eb24249c872b4aaafcfc7e97baaafda440994c5491`）では、
- `BAC251213.txt`: 9R（中山・中京・阪神の当日36Rのうち27R欠損）
- `BAC251214.txt`: 10R（当日36Rのうち26R欠損）
- 合計欠損 **53R・KYI出走735行**。2025年の年間BAC総レース **3,402R**。年間KYI/SEDは各 **47,884行**、レースキー各 **3,455R**。

## 2. 正式JRDB認証経路で再取得
- GitHub Issue [#2641](https://github.com/yukki0113/GPT/issues/2641) `[JRDB_DAILY_HISTORY_FETCH_REQUEST] jpdb-p0-recover-bac-20251213-14`、workflow `.github/workflows/jrdb_daily_history_fetch_issue.yml`。
- Router run `44249935270` SUCCESS → source acquisition run [44250027970](https://github.com/yukki0113/GPT/actions/runs/44250027970) SUCCESS。全ステップ成功、Issue完了。
- Actions artifact ID `14403133146`, name `jrdb-daily-history-20251213-20251214`, containing two verified original daily JRDB ZIP files.
- `BAC251213.zip`: 1,091 bytes, SHA256 `f159c63f89889bd4a1151e63584055ba43306806f3383da3dd72de492cca41ff` → `BAC251213.txt` **36R / 6,624bytes**。
- `BAC251214.zip`: 1,155 bytes, SHA256 `3610a3d09161d9da57a2c50916ead3c337195fe1caa66e1cb15e0edd4afea160` → `BAC251214.txt` **36R / 6,624bytes**。
- 固定長BAC1R=184bytes（CRLF含む）。日付・競馬場3場×各1〜12R・race_key重複なし・対象日のKYI/SED出走キー一致を実確認。

## 3. 既存Rawとの差分と改版注意
| 日付 | 年間BAC既存 | 再取得結果 | 追加キー | 既存重複 | 重複行のbyte変更 |
|---|---:|---:|---:|---:|---:|
| 2025-12-13 | 9R | 36R | 27R | 9R | 9/9 |
| 2025-12-14 | 10R | 36R | 26R | 10R | 10/10 |
| **合計** | **19R** | **72R** | **53R** | **19R** | **19/19** |

**重要:** 再取得は「53行だけの追記」ではない。重複19RもRaw byteが変わる（後日確定・更新フィールド）。一方、race-key/開催日/開催場/コース・距離等の監査対象静的範囲は不一致0。元版の19行は消去せず、年間既存オブジェクトを凍結してprovenanceを残す。

## 4. 別世代補修候補を作成・検証（現行正本未変更）
一時的な監査スクリプト `jpdb_bac_2025_repair_verify.py`（この会話の分析環境）は、元年間ZIPの**全109 memberを引き継ぎ、`BAC251213.txt`／`BAC251214.txt`をJRDBの再取得済み36R分の完全版に差し替える**。他107 memberは展開後の元バイト列に完全一致。元ZIP自体は変更なし。

- Candidate: `JPDB_BAC_2025_REPAIRED_CANDIDATE_20261118.zip`
- Candidate size 109,879 bytes / SHA256 `38bdb48d825aa97a91b43b2ba16d356b903c7fffd1acb45ceaaf738eed638efd`
- ZIP全memberのtestzip PASS、年間BAC race_key重複0、固定長異常0。
- Candidate 2025 BAC **3,455R**（元3,402R + 53R）。
- 2025 KYIレースキー **3,455R** / SEDレースキー **3,455R** / Candidate BACレースキー **3,455R**、各集合が完全一致。**BAC↔KYI↔SEDレースキー 3,455/3,455 = 100%、差集合0**。
- 該当2日KYI・SEDは12/13各499行、12/14各496行、再取得BAC各36レースに全件所属。
- 候補ZIPを全体で再読込して同一性・レコード数をチェック済み。
- ただし候補は**現在入手したJRDB最終寄りのBACであり、2025年12月当日のpre-raceスナップショットであった証拠はない**。研究用の実測歴史条件と当時の予想可能情報を混同しない。

## 5. 結論と正本境界
- **Source recovery PASS:** 欠損53Rの完全版BACを取得・照合できた。修復候補で2025年全3,455Rのrace-key coverageを達成。
- **Canonical Raw unchanged:** 既存Drive `BAC_2025.zip` を上書き／削除／renameしていない。
- **Accepted Historical Warehouse unchanged:** `jrdb_normalized_warehouse_v1_2010_2025_g20260921` の immutable Parquet object / manifest / CURRENTを一切変更していない。
- **Publication / consumer migration OPEN:** 年間Rawと既存Warehouseは版が固定されているため、Rawを直接上書きして既存Accepted Warehouseと不一致にするのは不可。JPDB研究で使う場合は明示的な `BAC_2025_repair_overlay` のsource SHA、採用日、対象member、diff台帳をReader inputに明記し、独立したimmutable generationの受入手順と下流影響を確認してから別世代として公開する。
- **JPDB P0 overall remains REVIEW_REQUIRED**: pre-race取得時点のprovenance、SED異常コード5の意味、physical Course geometryのPARTIAL status、Refresh cadenceが未解決。P1実装とRaceNote本番接続は未承認。

## 6. 監査ローカルファイル
- `JPDB_BAC_2025_REPAIRED_CANDIDATE_20261118.zip`: 保全型補修候補（GitHub/Drive現行正本とは別）。
- `JPDB_BAC_2025_REPAIR_VERIFICATION_20261118.json`: 年間／日別のsourceハッシュ、missing keys、変更対象、照合結果、発行しない理由。
- `jpdb_bac_2025_repair_verify.py`: 一時的実査スクリプト（JPDB production parserではない）。
