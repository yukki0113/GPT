# BRDB ⑥ D4 — D3条件別研究から統合レビュー候補への補足接続（研究用）

Date: 2026-11-16 (JST)  
Status: **RESEARCH SIDECAR E2E PASS / NO PRODUCTION AUTHORIZATION**

## 背景・境界

- 凍結済み `brdb-review-v0.1` は変更しない。
- 既存 `brdb-integrated-blood-review-v0.2-candidate` schema は `supplemental_insights` 未定義であるため変更しない。
- D4 は**別ファイルの非採点サイドカー**として `brdb-d4-supplemental-research-v0.1` を出力。RaceNote/PWA/本番BRDB CURRENTへ自動注入しない。
- 接続対象は D3 の父 `SIRE`、母父 `BMS`、父×母父 `PAIR` の出典付き記述統計。③-C/④の名前観測を予想実績の公式IDに変換しない。地域ルーツや内包祖先12候補の適性は未検証なので補足を作らない。

## 入力・出力

D3の実データ正本3ファイル（SHA-256固定）から、研究用のrace contextと一意なJRDB8桁馬ID付き登録頭数分の投影を生成する。PACIからの抽出はD4では未実装。デモ入力の馬IDは**架空・研究用**であり実在の出走馬と誤認してはいけない。

| 正本D3ファイル | SHA-256 |
|---|---|
| `d3_full_condition_evidence.json` | `705a85d4c43b369b14cbba9177f5af13ed3111f1a5031a97ee76acf51064e764` |
| `d3_temporal_diagnostic.json` | `27abb3aafabd8b5350009cf8623d43246bda70365427cc772d07e3aba4d8c8bf` |
| `d3_run_receipt.json` | `4a128dc02baf4a6ee82a1b560fa1cafb62f540cba8bed38511a97af43c3abd2e` |

研究レースの日付はD3結果の最終参照日（2026-11-01）より後のみ受理する。これは**未来結果を含む過去レースへのサイドカー作成を拒否する最低条件**であり、祖先・血統情報の当時公開時点を保証するものではない。`historical_asof_status=AS_OF_UNVERIFIED` を固定し、予想へ利用しない。

各馬に出力するのは、対象芝ダ・距離・距離帯・競馬場・馬場状態原コードと一致する観測実績、母数、同条件基準値、Wilson95区間、対象時期分割診断。全て `interpretation_status=OBSERVATION_ONLY_AS_OF_UNVERIFIED`。未知の組合せは空根拠とし、`NO_SAMPLE` に改変しない。

- `factors.positive/negative/unknown=[]`
- `summary=null`、`confidence=UNASSESSED`
- `contribution_to_score=null`
- `research_only=true`、`prediction_safe=false`、`release_status=RESEARCH_SIDECAR_ONLY`
- 同じ出走がSIRE/BMS/PAIR各レーンに現れうるため、**根拠数を合算して独立試行件数としない**。

## 受入条件

1. ③〜D3の回帰スイートとD4新規11件がPASS。
2. GitHubから正本コードを取得してSHA照合し、同一D3実データで2回生成したサイドカーのバイトSHA一致。
3. 架空3頭デモの対象血統に一致する根拠が抽出され、血統不明の馬は根拠空配列になること。
4. 本番のレビュー契約ファイル・CURRENT、RaceNote、PWA、workflowへの差分がゼロ。
5. 時点確認未完了のためD4は**研究用の補足表示インターフェースが接続可能**という意味で受入れ、⑤統合Blood Reviewの主解釈・予想スコア・RaceNote接続の完了とはみなさない。

## 再現コマンド

```bash
python horse-racing/brdb/src/run_brdb_d4_sidecar.py \
 --full /secure/d3/d3_full_condition_evidence.json \
 --temporal /secure/d3/d3_temporal_diagnostic.json \
 --receipt /secure/d3/d3_run_receipt.json \
 --context /secure/d4/research_field.json \
 --output /secure/d4/d4_research_sidecar.json
```

出力には個票と利用元の父/母父名が含まれるため、現実の競走馬の入力と生成物は公開Gitへ保存しない。研究用デモのみ公表可能。
## 2026-11-16 最終E2E・回帰検証

[GitHub Actions #43834441975](https://github.com/yukki0113/GPT/actions/runs/43834441975) は source commit 037c7026e098679e8b77f41c132215780aa00b7f で実行、結論 **PASS**。artifact data-storage-fallback-43834441975 (ID 14209669608) から正本D4のPython 3ファイルを取得し、SHAを各ファイルについて独立照合した。

| 回帰テスト | 件数 | 判定 |
|---|---:|---|
| ③ Stage3 | 73 | PASS |
| ④ Stage4 | 10 | PASS |
| ⑤ D3 | 9 | PASS |
| ⑥ D4 | 11 | PASS |
| **計** | **103** | **PASS** |

研究用D3実データ正本3ファイルを固定入力とし、GitHub artifactから取得した**そのままのD4正本コード**で仮想研究レース（2026-11-16、venue_code 05、芝2000m、架空の馬IDを持つ3頭）を2回処理し、出力JSONがバイト一致することを確認。**仮の3頭は公式PACIの実出走馬ではなく合成フィールド**である。

| 正本E2E項目 | 実測 |
|---|---:|
| 研究レース登録馬 | 3/3 |
| D3に厳密一致する補足根拠 | **17件** |
| SIRE / BMS / PAIR | **8 / 8 / 1** |
| 上位50対象外の架空父名 | 根拠0件 |
| 統計母数・Wilson区間・基準値 | D3の元値を保持 |
| positive / negative factors | 全馬で空 |
| summary | 全馬 null |
| confidence | 全馬 UNASSESSED |
| prediction_safe | false |
| 2回生成した研究用JSON SHA-256 | ddc42aa1d80ba9d63f5e3d7e19f39149a0c3426ccfb725acc3c757884f23691e（完全一致） |

**D4初期研究バッチの取り込み可**。ただしこれは「⑤統合評価・スコア・本番結合の完成」ではなく、条件別統計を安全に表示できる独立補足インターフェースの受入である。公式PACI全出走馬での実レースE2E、race-day血統資料の当時配信時刻、交絡調整、適性ラベルの妥当性、RaceNote/PWA本番表示は**未実装／未承認**。
