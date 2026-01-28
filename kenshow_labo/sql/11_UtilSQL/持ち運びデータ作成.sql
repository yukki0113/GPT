/* =========================================================
   ミニデータ抽出（TRベース）
   - 起点：Aレース（race_id 3本）
   - 追加：A条件に近い過去レース（条件ごと最大30レース）
   - 追加：A上位想定 6～8頭（人気順）× 直近5走
   - 出力：
     1) TR_RaceResult（最終race_id集合）
     2) TR_Payout（最終race_id集合）
     3) MT_HorsePedigree（対象horse_id集合：上位想定馬）
     4) race_id一覧（確認用）
   ========================================================= */

SET NOCOUNT ON;

DECLARE @TopHorsesPerRace INT = 8;   -- A各レースの上位想定頭数（6～8想定）
DECLARE @PastRunsPerHorse INT = 5;   -- 各馬の直近走数
DECLARE @NearRacesPerCond INT = 30;  -- 条件ごとの追加レース数（A条件に近い過去レース）

/* 既存があれば掃除 */
IF OBJECT_ID('tempdb..#SeedRaceIds') IS NOT NULL DROP TABLE #SeedRaceIds;
IF OBJECT_ID('tempdb..#RaceBase') IS NOT NULL DROP TABLE #RaceBase;
IF OBJECT_ID('tempdb..#SeedCondKey') IS NOT NULL DROP TABLE #SeedCondKey;
IF OBJECT_ID('tempdb..#NearRaces') IS NOT NULL DROP TABLE #NearRaces;
IF OBJECT_ID('tempdb..#TopHorses') IS NOT NULL DROP TABLE #TopHorses;
IF OBJECT_ID('tempdb..#RecentRuns') IS NOT NULL DROP TABLE #RecentRuns;
IF OBJECT_ID('tempdb..#AllRaceIds') IS NOT NULL DROP TABLE #AllRaceIds;
IF OBJECT_ID('tempdb..#TargetHorseIds') IS NOT NULL DROP TABLE #TargetHorseIds;

/* ---------------------------------------------------------
   1) 起点：ターゲットレースA（race_idを入れる）
   --------------------------------------------------------- */
CREATE TABLE #SeedRaceIds
(
    race_id CHAR(12) NOT NULL PRIMARY KEY
);

-- TODO: ここをあなたのA(3レース)に差し替え
INSERT INTO #SeedRaceIds (race_id)
VALUES
    ('202509280611') -- スプリンターズステークス
  , ('202506010511') -- 東京優駿
  , ('202502230511') -- フェブラリーステークス
;

/* ---------------------------------------------------------
   2) レース単位の基礎情報（TR_RaceResultは馬単位行なので集約する）
      surface_type は baba_*_cd から推定（芝/ダ）
      distance_band は 200m刻み
   --------------------------------------------------------- */
CREATE TABLE #RaceBase
(
      race_id        CHAR(12) NOT NULL PRIMARY KEY
    , race_date      DATE     NOT NULL
    , ymd            CHAR(8)  NOT NULL
    , jyo_cd         CHAR(2)  NOT NULL
    , race_no        TINYINT  NOT NULL
    , track_cd       CHAR(2)  NULL
    , distance_m     INT      NULL
    , distance_band  INT      NULL
    , surface_type   NVARCHAR(10) NULL
);

INSERT INTO #RaceBase
(
    race_id, race_date, ymd, jyo_cd, race_no, track_cd, distance_m, distance_band, surface_type
)
SELECT
      rr.race_id
    , MIN(rr.race_date) AS race_date
    , MIN(rr.ymd)       AS ymd
    , MIN(rr.jyo_cd)    AS jyo_cd
    , MIN(rr.race_no)   AS race_no
    , MIN(rr.track_cd)  AS track_cd
    , MIN(rr.distance_m) AS distance_m
    , CASE
          WHEN MIN(rr.distance_m) IS NULL THEN NULL
          ELSE CAST(ROUND(CAST(MIN(rr.distance_m) AS FLOAT) / 200.0, 0) * 200 AS INT)
      END AS distance_band
    , CASE
          WHEN MAX(CASE WHEN rr.baba_siba_cd IS NOT NULL THEN 1 ELSE 0 END) = 1
               AND MAX(CASE WHEN rr.baba_dirt_cd IS NOT NULL THEN 1 ELSE 0 END) = 0
              THEN N'芝'
          WHEN MAX(CASE WHEN rr.baba_dirt_cd IS NOT NULL THEN 1 ELSE 0 END) = 1
               AND MAX(CASE WHEN rr.baba_siba_cd IS NOT NULL THEN 1 ELSE 0 END) = 0
              THEN N'ダ'
          ELSE NULL
      END AS surface_type
