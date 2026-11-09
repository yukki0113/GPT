# P1-A0 synthetic contract probe

**架空データのみ**で動くカードID／MDレアリティ出典／禁止制限／UNKNOWNの検証器です。

Run from master-duel/p1_a0:

    python -m unittest discover -s tests -v

公開Gitに実カード原文・所持情報は保存しません。Drive原本の取得・変換、公式MD情報の保証、デッキ生成は行いません。
名前やパスコード別画像は論理カードのキーとしません。非公式禁止制限はゲーム内確認前に合法性として確定しません。
本ツールは標準Pythonのみで動作しDuckDB/Parquetを利用しないため、共有data-storage基盤への変更はありません。
P0-C公式ゲーム画面30件の検証は未実施、P1-A1はNO-GOを維持します。
