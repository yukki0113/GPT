CREATE OR ALTER VIEW dbo.VW_HorseStyleFixed_N5
AS
WITH R AS
(
    SELECT
          v.horse_id
        , CASE
              WHEN v.[脚質] LIKE N'%逃%' THEN N'逃げ'
              WHEN v.[脚質] LIKE N'%先%' THEN N'先行'
              WHEN v.[脚質] LIKE N'%差%' THEN N'差し'
              WHEN v.[脚質] LIKE N'%追%' THEN N'追込'
              WHEN v.[脚質] LIKE N'%まく%' OR v.[脚質] LIKE N'%捲%' THEN N'差し'
              ELSE NULL
          END AS style4
        , ROW_NUMBER() OVER (PARTITION BY v.horse_id ORDER BY v.[日付] DESC, v.race_id DESC) AS rn
    FROM dbo.VW_RaceResultContract v
    WHERE v.horse_id IS NOT NULL
      AND v.[脚質] IS NOT NULL
      AND v.[日付] IS NOT NULL
),
L AS
(
    SELECT horse_id, style4, rn
    FROM R
    WHERE rn <= 5
      AND style4 IS NOT NULL
),
A AS
(
    SELECT
          horse_id
        , style4
        , COUNT(1) AS cnt
        , MIN(rn) AS best_rn  -- 同数なら直近（rn小）を優先
    FROM L
    GROUP BY horse_id, style4
),
P AS
(
    SELECT
          horse_id
        , style4
        , ROW_NUMBER() OVER (PARTITION BY horse_id ORDER BY cnt DESC, best_rn ASC) AS pick
    FROM A
)
SELECT
    horse_id,
    style4 AS style_fixed
FROM P
WHERE pick = 1;
GO
