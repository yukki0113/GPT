# NAR P9 補助評価研究 — 2026-11-25

Status: EVALUATION_COMPLETE_NO_NEW_CANDIDATE. P10へ渡す研究基準 P8-Astar-r1 unchanged。保存・読み戻しが完了するまでCURRENTは更新しない。production/2026/ROI未承認。

## 1. 事前登録と範囲
- Design `docs/NAR_P9_RESEARCH_DESIGN_20261125.md` Git commit 3c1e8c44cead92e27c3b723bc5cbdbeb7008e267, blob f30c2455f8ab12fdf790868cb3bafa31669b00ed。P8-Astar-r1固定、Bstarを追加しない。P0.1 ENTRY cutoff。P8と同じ期間分割、補助残差は2017から（2016はAstarのwarm-up）。P9の新規候補は2024–25を選択に使用しない。P8で開示済みの回顧期間は独立未見ではない。
- 過去のvalid NORMAL finisherの正規化着順pから、同じraceでの固定Astar既知score順位（丸めscoreの同点平均順位）の正規化qを引いた残差e=p-q。既知4頭以上・ENTRY rosterの50%以上、1e9整数化。前180/365日、同馬除外。jockey/trainer/pairはn>=20/20/10、父/母父はn>=30。補正w*sum(e)/(n+k)、k30/100、w.10/.20。未知/支持不足は無補正、Astar未知のまま。5family 32候補。選択ルールは事前設計を変更せず。

## 2. 入力・entity・guards
- 2016–23の32 canonical assets同一SHA/ledger/size/row count、前回のschema/key監査継承。2024–25の8資産もbyte/row countのみ確認、全40一致。P8B年度別9 prediction archive全内部SHA一致。P8.0/P8Bの既知訂正条件・原Canonical不変。2017–23全ENTRY 939724行、roster/key/rank parity exact、曖昧馬0。history residual 880805件。
- exact name+affiliation jockey 616, trainer 709, pair 25209。jockey同race重複46行はj/p unknown、trainerはそのまま。複数所属を観測した名前86/3、統合せず別key。父名863/母父名1366 categories、欠損0（公式恒久IDではない）。観測上のキーであり完全な人物・血統名寄せではない。2017以前の補助残差は使わない。月次確定版、選抜/反復他馬の偏り残存、因果効果ではない。
- approved bundle outer/nested/wheel SHA一致、DuckDB 2.0.1/PyArrow 25.0.1/NumPy2.2.4、Git shared dependency_report (blob 7b5b8cdebf9d811b828c573ed4b1bb7950f83df3) success。初回全family一括1-thread処理がtimeoutしたためfamily別1-thread論理比較へ変更。特徴量のcount/sum/excluded全行差0、全ファイルbyte一致は主張しない。全候補prediction key/score/rank/null/applied 1/4 thread parity PASS。7年度境界×5familyのprefix direct-join reference と同日/未来極端値注入差0、禁止列7/7拒否。tie12境界テスト、score-only別作業ツリーでlabelなし/poisoned label同一。OSレベルsandboxではない。時点lineageはtargets/historyのhash, key, window, same-horse subtraction, count/sumを保存、実max履歴日は同一条件のjoinで再現可能。2024–25でP9 feature/scoreは作成していない。

## 3. 開発・比較
2017–21 eligible 64876/scored 63863、Astar 20820勝。32候補のうち騎手・厩舎全候補negative。最良 j180_k100_w20 -27、tk180_k100_w10 -21、pair p365_k100_w10 +10、sire s365_k100_w20 +62、damsire d365_k30_w20 +20。shortlist をGit commit 6be1bfb6af7044aa945266a5abf28f00cdf54778で比較前freeze。全候補の採否はdecision_ledger.csv。

| Model | 2022 wins | 2023 wins | Total wins | top1 top3 | winner in top3 | Qualification |
|---|---:|---:|---:|---:|---:|---|
| Astar | 4108 | 4221 | 8329 | 16808 | 16310 | reference |
| sire | 4100 | 4231 | 8331 | 16777 | 16304 | FAIL 2022 |
| damsire | 4122 | 4210 | 8332 | 16792 | 16310 | FAIL 2023 |
| pair | 4104 | 4225 | 8329 | 16788 | 16287 | FAIL 2022 |
| sire+damsire | 4115 | 4231 | 8346 | 16784 | 16302 | FAIL constituent gates |
| sire+damsire+pair | 4104 | 4235 | 8339 | 16776 | 16305 | FAIL constituent and 2022 |

2022–23 all 26919 eligible/26391 scored; 261049/272409 scored runners、全候補同一支持なのでnative/common同一。Astar 31.56000% (8329/26391), prefix2 31.62442% (+0.06442pp), paired date-block bootstrap 2000 seed20261124 年層別 CI [-0.072377,+0.200980] pp。その他候補CIもすべて0を跨ぐ。副指標/順位一致率・coverageと全fold/venue/distance/history-count別集計は証跡に保存。勝率だけを目的とし個別不合格を統合で救済しない。

## 4. P9 close
P9.1 jockey/trainer REJECT_DEV、P9.2 pair REJECT_VALIDATION、P9.3 sire/damsire REJECT_VALIDATION、P9.4 integration REJECT_CONSTITUENT_GATE。P9新規候補なし、Astar fallback fixed. 2024–25 P9確認は **NOT_APPLICABLE_NO_QUALIFIED_CANDIDATE**（P8では既に開示済み）。追加の+0.3pp gateを満たした新規モデルはない。結果を見て係数変更・候補追加・閾値緩和をしない。単純残差方式の限界であり騎手/厩舎/血統一般が無意味とは結論しない。P10でAstarを固定、P8/P9不採用結果は不変。P10のROI/独立確認は別途事前設計、2026は別承認まで使用不可。production_approved=false。

## 5. Reproduction / artifacts
`prepare.py 2023` → `features.py devval 4` → `features.py devval 1 {j,tk,p,s,d}` → `score.py dev {4,1}` → `evaluate.py dev` → `select_candidates.py dev` → shortlist Git freeze → `score.py val {4,1}` → `evaluate.py val` → `select_candidates.py val` → `final_audit.py`。初回1-thread一括タイムアウト、別family照合へ変更したが数式・候補は不変。入力pathは実行環境依存、input_manifestで再構成可能。予想freezeは各model全ENTRY行を保存、参照と特徴量は別アーカイブ。評価label原本はCanonicalから再生成し配布しない。Gitにraw/post/Parquetは置かない。
