# JRDB Common Reader Index Migration Phase 3

## 目的
PWA/index-base builder に残る固定長 offset の重複実装を段階的に Common JRDB Reader (`src/jrdb_raw.py`) へ集約する。

## 対象
- `build_jrdb_index_base_from_raw.py::parse_sed`
- `build_jrdb_index_base_from_raw.py::parse_cha`
- `build_jrdb_index_base_from_raw.py::parse_cyb`

BAC/KYI はすでに `jrdb_index_base_adapter.py` 経由で Common Reader へ切替済み。

## 方針
1. `jrdb_index_base_adapter.py` に `parse_sed`, `parse_cha`, `parse_cyb` の adapter を追加する。
2. adapter 内に固定長 offset を新規記述しない。byte-position ownership は `jrdb_raw.Parser` のみとする。
3. 現行 `build_jrdb_index_base_from_raw.py` の parse_sed/cha/cyb を Legacy oracle として一時保持する。
4. synthetic fixture に対して adapter と Legacy の parsed output を完全一致比較する characterization test を追加する。
5. SED は result / result_context / BAC-missing fallback の3返却値すべて一致させる。
6. CHA/CYB は provenance、型、null/blank semantics を含めて一致させる。
7. equivalence test 通過後に production binding を adapter へ切り替える。
8. schema・feature・metric・PWA DB contract は変更しない。

## 追加検証
- 2024 annual Raw からランダム抽出した SED/CHA/CYB 各100 records で Legacy vs adapter 完全一致。
- existing `test_build_jrdb_index_base_from_raw.py` を通す。
- `test_jrdb_index_base_adapter.py` に SED/CHA/CYB equivalence を追加。
- `jrdb_common_reader_tests.yml` か index-base CI に adapter test を含める。

## 完了条件
- fixed-width offset の実運用正本が `jrdb_raw.py` に集約される。
- index-base output の semantic regression 0。
- BAC/KYI/SED/CHA/CYB の production path が Common Reader 経由になる。
- Raw・生成DB・credential はcommitしない。
