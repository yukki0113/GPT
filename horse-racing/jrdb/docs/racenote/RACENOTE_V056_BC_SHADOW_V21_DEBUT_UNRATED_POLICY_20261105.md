# RaceNote v0.5.6 — Shadow B/C v2.1 初出走馬・判定不能の継続運用規則

- **制定**: 2026-11-05（BTDAY-0162の結果解禁より前）
- **状態**: RESEARCH ONLY / PRE-RESULT AMENDMENT / APPLY TO CURRENT UNFROZEN 0162 AND FUTURE UNSEEN BTDAY
- **互換**: Shadow v2運用定義（`RACENOTE_V056_BC_SHADOW_V2_FORWARD_OPERATION_20261104.md`）への追加規則。元Prediction／元Confidence／印／A/Z／T2は変更しない。
- **既存研究Freeze**: BTDAY-0163〜0171の既存B/Cラベル・原票・検証済みJSON・SHAを一切変更しない。BTDAY-0152〜0161の既存研究にも遡及適用しない。

## 1. 目的

初出走馬が◎となる未勝利・1勝クラス等では、レース出走歴が存在せず過去走由来の「3着内再現性」を提示できない場合がある。**これだけで日単位のShadow研究Freeze全体を停止しない**。同時に、B/Cを捏造せず「評価不能」も選定結果として完全に記録・固定する。

初出走馬＝必ずUではない。実際の適性・調整・比較根拠が十分ならB/Cを個別選定する。逆に経験馬の単なる取込漏れを初出走扱いしてはいけない。

## 2. 判定優先順位

1. **確認**: 対象レースの凍結済みPrediction/Confidenceの◎とReaderの同一馬番・同一馬IDを照合する。過去走がないことを`history_coverage.observed_starts == 0`、`historical_profile.career.starts == 0`、`recent_runs`/ `older_runs`が空であることで確認。欠測・パーサ不具合と区別できない場合はデータ品質の別エラーとして修正する。
2. **代替する事前証拠**: 調教時計と本数（絶対値・相対値・仕上がり傾向）、血統・兄姉の当該条件適性（補助証拠）、陣営・騎手・厩舎・枠、ペースと他の印馬との実績比較など、対象レース実施前に利用可能な情報を複数の独立軸で検討する。指数や血統の一般論だけで3着内を確約しない。デビュー馬の調教評価を既走馬の実走再現性と同等視しない。
3. **Shadow B**: ◎が馬券内に残り得る十分具体的な積極根拠と、他馬との比較の両方がある場合のみ選定。初出走だからBとはしない。
4. **Shadow C**: ◎が4着以下になり得る**具体的で無視できない不利・条件リスク**が事前情報で裏付く場合のみ選定。初出走・未実証というだけでCとはしない。
5. **Shadow U（Unrated: 判定保留）**: 上記の比較に必要な証拠が合理的に不足し、B/Cのどちらにもできない場合。**Uは低評価ではなく、証拠不足により判定しないことを示す第三の研究状態**。元のConfidence B/Cは変更しない。

## 3. Uは欠測を隠さない・研究の選択バイアスを残さない

- 正本ConfidenceのB/Cを対象とする**全レースに必ず1レコード**を作り、Shadow `B`/`C`/`U`を格納。Uの理由には`UNRATED_NO_PRIOR_RUN`の監査コードと、利用できた事前情報、B/Cを決められなかった根拠を残す。
- Uは**B/Cの区分別的中率・回収率の分母から除外**し、件数、元Confidence別分布、対象全体に占める割合を独立して公表する。
- 成績解禁後はUもレース結果との突合対象に含め、別表で◎着順・3着内率・馬券別損益を参考表示できる。ただしUを事後的にB/Cへ振り分けたり、B/Cの検証成績に紛れ込ませたりしない。
- Uが多い場合、B/C性能が良好でも「評価しやすいケースに偏っている」という制約を明記する。U率を下げるための機械的B/C付与を禁止。
- Uを持つBTDAYも**研究用Frozen**として扱い、結果閲覧前に全件入力・元FreezeのSHA一致・Uの監査根拠とSHA・コミットを固定する。旧validatorを無理に通さず、**v2.1専用validator**を用いる。
- Uの利用範囲は当面「既走ゼロがReaderから検証された◎」に限定する。既走馬の証拠不足やソース欠損は従来どおり品質調査が必要だが、その1Rが未解決でも日全体の本番Prediction／Confidence処理は停止しない。

## 4. 既存入力形式を保ったU記録

既存10フィールド（`venue, race_no, honmei, shadow_grade, strongest_rival, axis_positive_case, relative_axis_case, unverified_assumptions, axis_failure_scenario, final_reason`）を変えず、`shadow_grade: "U"`を許す。全テキスト欄は省略せず、そのレース固有の事前事実を書く。

例（架空・実レースの判断ではない）：

```json
{
  "venue": "東京",
  "race_no": 1,
  "honmei": 4,
  "shadow_grade": "U",
  "strongest_rival": 8,
  "axis_positive_case": "初出走で過去レース実績なし。調教の動きは事前材料だが着内の再現性は検証できない。",
  "relative_axis_case": "○8にはレース実績があるが、◎4の未知の能力を比較可能な事実で順位付けできない。",
  "unverified_assumptions": "初戦のスタート・追走・砂被り・距離耐性がいずれも未実証。",
  "axis_failure_scenario": "初戦の追走や位置取りに対応できず着外となるリスクはあるが、頻度を裏付ける実走証拠がない。",
  "final_reason": "UNRATED_NO_PRIOR_RUN: 初出走でBの着内根拠もCの具体的な着外リスクも判定できないためU。"
}
```

## 5. Freezeとv2.1ツール

- 入力：正本`v056`ルート、元B/Cを全件含む研究用原票。
- v2.1専用 `horse-racing/jrdb/src/racenote_v056_bc_shadow_v21.py` で`--assert-results-unopened`を付けてバリデーション。元`racenote_v056_bc_shadow.py`はv1/v2の既存固定検証用として温存。
- 全Rカバレッジ、元A/Z対象外、元◎と相手馬番、Prediction/Confidence元SHAの一致は従来どおり必須。Uを使う場合は上記無出走状態をReaderと照合。任意にUへ逃げるフォールバックは禁止。
- 出力は`rated_count`と`unrated_count`および`B->U`などの遷移を明示。既存評価コードがU未対応なら**黙って読み込まずfail closed**にし、Uを別集計できる評価器を適用する。
- **結果解禁前に**研究原票・検証済みJSONのGitコミット、各SHAの検算、Uの根拠確認を完了する。ローカル保存やActions成功だけでは研究Freeze完了とは呼ばない。
- v2.1を後から結果既知のコホートに遡及利用しない。

## 6. 0162の既存保留への適用

BTDAY-0162京都1Rの◎10は、Readerに初出走（過去走0）が記録されている。既存26Rの判定内容は保持し、京都1Rだけを本規則で再監査する。代替事前材料でB/Cのいずれも証明できない場合は**Uとして1R記録**し、計27Rの研究用Freezeを成立させる。結果・払戻はそのコミットとSHA確認が済むまで照会しない。

この規則は**既存の予想や正本A/B/C/Zの判定を変更するものではない**。
