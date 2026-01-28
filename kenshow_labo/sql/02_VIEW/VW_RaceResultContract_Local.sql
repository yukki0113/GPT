CREATE OR ALTER VIEW dbo.VW_RaceResultContract_Local
AS
WITH Base AS
(
    SELECT
          r.race_id
        , r.race_date
        , r.race_no
        , r.race_name
        , r.jyoken_name
        , r.win5_flg
        , r.jyo_cd
        , r.grade_cd
        , r.jyoken_syubetu_cd
        , r.jyoken_cd4
        , r.track_cd
        , r.distance_m
        , r.weather_cd
        , r.baba_siba_cd
        , r.baba_dirt_cd
        , r.frame_no
        , r.horse_no
        , r.horse_id
        , r.horse_name
        , r.sex_cd
        , r.age
        , r.jockey_name
        , r.carried_weight
        , r.popularity
        , r.odds
        , r.finish_time
        , r.horse_weight
        , r.horse_weight_diff
        , r.finish_pos
        , r.pos_c1
        , r.pos_c2
        , r.pos_c3
        , r.pos_c4
        , r.final_3f
        , COUNT(*) OVER (PARTITION BY r.race_id) AS head_count
    FROM dbo.TR_RaceResult AS r
)
SELECT
      b.race_id
    , b.race_date AS [日付]
    , b.race_name AS [レース名]
    , b.jyoken_name AS [クラス]
    , dgrade.[text] AS [グレード]
    , b.win5_flg AS WIN5_flg

    , dcourse.[text] AS [場名]
    , CAST(b.distance_m AS SMALLINT) AS [距離]

    -- 従来通り：芝/ダは馬場CDの有無（0以外）で判定
    , CASE
        WHEN b.baba_siba_cd IS NOT NULL
         AND b.baba_siba_cd <> N'0'
            THEN N'芝'
        WHEN b.baba_dirt_cd IS NOT NULL
         AND b.baba_dirt_cd <> N'0'
            THEN N'ダ'
        ELSE
            NULL
      END AS [芝/ダ]

    , b.frame_no AS [枠番]
    , b.horse_no AS [馬番]
    , b.horse_id
    , b.horse_name AS [馬名]
    , dsex.[text] AS [性]
    , b.age AS [齢]
    , b.jockey_name AS [騎手]
    , b.carried_weight AS [斤量]
    , b.popularity AS [人気]
    , b.odds AS [オッズ]
    , b.finish_time AS [走破時計]
    , b.horse_weight AS [馬体重]
    , b.horse_weight_diff AS [馬体重変動]
    , b.finish_pos AS [着順]
    , b.pos_c1 AS [通過順_1角]
    , b.pos_c2 AS [通過順_2角]
    , b.pos_c3 AS [通過順_3角]
    , b.pos_c4 AS [通過順_4角]
    , b.final_3f AS [上がり]
    , dweather.[text] AS [天気]
    , CASE
        WHEN b.baba_siba_cd IS NOT NULL
         AND b.baba_siba_cd <> N'0'
            THEN db_siba.[text]
        WHEN b.baba_dirt_cd IS NOT NULL
         AND b.baba_dirt_cd <> N'0'
            THEN db_dirt.[text]
        ELSE
            NULL
      END AS [馬場]
    , p.horse_name AS [血統馬名]
    , p.sire       AS [父]
    , p.dam        AS [母]
    , p.dam_sire   AS [母父]
    , p.dam_dam    AS [母母]
    , p.sire_sire  AS [父父]
    , p.sire_dam   AS [父母]
    , b.head_count AS [頭数]
    , CASE
          WHEN b.pos_c1 IS NOT NULL
           AND b.pos_c2 IS NOT NULL
           AND b.pos_c3 IS NOT NULL
           AND b.pos_c4 IS NOT NULL
           AND b.pos_c2 > FLOOR(b.head_count * 2.0 / 3.0)
           AND b.pos_c4 <= 2
              THEN N'まくり'
          WHEN b.pos_c4 IS NULL
              THEN N'不明'
          WHEN b.pos_c4 <= 2
              THEN N'逃げ'
          WHEN b.pos_c4 <= FLOOR(b.head_count / 3.0)
              THEN N'先行'
          WHEN b.pos_c4 <= FLOOR(b.head_count * 2.0 / 3.0)
              THEN N'差し'
          ELSE N'追い込み'
      END AS [脚質]
    , sp.payout_amount AS [単勝払戻]
    , sp.popularity    AS [単勝人気]
    , fp.payout_amount AS [複勝払戻]
    , fp.popularity    AS [複勝人気]

    -- 集計用コード（末尾）
    , b.race_no           AS race_no
    , b.jyo_cd            AS jyo_cd
    , b.grade_cd          AS grade_cd
    , b.jyoken_syubetu_cd AS jyoken_syubetu_cd
    , b.jyoken_cd4        AS jyoken_cd4
    , b.track_cd          AS track_cd
    , b.weather_cd        AS weather_cd
    , b.baba_siba_cd      AS baba_siba_cd
    , b.baba_dirt_cd      AS baba_dirt_cd
FROM Base AS b
LEFT JOIN dbo.MT_HorsePedigree AS p
    ON b.horse_id = p.horse_id
LEFT JOIN dbo.MT_CodeDictionary AS dcourse
    ON dcourse.code_type = N'RACE_COURSE'
   AND dcourse.code      = b.jyo_cd
   AND dcourse.is_active = 1
LEFT JOIN dbo.MT_CodeDictionary AS dweather
    ON dweather.code_type = N'WEATHER'
   AND dweather.code      = b.weather_cd
   AND dweather.is_active = 1
LEFT JOIN dbo.MT_CodeDictionary AS dsex
    ON dsex.code_type = N'SEX_CD'
   AND dsex.code      = b.sex_cd
   AND dsex.is_active = 1
LEFT JOIN dbo.MT_CodeDictionary AS dgrade
    ON dgrade.code_type = N'GRADE'
   AND dgrade.code      = b.grade_cd
   AND dgrade.is_active = 1
LEFT JOIN dbo.MT_CodeDictionary AS dclass
    ON dclass.code_type = N'RACE_CLASS'
   AND dclass.code      = b.jyoken_cd4
   AND dclass.is_active = 1
LEFT JOIN dbo.MT_CodeDictionary AS dtype
    ON dtype.code_type = N'RACE_TYPE'
   AND dtype.code      = b.jyoken_syubetu_cd
   AND dtype.is_active = 1
LEFT JOIN dbo.MT_CodeDictionary AS db_siba
    ON db_siba.code_type = N'BABA'
   AND db_siba.code      = b.baba_siba_cd
   AND db_siba.is_active = 1
LEFT JOIN dbo.MT_CodeDictionary AS db_dirt
    ON db_dirt.code_type = N'BABA'
   AND db_dirt.code      = b.baba_dirt_cd
   AND db_dirt.is_active = 1
LEFT JOIN dbo.TR_Payout AS sp
    ON  b.race_id   = sp.race_id
    AND b.horse_no  = sp.horse_no_1
    AND sp.bet_type = N'単勝'
LEFT JOIN dbo.TR_Payout AS fp
    ON  b.race_id   = fp.race_id
    AND b.horse_no  = fp.horse_no_1
    AND fp.bet_type = N'複勝'
WHERE
    dcourse.text_sub = N'LOCAL';
GO
