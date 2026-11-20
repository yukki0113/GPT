# BRDB → Newspaper 血統モーダル private research projection v0.1 candidate — 2026-11-20

**PRIVATE RESEARCH PREVIEW ONLY / NO NEWSPAPER MUTATION / NO PWA PUBLICATION**

## Purpose

PR #2655 で受入済みの private v0.6 馬場4状態・父/母父/配合観測と、M7 private 近親詳細を、PR #2643 の optional `addons.brdb_pedigree_display` UI guard が読める候補形へ投影する。

この段階では Newspaper JSON へ書き込まない。RaceNote、BRDB CURRENT、公開PWA、新聞日次生成、印、Confidence は変更しない。

## Source

- `brdb-going-multilane-discovery-v0.6-candidate`
- `brdb-m7-relatives-detail-v0.1-candidate`
- exact `(horse_no, horse_id)` join only
- relative historical as-of remains `AS_OF_UNVERIFIED`

## Output

`src/brdb_newspaper_pedigree_display_projection.py` は private JSON を出力する。

各馬レコードは UI candidate contract:

`brdb-newspaper-pedigree-display-v0.1-candidate`

に合わせるが、以下を固定する。

- `release_status=RESEARCH_PREVIEW_ONLY`
- `prediction_safe=false`
- `production_authorized=false`
- `as_of_status=AS_OF_UNVERIFIED`
- `score/rank/probability=null`
- `crosses=[]`
- `reviews=[]`
- `tips=[]`

v0.6 の natural-language review は未許可なので、レビュー文や適性結論を生成しない。condition records は primary observation の state-side `starts/wins/top3` をそのまま記述統計として載せるだけで、方向やtierは source label に provenance として残す。

M7 relatives は private detail の名前・relationship と5 scope cellの単純合計を表示候補へ投影する。ただし scope は重複するため、note に「scope重複あり」を明記する。合計は独立標本・馬場状態別近親実績・適性根拠ではない。

## Safety boundary

- Newspaperへのmergeは未実装
- PWA/Pages publicationなし
- actual device visual acceptanceなし
- user-facing wording graduationなし
- suitability / causal / independent-support claimなし
- betting recommendationなし
- private horse-level JSONをGit/公開Actions artifactへ保存しない

## Next acceptance

1. private fixed race `05265412` で projection を2回実行し byte-identical を確認
2. Draft 2020-12 schema validation
3. PR #2643 の `NewspaperBloodPanel.candidate()` guard と実データ projection の互換テスト
4. 実新聞18頭への **private in-memory attach only** で canonical identity / other-addon non-interference を監査
5. その後に限り、ユーザー表示レビューと production graduation を別gateで判断

本projectionの完成は M7 H の graduation ではない。
