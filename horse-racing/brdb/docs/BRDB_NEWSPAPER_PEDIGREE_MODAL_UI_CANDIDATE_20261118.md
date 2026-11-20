# BRDB × Newspaper 「血統」モーダル UI契約 v0.1 候補（2026-11-18）

状態：**PWA UI試作・研究用、BRDB M7実データの公開結合は未実施**。予想印やRaceNoteのロジックには影響させない。個人版と桃太郎版の両新聞ページで同じ馬名欄を使う。

## 画面
- 各馬の馬名マス右下に小型 **「血統」** ボタン。固定幅のsticky列から横スクロール中も操作できる。
- 押下すると既存の過去走詳細とは別の、スマホ内でスクロール可能な `<dialog>` を開く。閉じるボタン、ブラウザ標準のEsc、背面モーダル化。必ず `(horse_no, horse_id)` の完全一致で対象馬を探す。馬名による結合は禁止。
- 構成順：基本血統（馬名／父／母／母父）、クロス・系統、今回の条件と血統実績、BRDB血統レビュー、母方近親、馬券検討Tips、注意書き。
- 基本血統は **既存Newspaper `horses[].basic`** が正本。M7が未接続でも閲覧可能。欠損は「未取得」、明細は「未接続」と明示し、空欄を肯定・否定評価としない。
- 馬券Tipsは「何を確認するか」を提示する根拠付きチェック項目で、買い推奨・確率・自信度・血統スコアにはしない。サンプル数と競馬場/コース/距離の説明を優先する。

## データ契約候補（未生産）

将来Newspaper上の **オプション** `horses[].addons.brdb_pedigree_display` を受け取る案。現在の日次Newspaper生成器はこれを出力せず、BRDB M7自身もこの契約の生産器を持たない。実データが生成されるまでは画面のレビュー欄が未接続と表示される。

追加の閲覧専用候補の識別子：`brdb-newspaper-pedigree-display-v0.1-candidate`。画面は次の保護条件をすべて満たすときだけ候補本文を表示する：

- `contract_version`固定、`release_status=RESEARCH_PREVIEW_ONLY`
- `research_only=true`、`prediction_safe=false`、`production_authorized=false`、`as_of_status=AS_OF_UNVERIFIED`
- `race_key`、8桁の`horse_id`、整数の`horse_no`が現在のNewspaper JSONと一致
- `source_sha256`が64桁hexであること（値の存在形式チェックであって、この画面単独では入力原本の再ハッシュではない）
- `score=null`、`rank=null`、`probability=null`を必須にする

子項目は `crosses:[{ancestor,pattern}]`、`condition_records:[{label,starts,wins,top3,status,source_label}]`、`reviews:[{category,text,status,evidence_label}]`、`relatives:[{name,relationship,note}]`、`tips:[{kind:'CHECK',text,evidence_label}]` を予定。各textはHTMLとして解釈せずエスケープする。産駒実績の統計は0走を0%と表示せず「算出対象なし」、今回の馬自体の好走確率へ変換しない。

この候補は**将来の明示的なadapter＋JSON Schema検証の叩き台**であり、現状で公開JSONの契約に昇格しない。元のM7 `brdb-m7-research-consumer-preview-v0.1` は根拠の状態・件数のみを持つため、これを根拠数値・クロス・Tipsに直接置き換えてはならない。クロスの世代判定、母方近親の競走実績、父/母父の条件別数字等はソースを確認した別工程で接続する。

## 実装境界
- `horse-racing/jrdb/pwa/newspaper-blood.js` と `newspaper-blood.css` が画面要素を所有。v4馬名セルのHTML関数だけ装飾し、印列・予想・過去走・短評を変更しない。
- 個人版 `pwa/newspaper.html` と桃太郎版 `pwa/momotaro/newspaper.html` が同じJS/CSSを読み込む。PWA Service Workerにはオフライン用に明示的に追加。
- 既存の `newspaper-detail-dialog` （過去走詳細）は改変せず、新しい `newspaper-blood-dialog` を分離。
- 研究用血統データが未接続の時点では **基本血統＋未取得表示のみが実運用可能**。①〜④のレビュー、クロス、コース数字、個別Tipsを架空に生成しない。
- 公開本番へのアップロード、BRDB `CURRENT`、日次生成・発行処理、RaceNoteの印やConfidenceの更新は本PRの対象外。

## 受入観点
1. 個人/桃太郎の新聞ページ両方に馬名マス右下ボタン・モーダル要素がある。
2. 馬名/父/母/母父を既存basicから表示し、欠損は未取得。HTML混入はエスケープ。
3. 根拠がないときはレビュー・クロス・コース・近親を未接続と表示。
4. 将来アドオンの契約・馬ID・レース・研究限定フラグが不一致なら拒否して基本情報のみに戻る。
5. 未検証の統計から印・馬券推奨・確率・スコアを作らない。
6. 既存の過去走モーダル、印、RaceNote、Eval/Iluka/RRDB/Momotaroを変えない。
7. Service Workerが新JS/CSSをオフラインシェルに入れる。
8. 次工程：研究用M7の①〜④成果からこのパネル契約に安全に変換するadapter、クロスの根拠供給、実18頭によるJSON/画面契約テスト、端末UIレビューを経て本番公開可否を別に判断する。
