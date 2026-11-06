# BRDB ③-B継続 — 頻出4祖先の出典付き個体リンク候補を補完

Date: 2026-11-06  
Status: **12 EXTERNAL PEDIGREE PATHS CORROBORATED / 36 PRIORITY-NAME SLOTS STILL UNAUDITED / 0 JRDB PERSON-ID CROSSWALKS / RESEARCH ONLY**

## 1. 目的・実行範囲

③-B初回バッチの共通上位50種牡馬から、影響範囲の大きい**サンデーサイレンス（1986）、ウインドインハーヘア（1991）、キングマンボ（1990）、マンファス（1991）**を優先調査した。既存の研究成果物`stage3b_top50_master_research.json`（ソース世代`5279af0bd8226cde`）を変更せずread-only監査。

- 4祖先の名前が直接観測された枠は、上位50頭のうち**31種牡馬・48経路**。
- **7種牡馬の外部JBIS個体ページ**にある直接／二代前の表示祖先と、**4祖先それぞれの独立JBIS個体ページ**を照合し、**12経路**を「外部資料で個体対応を裏付けた経路」として登録した。
- 残る**36経路**は表記名が一致していても、それぞれの子孫側での個体・経路の独立資料照合が済んでいないので`PERSON_PATH_SOURCE_AUDIT_REQUIRED`のまま残した。
- **JRDB canonical ancestor IDの追加確定は0**。JBISで外部個体IDが分かっても、JRDB 8桁の本人IDは発行・推測しない。
- 正式なJRDB⇔JBIS child-person crosswalkも**0件（承認前）**。親子出典は外部で裏付けられたものの、正式なJRDB祖先経路と認証したものではない。
- すべて`AS_OF_UNVERIFIED`、`prediction_safe=false`。血統適性・国ルーツの証明には使わない。

## 2. 個別出典と登録対象

4祖先のsource-native identity:
- サンデーサイレンス：JBIS `0000333862` https://www.jbis.jp/horse/0000333862/ （工程②に既登録）。
- ウインドインハーヘア：JBIS `0000430846` https://www.jbis.jp/horse/0000430846/ 。
- キングマンボ：JBIS `0000347989` https://www.jbis.jp/horse/0000347989/ （工程②に既登録）。
- マンファス：JBIS `0000440324` https://www.jbis.jp/horse/0000440324/ 。

| 子孫側の馬 | JBIS出典 | 4祖先への外部資料上の位置 | 登録済み経路数 |
|---|---|---|---:|
| ディープインパクト | https://www.jbis.jp/horse/0000742976/ | `S` Sunday Silence、`D` Wind in Her Hair | 2 |
| キングカメハメハ | https://www.jbis.jp/horse/0000729458/ | `S` Kingmambo、`D` Manfath | 2 |
| キズナ | https://www.jbis.jp/horse/0001120570/ | `SS` Sunday Silence、`SD` Wind in Her Hair | 2 |
| ロードカナロア | https://www.jbis.jp/horse/0001089850/ | `SS` Kingmambo、`SD` Manfath | 2 |
| ダイワメジャー | https://www.jbis.jp/horse/0000725485/ | `S` Sunday Silence | 1 |
| ハーツクライ | https://www.jbis.jp/horse/0000722158/ | `S` Sunday Silence | 1 |
| ルーラーシップ | https://www.jbis.jp/horse/0001042049/ | `SS` Kingmambo、`SD` Manfath | 2 |
| **合計** | | | **12** |

ここに表示した`S/SS/SD/D`は**それぞれの種牡馬自身からの経路**。出走馬の父・母父起点に展開する場合は先頭へ`S`または`DS`を追加し、5代より先は対象外。母母ラインはまだ別工程。

**重要**：外部の個体ページが確認できても「JRDBの子孫profile→JBISの同一個体」が承認済みではないため、今回の12件は`EXTERNAL_PEDIGREE_CORROBORATED_JRDB_UNBOUND`。事前に確認していない残り36件へ、同じ人名を理由に一括展開しない。

## 3. 改善指標

| 指標 | 前回③-B | 今回 |
|---|---:|---:|
| JRDB収録の上位50頭入口profile | 37 | 37（不変） |
| 13海外種牡馬のJBIS入口profile | 13 | 13（不変） |
| 1代前のJRDB canonical ancestor-ID paths | 36/100 | **36/100（不変）** |
| 2代前のJRDB canonical ancestor-ID paths | 10/200 | **10/200（不変）** |
| 3代前のJRDB canonical ancestor-ID paths | 0/400 | **0/400（不変）** |
| 対象4祖先の名前観測枠 | 48 | 48 |
| 対象4祖先の外部資料で照合した経路 | 前回個別照合未集計 | **12/48** |
| 対象4祖先の経路監査待ち | — | **36/48** |
| JRDB⇔外部の承認済み本人ID crosswalk | 0 | **0** |

**12/48=25%は4祖先の名前観測枠を分母にした外部経路照合率であり、全出走馬の血統充足率ではない。**

## 4. リポジトリ成果物

- `taxonomy/stage3b_priority4_bridge_candidate_v0_2.json`：外部ID4祖先、JBIS子孫馬7profile、12 pathの親子出典、本人対応の未承認状態。
- `src/brdb_stage3b_priority_bridge.py`：上位50頭研究JSONと外部出典レジストリを比較し、照合済み・要監査の名前経路を区分。勝手にJRDB person-IDを作らない。
- `tests/test_brdb_stage3b_priority_bridge.py`：10件の合成回帰テスト。現時点でGitHub正本に登録したが、**Pythonテストの実行結果は別途確認するまで未実行**。
- `stage3b_priority4_bridge_local_audit.json`：ローカルの既存50頭研究JSONを使った独立経路集計結果。SHA256 `4b57b109e185544b0435c3380036cf907d2622e94e659dca80bd80dc399b053b`。**このローカル監査はGitHubに新規登録したPythonモジュールそのもののE2E PASSではない**。

## 5. 次の最適化対象

高影響のまま未解決の子孫経路: サンデーサイレンスの他の`S/SS/DSS`、ウインドインハーヘアの`SD/DDD`、Kingmambo/Manfathの`SS/SD/SSS/SSD`などを、頻出順に子孫本人のJBIS血統ページを個別照合する。個別同一性に使えるJRDB外部共通IDが正式に得られたら、別の承認済みcrosswalkへ移して正式IDグラフを再計測。

本研究の結果をBRDB CURRENT、凍結Review、RaceNote/PWA、新聞、本番workflowへ接続しない。①〜③ ＞ ④ ≫ ⑥⑦を保持。
