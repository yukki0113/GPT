-- 集計確認用

-- A) mult がクリップに張り付いていないか（偏りチェック）
SELECT
    'Course' AS kind,
    SUM(CASE WHEN mult = 0.85 THEN 1 ELSE 0 END) AS at_min,
    SUM(CASE WHEN mult = 1.15 THEN 1 ELSE 0 END) AS at_max,
    COUNT(*) AS total
FROM dbo.ST_CoursePlace
UNION ALL
SELECT
    'Frame',
    SUM(CASE WHEN mult = 0.85 THEN 1 ELSE 0 END),
    SUM(CASE WHEN mult = 1.15 THEN 1 ELSE 0 END),
    COUNT(*)
FROM dbo.ST_FramePlace
UNION ALL
SELECT
    'Style',
    SUM(CASE WHEN mult = 0.85 THEN 1 ELSE 0 END),
    SUM(CASE WHEN mult = 1.15 THEN 1 ELSE 0 END),
    COUNT(*)
FROM dbo.ST_StylePlace
UNION ALL
SELECT
    'Blood',
    SUM(CASE WHEN mult = 0.85 THEN 1 ELSE 0 END),
    SUM(CASE WHEN mult = 1.15 THEN 1 ELSE 0 END),
    COUNT(*)
FROM dbo.ST_BloodSirePlace
UNION ALL
SELECT
    'Jockey',
    SUM(CASE WHEN mult = 0.85 THEN 1 ELSE 0 END),
    SUM(CASE WHEN mult = 1.15 THEN 1 ELSE 0 END),
    COUNT(*)
FROM dbo.ST_JockeyPlace;

-- B) n（母数）が極端に小さいキーがどれだけあるか（信頼度チェック）
SELECT 'Blood' AS kind,
       SUM(CASE WHEN n < 10 THEN 1 ELSE 0 END) AS n_lt_10,
       SUM(CASE WHEN n < 30 THEN 1 ELSE 0 END) AS n_lt_30,
       SUM(CASE WHEN n < 50 THEN 1 ELSE 0 END) AS n_lt_50,
       COUNT(*) AS total
FROM dbo.ST_BloodSirePlace
UNION ALL
SELECT 'Jockey',
       SUM(CASE WHEN n < 10 THEN 1 ELSE 0 END),
       SUM(CASE WHEN n < 30 THEN 1 ELSE 0 END),
       SUM(CASE WHEN n < 50 THEN 1 ELSE 0 END),
       COUNT(*)
FROM dbo.ST_JockeyPlace;

-- C) mult の分布をざっくり見る（妥当性の肌感）
SELECT TOP (20) *
FROM dbo.ST_CoursePlace
ORDER BY mult DESC;

SELECT TOP (20) *
FROM dbo.ST_CoursePlace
ORDER BY mult ASC;