FROM dbo.TR_RaceResult rr
GROUP BY rr.race_id;

/* ---------------------------------------------------------
   3) A条件キー（jyo_cd × surface_type × distance_band）を作る
      ※同条件のAが複数ある場合、max_seed_date を上限に過去レースを集める
   --------------------------------------------------------- */
CREATE TABLE #SeedCondKey
(
      jyo_cd        CHAR(2) NOT NULL
    , surface_type  NVARCHAR(10) NOT NULL
    , distance_band INT NOT NULL
    , max_seed_date DATE NOT NULL
    , CONSTRAINT PK_SeedCondKey PRIMARY KEY (jyo_cd, surface_type, distance_band)
);

INSERT INTO #SeedCondKey (jyo_cd, surface_type, distance_band, max_seed_date)
SELECT
      rb.jyo_cd
    , rb.surface_type
    , rb.distance_band
    , MAX(rb.race_date) AS max_seed_date
FROM #RaceBase rb
INNER JOIN #SeedRaceIds s
    ON s.race_id = rb.race_id
WHERE rb.surface_type IS NOT NULL
  AND rb.distance_band IS NOT NULL
GROUP BY
      rb.jyo_cd
    , rb.surface_type
    , rb.distance_band;

/* ---------------------------------------------------------
   4) A条件に近い過去レース（条件ごと最大30）
      - 未来リーク防止：race_date < max_seed_date
      - Aレースそのものは除外
   --------------------------------------------------------- */
CREATE TABLE #NearRaces
(
    race_id CHAR(12) NOT NULL PRIMARY KEY
);

