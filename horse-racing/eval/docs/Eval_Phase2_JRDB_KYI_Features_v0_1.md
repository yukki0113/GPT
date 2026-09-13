# Eval Phase2 JRDB KYI Features v0.1

Status: **SUPERSEDED**

この文書は初期KYI特徴量contractの履歴です。現行実装 `horse-racing/eval/src/build_phase2_jrdb_kyi_features.py` は `VERSION = 0.2.0` であり、出力schemaも拡張されています。

現行正本:

```text
horse-racing/eval/docs/Eval_Phase2_JRDB_KYI_Features_v0_2.md
horse-racing/eval/src/build_phase2_jrdb_kyi_features.py
horse-racing/eval/tests/test_build_phase2_jrdb_kyi_features.py
```

v0.2ではv0.1項目に加えて、厩舎系判断、予想ペース、展開予測index/rank、スタート/出遅れ関連の開催前KYI fieldを保持します。

過去成果物のschemaを確認する目的以外では、本v0.1を現行出力contractとして使用しないでください。
