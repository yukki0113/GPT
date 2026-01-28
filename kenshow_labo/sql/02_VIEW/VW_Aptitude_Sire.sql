CREATE OR ALTER VIEW dbo.VW_Aptitude_Sire AS
WITH SireOffspringResults AS (
    SELECT 
          p.sire
        , ra.ability_idx
        , rr.jyo_cd
        , CASE WHEN rr.baba_siba_cd <> '0' THEN '1' ELSE '2' END AS surface_type_cd
        , CASE 
            WHEN rr.distance_m < 1400 THEN 'S'
            WHEN rr.distance_m < 1900 THEN 'M'
            WHEN rr.distance_m < 2400 THEN 'I'
            ELSE 'L'
          END AS dist_category
    FROM dbo.TR_RaceAnalysis ra
    JOIN dbo.TR_RaceResult rr ON ra.race_id = rr.race_id AND ra.horse_id = rr.horse_id
    JOIN dbo.MT_HorsePedigree p ON ra.horse_id = p.horse_id -- マスタから父を取得
),
SireBase AS (
    SELECT sire, AVG(ability_idx) AS avg_sire_all FROM SireOffspringResults GROUP BY sire
)
SELECT 
      sor.sire AS sire_name
    , sor.jyo_cd
    , sor.surface_type_cd
    , sor.dist_category
    , COUNT(*) AS sire_run_count
    , AVG(sor.ability_idx) - MAX(sb.avg_sire_all) AS sire_aptitude_score
FROM SireOffspringResults sor
JOIN SireBase sb ON sor.sire = sb.sire
GROUP BY sor.sire, sor.jyo_cd, sor.surface_type_cd, sor.dist_category;