WITH Cand AS
(
    SELECT
          rb.race_id
        , rb.race_date
        , rb.jyo_cd
        , rb.surface_type
        , rb.distance_band
    FROM #RaceBase rb
    WHERE rb.surface_type IS NOT NULL
      AND rb.distance_band IS NOT NULL
),
Ranked AS
(
    SELECT
          c.race_id
        , ROW_NUMBER() OVER
          (
              PARTITION BY c.jyo_cd, c.surface_type, c.distance_band
              ORDER BY c.race_date DESC
          ) AS rn
    FROM Cand c
    INNER JOIN #SeedCondKey k
        ON k.jyo_cd = c.jyo_cd
       AND k.surface_type = c.surface_type
       AND k.distance_band = c.distance_band
    WHERE c.race_date < k.max_seed_date
      AND NOT EXISTS (SELECT 1 FROM #SeedRaceIds s WHERE s.race_id = c.race_id)
)
INSERT INTO #NearRaces (race_id)
SELECT r.race_id
FROM Ranked r
WHERE r.rn <= @NearRacesPerCond;

/* ---------------------------------------------------------
   5) Aレースの上位想定馬（人気が小さい順で最大8頭）
      - TR_RaceResult の popularity を使用
   --------------------------------------------------------- */
CREATE TABLE #TopHorses
(
      race_id  CHAR(12) NOT NULL
    , horse_id CHAR(10) NOT NULL
    , CONSTRAINT PK_TopHorses PRIMARY KEY (race_id, horse_id)
);

WITH RankHorses AS
(
    SELECT
          rr.race_id
        , rr.horse_id
        , rr.popularity
        , rr.horse_no
        , ROW_NUMBER() OVER
          (
              PARTITION BY rr.race_id
              ORDER BY
                  CASE WHEN rr.popularity IS NULL THEN 9999 ELSE rr.popularity END ASC,
                  rr.horse_no ASC
          ) AS rn
    FROM dbo.TR_RaceResult rr
    INNER JOIN #SeedRaceIds s
        ON s.race_id = rr.race_id
    WHERE rr.horse_id IS NOT NULL
      AND LTRIM(RTRIM(rr.horse_id)) <> ''
)
INSERT INTO #TopHorses (race_id, horse_id)
SELECT
      rh.race_id
    , rh.horse_id
FROM RankHorses rh
WHERE rh.rn <= @TopHorsesPerRace;

/* ---------------------------------------------------------
   6) 上位想定馬の直近5走（B）を race_id 単位で集める
      - Aレースは除外
      - 同一日複数出走は通常無い想定だが、race_dateで降順
   --------------------------------------------------------- */
CREATE TABLE #RecentRuns
(
    race_id CHAR(12) NOT NULL PRIMARY KEY
);

WITH HorseRuns AS
(
    SELECT
          rr.horse_id
        , rr.race_id
        , rr.race_date
        , ROW_NUMBER() OVER
          (
              PARTITION BY rr.horse_id
              ORDER BY rr.race_date DESC
          ) AS rn
    FROM dbo.TR_RaceResult rr
    WHERE EXISTS (SELECT 1 FROM #TopHorses th WHERE th.horse_id = rr.horse_id)
      AND NOT EXISTS (SELECT 1 FROM #SeedRaceIds s WHERE s.race_id = rr.race_id)
)
INSERT INTO #RecentRuns (race_id)
SELECT DISTINCT
    hr.race_id
FROM HorseRuns hr
WHERE hr.rn <= @PastRunsPerHorse;

/* ---------------------------------------------------------
   7) 最終 race_id 集合（A + 近傍 + B）
   --------------------------------------------------------- */
CREATE TABLE #AllRaceIds
(
    race_id CHAR(12) NOT NULL PRIMARY KEY
);

INSERT INTO #AllRaceIds (race_id)
SELECT race_id FROM #SeedRaceIds
UNION
SELECT race_id FROM #NearRaces
UNION
SELECT race_id FROM #RecentRuns;

/* 対象horse_id集合（血統抽出用）
   ※ここは「A上位想定馬」に限定（軽量化）
*/
CREATE TABLE #TargetHorseIds
(
    horse_id CHAR(10) NOT NULL PRIMARY KEY
);

INSERT INTO #TargetHorseIds (horse_id)
SELECT DISTINCT th.horse_id
FROM #TopHorses th;

/* =========================================================
   出力1：TR_RaceResult（そのままCSV化 → ノート側へ取込可）
   ========================================================= */
SELECT
    rr.*
FROM dbo.TR_RaceResult rr
WHERE EXISTS (SELECT 1 FROM #AllRaceIds a WHERE a.race_id = rr.race_id)
ORDER BY rr.race_date, rr.race_id, rr.horse_no;

/* =========================================================
   出力2：TR_Payout（そのままCSV化 → ノート側へ取込可）
   ※単勝/複勝のみでもOK。AllRaceIdsでまとめて抜く
   ========================================================= */
SELECT
    p.*
FROM dbo.TR_Payout p
WHERE EXISTS (SELECT 1 FROM #AllRaceIds a WHERE a.race_id = p.race_id)
ORDER BY p.race_id, p.bet_type, p.horse_no_1, p.horse_no_2, p.horse_no_3;

/* =========================================================
   出力3：MT_HorsePedigree（上位想定馬ぶん）
   ※対象horse_idがMTに無い場合もあり得るので LEFT JOIN にしてもOK
   ========================================================= */
SELECT
    hp.*
FROM dbo.MT_HorsePedigree hp
WHERE EXISTS (SELECT 1 FROM #TargetHorseIds h WHERE h.horse_id = hp.horse_id)
ORDER BY hp.horse_id;

/* =========================================================
   出力4：確認用（最終race_id一覧 + 件数）
   ========================================================= */
SELECT a.race_id
FROM #AllRaceIds a
ORDER BY a.race_id;

SELECT
      (SELECT COUNT(1) FROM #SeedRaceIds)     AS seed_races
    , (SELECT COUNT(1) FROM #NearRaces)       AS near_races
    , (SELECT COUNT(1) FROM #RecentRuns)      AS recent_run_races
    , (SELECT COUNT(1) FROM #AllRaceIds)      AS total_races
    , (SELECT COUNT(1) FROM #TargetHorseIds)  AS target_horses;
