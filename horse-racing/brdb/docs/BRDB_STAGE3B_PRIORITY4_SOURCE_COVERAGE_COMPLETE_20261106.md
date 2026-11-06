# BRDB ③-B 継続：優先4祖先の名前経路48件を個別血統資料に照合

Date: 2026-11-06  
Status: **48/48 SOURCE-CORROBORATED NAME PATHS / 0 ADDITIONAL JRDB CANONICAL PERSON IDS / RESEARCH ONLY**

## 1. 完了した作業の正確な範囲

③-B初回マスタ（2022〜2024年生まれの研究収録12,018頭から抽出した父/母父共通上位50種牡馬）に記録された、サンデーサイレンス、ウインドインハーヘア、キングマンボ、マンファスという**頻出4祖先についての名前観測48経路**を調査した。

- 前バッチ：12経路にJBISの個別子孫血統ページと各祖先のJBIS個別ページを紐付け。
- 今回新規：**36経路**に、子孫本人のJBIS血統情報と祖先の確認済みJBIS人物ページを紐付け。
- 合計：**48/48の外部血統関係の出典整備**。上位50種牡馬のうち**31頭**にまたがる。
- 対象経路には`S`,`D`,`SS`,`SD`,`DSS`,`DDD`,`SSS`,`SSD`が含まれる。意味は出走馬ではなく**各種牡馬自身からの父S・母D経路**。
- **人物同定の正式JRDB 8桁ancestor horse_idを新規確定した件数は0**。JBIS IDは外部IDであり、JRDB個体への承認済みcrosswalkは0のまま。従ってこの「48/48」はJRDB親子IDグラフの経路coverageではない。
- 歴史的な出走前公開時点は未監査（`AS_OF_UNVERIFIED`, `prediction_safe=false`）。適性・国ルーツの加点や採用は一切しない。

## 2. 追加した名前経路の具体例

| 子孫側種牡馬 | 確認した追加経路 | 直接の血統資料 |
|---|---|---|
| レイデオロ | `SS` Kingmambo、`SD` Manfath、`DDD` Wind in Her Hair | https://www.jbis.or.jp/horse/0001189721/pedigree/ |
| サートゥルナーリア | `SSS` Kingmambo、`SSD` Manfath、`DSS` Sunday Silence | https://www.jbis.or.jp/horse/0001215724/pedigree/ |
| ルヴァンスレーヴ | `DSS` Sunday Silence | https://www.jbis.or.jp/horse/0001205475/pedigree/ |
| リオンディーズ | `SS` Kingmambo、`SD` Manfath、`DSS` Sunday Silence | https://www.jbis.or.jp/horse/0001170063/pedigree/ |
| キタサンブラック | `SS` Sunday Silence、`SD` Wind in Her Hair | https://www.jbis.jp/horse/0001155349/ |
| シルバーステート | `SS` Sunday Silence、`SD` Wind in Her Hair | https://www.jbis.jp/horse/0001171845/ |
| リアルスティール | `SS` Sunday Silence、`SD` Wind in Her Hair | https://www.jbis.jp/horse/0001157711/ |
| サトノダイヤモンド | `SS` Sunday Silence、`SD` Wind in Her Hair | https://www.jbis.jp/horse/0001175221/ |
| コントレイル | `SS` Sunday Silence、`SD` Wind in Her Hair | https://www.jbis.jp/horse/0001237042/ |
| ゴールドアリュール | `S` Sunday Silence | https://www.jbis.jp/horse/0000619768/ |
| ステイゴールド | `S` Sunday Silence | https://www.jbis.jp/horse/0000286968/ |
| マンハッタンカフェ | `S` Sunday Silence | https://www.jbis.jp/horse/0000324971/ |

各リンクは該当種牡馬の血統情報への参照。詳細な**全48行・個別ID・出典URL・枝パス**はJSON `taxonomy/stage3b_priority4_bridge_candidate_v0_4.json`に格納（5代表に直接リンクできる場合はそのURLを優先）。

## 3. ファイルと検証

- 正本候補：`taxonomy/stage3b_priority4_bridge_candidate_v0_4.json`：31子孫個体のJRDB観測IDとJBIS個別ID・外部血統パス48件、4祖先のJBIS外部個体ID、同一性承認状態。
- `src/brdb_stage3b_priority_bridge.py`：48行・31子孫・4祖先をガード、本人IDやhistorical as-ofの無証明な昇格を拒否する研究用audit。
- `tests/test_brdb_stage3b_priority_bridge.py`：48件の正常fixtureと境界違反を想定した10ケース。
- ローカル既存の50頭研究JSONの出典SHA `89d01e2c05af27a929c8398ef9e94660f5f1e442362d458383db6e6a9bd7bdc0`を固定し、**別のローカル監査スクリプト**で、旧12＋新36のすべてが該当50頭の名前・枝パス観測と一致し、未監査経路が0件であることを実行検証。
- 上記は**ローカル独立スロット監査**であり、GitHubコミット済みPython validatorをそのまま実行したことを意味しない。後者のPython unittestとGitHubモジュールE2Eは依然**未実行**。GitHubファイルのread-backとJS静的整合を別途実施。

## 4. 依然残る問題

**48/48で完了したのは「4祖先名が登場する経路の外部出典への紐付け」であり、「高頻度50頭から3代先までの完全な馬IDネットワーク」ではない。**

現在、上位50種牡馬の各世代でのJRDB正式IDベース到達経路は、1代目36/100、2代目10/200、3代目0/400のまま。JDDB資料内に未収録の古い父母個体と外部JBIS profileの正式な相互同定基準を、別途マスタで承認・適用する必要がある。

③-Bの次段は、`JRDB horse_id（子孫）→JBIS個体（同一馬）`の複数項目同定（馬名・生年・性別・父母名・公式系統・出典）と、外部祖先個体の一意化・母母含む必要範囲の共有グラフ格納を設計/実装し、**出典付き外部IDによる観測グラフのcoverageと、JRDB canonical horse IDによるグラフcoverageを分離**して再計測すること。

今回の研究用補完はBRDB CURRENT、①〜⑤の主評価、RaceNote、PWA、Newspaper、本番workflowに一切接続しない。優先関係は①〜③＞④≫⑥⑦を維持。
