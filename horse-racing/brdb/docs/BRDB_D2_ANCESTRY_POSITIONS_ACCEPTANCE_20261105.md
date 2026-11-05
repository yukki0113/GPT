# BRDB D2 — 祖先の位置・世代・観測クロス抽出 v0.1

- Date: 2026-11-05
- Status: **RESEARCH IMPLEMENTATION COMMITTED / SOURCE READBACK VERIFIED / SYNTHETIC TESTS AUTHORED / NO FULL REAL-RACE E2E OR AS-OF ATTESTATION**
- Source: `../src/brdb_d2_ancestry_positions.py`
- Tests: `../tests/test_brdb_d2_ancestry_positions.py`
- Dependencies: `brdb_ancestor_graph.py`, `brdb_ancestor_evidence.py`, `brdb_d1_catalog.py`.
- ⑥⑦の役割: ①〜③ ＞ ④ ≫ ⑥⑦。⑤へは将来の非採点 `supplemental_insights` の根拠候補として供給する。レビュー文の生成・地域適性の認定はまだ行わない。

## 1. D2の処理と入出力

`from_relations(horse_id, relations_for, *, source_generation, target_date, source_profile_as_of=None, max_depth=5, candidate_catalogs=None)` は、既存 `ancestor_graph` だけで血統登録番号から父・母の**確定ID経路**をたどる。

`describe_positions(graph, *, source_generation, target_date, source_profile_as_of=None, candidate_catalogs=None)` は、canonical graphの情報を変更せず、以下を出力する。

- `ancestors` — `ancestor_horse_id`, `paths`, `generations`, `sides`, `roles`, `observed_occurrences`, `identity_binding`。
- `observed_crosses` — 同一canonical IDが2経路以上で出現した場合の `paths`, `generations`, `notation`（例: 3×4）。祖先名の偶然の一致ではクロスにしない。
- `generation_coverage` — 各世代の理論経路数（2^depth）とID確定済み/未解決経路数。
- `side_coverage` — 父側・母側の確定経路数、理論経路数、未知数。
- `complete` — 指定した `max_depth` までのすべての理論経路が確定した場合のみtrue。深さ2の完全性と深さ5の完全性は別。
- `no_observed_cross_absence_proven` — 指定範囲が**完全**かつ観測クロスゼロの場合だけtrue。
- `historical_asof_status` — 現段階では必ず `AS_OF_UNVERIFIED`。
- `candidate_catalog_status` — D1候補辞書を渡した場合 `D1_CANDIDATE_UNBOUND`。
- `candidate_bloodline_matches=[]`, `regional_root_assignments=[]`, `aptitude_claims=[]`。**ゼロ件は「内包血統なし」「適性なし」の意味ではない。** D1には確認済みのJRDB血統ID対応がないため名寄せしない。

機械的に `DS` は母の父（母父）、`S` は父、`D` は母、`SS` は父の父、`DSS` は母の父の父である。出力`roles`でも区別する。

## 2. 安全条件・制約

- 既存 `ancestor_graph` の解決済み `resolved_parent_horse_id` のみを使用。`resolution_status=RESOLVED_EXACT|RESOLVED_ALIAS` の場合だけIDの記録を採用。
- graph version、path文法、重複path、確定IDと解決statusの矛盾、未解決中間ノードより先の孤立path、resolved/expected数の矛盾、FULL宣言の整合性を拒否。
- 対象日より未来の `source_profile_as_of` はエラー。**過去の日付だけで全血統辺の配信時点が立証されるわけではない**。呼び出し元が `profile_timing_verified=True` と指定してもD2は拒否し、`prediction_safe=false` を固定する。
- D1辞書を入力したときは既存ガバナンスvalidatorで未承認状態を確認。未確認の祖先を名前・大系統・類似文字列からID推定しない。
- 祖先IDの観測結果は`CANONICAL_GRAPH_ONLY`。D1のHalo/Storm Cat/トニービン/Danzigと同じIDかどうかは、独立に監査したID対応表が導入されるまで`UNBOUND`。
- スコア、血統国籍、適性順位、出走馬の評価逆転、予想勝率、条件別着順集計、回収率は算出しない。
- 一部の祖先しか取れないとき、未解決経路を否定的証拠として扱わない。観測クロス数ゼロでも「クロスなし」は原則断定しない。

## 3. 合成回帰テスト（10件）

- `S`、`D`、`DS`、`SS` の経路・役割と同一ID複数経路。
- `SSS`/ `DSS` の同一祖先による観測3×3クロス、父側/母側混在。
- 5世代の部分グラフで全理論62経路のうち未知数を保持。母方31経路が不明なら0%扱いしない。
- 指定深さ1の完全性を別管理。
- D1候補ラベルからID・地域タグ・適性を捏造しない。
- 将来のプロフィール日付と自己申告の `profile_timing_verified` を拒否。
- 日付が正しくても歴史的な公開時点は未検証。
- 未解決IDを解決済みとする改ざん、途中経路の欠落を拒否。
- D1候補の無断昇格を拒否。

**今回のGitHub登録と読み戻しで新規ソース/テストの存在を確認したが、コミットされた10件のPythonテストはまだ実行検証を行っていない。** 実行済み・PASSとは表記しない。

## 4. 実行例

```python
from brdb_d2_ancestry_positions import from_relations
from brdb_d1_catalog import load_catalog

result = from_relations(
    horse_id="12345678",
    relations_for=reader.parent_relations,
    source_generation=verified_generation_id,
    target_date="2026-11-01",
    source_profile_as_of="2026-10-31",
    max_depth=5,
    candidate_catalogs=(
        load_catalog("horse-racing/brdb/taxonomy/regional_roots_candidate_v0_1.json"),
        load_catalog("horse-racing/brdb/taxonomy/embedded_blood_hypotheses_candidate_v0_1.json"),
    ),
)
```

上記は**接続方式の例**であり、架空IDを使って実レース実行済みという意味ではない。Readerが参照するgenerationとプロフィール日付の整合は呼び出し元で検証する必要がある。

```bash
python -m unittest discover -s horse-racing/brdb/tests -p test_brdb_d2_ancestry_positions.py -v
```

## 5. 残作業／D3へのゲート

1. 正式な祖先IDとD1血脈候補の対応表について、JRDB由来の一意ID・監査済み出典・配信時点を整備する。**名前のみの紐付けは不可**。
2. BRDB実際の`BloodReviewReader.parent_relations`を入力し、1レース全馬の深度別coverage、所要時間、ID一致品質を記録する。現状この検証は未実施。
3. ⑥の地域ルーツを複数保持する辞書をreviewed taxonomyとして採用するには独立のsource reviewが必要。
4. D3の条件別成績集計は、ancestor ID/role/pathに加えてas-of-safeな当時の情報とresult cohortを用意し、`prediction_safe`を別に検証する。
5. ⑤の候補Schema、Blood Review v0.1、BRDB CURRENT、RaceNote、PWA、Newspaperは今回変更しない。

**D2の達成範囲: IDで観測した位置・世代・クロスと未解決範囲の抽出まで。D1血脈名の自動検索や適性の検証ではない。**
