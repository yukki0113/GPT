SELECT TOP (200)
    v.horse_id, v.馬名, v.race_id, v.[日付], v.[着順], v.[頭数]
FROM dbo.VW_RaceResultContract v
CROSS APPLY (SELECT TRY_CONVERT(INT, v.[着順]) AS f, TRY_CONVERT(INT, v.[頭数]) AS n) x
WHERE x.f IS NULL OR x.n IS NULL
   OR x.n NOT BETWEEN 5 AND 18
   OR x.f NOT BETWEEN 1 AND x.n
ORDER BY v.[日付] DESC, v.race_id DESC;
