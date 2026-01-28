/* 【検証ラボ：汎用予測エンジン・最終確定版】
   - 重複排除：種牡馬適性を場所・距離で個別に集約し、行の増殖を防止。
   - 構文修正：WITH ... INSERT ... SELECT の順序を遵守。
*/
CREATE OR ALTER PROCEDURE dbo.usp_GetRacePrediction
    @race_id CHAR(12) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    -- 1. 物理テーブルのクリア
    IF @race_id IS NULL 
        TRUNCATE TABLE dbo.TR_RacePredictionResult;
    ELSE 
        DELETE FROM dbo.TR_RacePredictionResult WHERE race_id = @race_id;

    -- 2. メインロジック（CTE）
    WITH TargetEntries AS (
        /* 予測対象馬の特定 */
        SELECT 
              v.race_id, v.[日付] AS target_date, v.jyo_cd, v.surface_type AS surface_type_cd
            , v.[距離], v.horse_id, v.horse_name, v.frame_no, v.horse_no, v.[R], v.[クラス]
            , CASE 
                WHEN v.[距離] < 1400 THEN 'S' WHEN v.[距離] < 1900 THEN 'M'
                WHEN v.[距離] < 2400 THEN 'I' ELSE 'L'
              END AS dist_category
            , p.sire AS sire_name
        FROM dbo.VW_RaceEntryContract v
        LEFT JOIN dbo.MT_HorsePedigree p ON v.horse_id = p.horse_id
        WHERE (@race_id IS NULL OR v.race_id = @race_id)
    ),
    PastResults AS (
        /* 履歴集計（当日より前） */
        SELECT 
              te.race_id AS target_race_id, te.horse_id, ra.ability_idx, rr.race_date, rr.jyo_cd
            , CASE WHEN rr.baba_siba_cd <> '0' THEN '1' ELSE '2' END AS surface_type_cd
            , CASE 
                WHEN rr.distance_m < 1400 THEN 'S' WHEN rr.distance_m < 1900 THEN 'M'
                WHEN rr.distance_m < 2400 THEN 'I' ELSE 'L'
              END AS dist_category
            , ROW_NUMBER() OVER (PARTITION BY te.race_id, te.horse_id ORDER BY rr.race_date DESC) AS row_num
        FROM TargetEntries te
        JOIN dbo.TR_RaceAnalysis ra ON te.horse_id = ra.horse_id
        JOIN dbo.TR_RaceResult rr ON ra.race_id = rr.race_id AND ra.horse_id = rr.horse_id 
        WHERE rr.race_date < te.target_date
    ),
    AggregatedMetrics AS (
        /* 個体別の能力集計 */
        SELECT 
              p.target_race_id AS race_id, p.horse_id
            , AVG(p.ability_idx) AS avg_total
            , AVG(CASE WHEN p.row_num <= 5 THEN p.ability_idx END) AS avg_last5
            , AVG(CASE WHEN p.row_num <= 3 THEN p.ability_idx END) AS avg_last3
            , COUNT(*) AS career_count
            , AVG(CASE WHEN p.jyo_cd = te.jyo_cd AND p.surface_type_cd = te.surface_type_cd THEN p.ability_idx END) AS site_avg
            , COUNT(CASE WHEN p.jyo_cd = te.jyo_cd AND p.surface_type_cd = te.surface_type_cd THEN 1 END) AS site_count
            , AVG(CASE WHEN p.dist_category = te.dist_category THEN p.ability_idx END) AS dist_avg
            , COUNT(CASE WHEN p.dist_category = te.dist_category THEN 1 END) AS dist_count
        FROM PastResults p
        JOIN TargetEntries te ON p.target_race_id = te.race_id AND p.horse_id = te.horse_id
        GROUP BY p.target_race_id, p.horse_id
    ),
    SireSiteApt AS (
        /* 種牡馬適性：場所単位に集約して重複を排除 */
        SELECT sire_name, jyo_cd, surface_type_cd, SUM(sire_run_count) AS run_count, AVG(sire_aptitude_score) AS score
        FROM dbo.VW_Aptitude_Sire GROUP BY sire_name, jyo_cd, surface_type_cd
    ),
    SireDistApt AS (
        /* 種牡馬適性：距離単位に集約して重複を排除 */
        SELECT sire_name, dist_category, SUM(sire_run_count) AS run_count, AVG(sire_aptitude_score) AS score
        FROM dbo.VW_Aptitude_Sire GROUP BY sire_name, dist_category
    )

    -- 3. INSERT実行
    INSERT INTO dbo.TR_RacePredictionResult (
        race_id, target_date, race_no, frame_no, horse_no, horse_name, race_class,
        ability_last5_avg, momentum_score, aptitude_site_score, aptitude_dist_score,
        final_expected_score, career_count, site_experience_count, dist_experience_count
    )
    SELECT 
          te.race_id, te.target_date, te.[R], te.frame_no, te.horse_no, te.horse_name, te.[クラス]
        , CAST(m.avg_last5 AS DECIMAL(5,1))
        , CAST(ISNULL(m.avg_last3 - m.avg_last5, 0) AS DECIMAL(4,1))
        /* 適性：個体実績 + 血統（集約済み） */
        , CAST(
            ISNULL((m.site_avg - m.avg_total) * (m.site_count / (m.site_count + 3.0)), 0) + 
            ISNULL(aps.score * (aps.run_count / (aps.run_count + 10.0)), 0) 
          AS DECIMAL(4,1))
        , CAST(
            ISNULL((m.dist_avg - m.avg_total) * (m.dist_count / (m.dist_count + 3.0)), 0) +
            ISNULL(apd.score * (apd.run_count / (apd.run_count + 10.0)), 0) 
          AS DECIMAL(4,1))
        /* 最終期待値：能力 + 勢い + 適性補正 + 枠順バイアス */
        , CAST(
            ISNULL(m.avg_last5, 0) + ISNULL(m.avg_last3 - m.avg_last5, 0) +
            ISNULL((m.site_avg - m.avg_total) * (m.site_count / (m.site_count + 3.0)), 0) + 
            ISNULL(aps.score * (aps.run_count / (aps.run_count + 10.0)), 0) +
            ISNULL((m.dist_avg - m.avg_total) * (m.dist_count / (m.dist_count + 3.0)), 0) +
            ISNULL(apd.score * (apd.run_count / (apd.run_count + 10.0)), 0) +
            ISNULL(pb.bias_score, 0)
          AS DECIMAL(5,1))
        , m.career_count, m.site_count, m.dist_count
    FROM TargetEntries te
    LEFT JOIN AggregatedMetrics m ON te.race_id = m.race_id AND te.horse_id = m.horse_id
    LEFT JOIN dbo.MT_PostPositionBias pb 
        ON te.jyo_cd = pb.jyo_cd AND te.surface_type_cd = pb.surface_type 
        AND te.[距離] = pb.distance_m AND te.frame_no = pb.frame_no
    LEFT JOIN SireSiteApt aps ON te.sire_name = aps.sire_name AND te.jyo_cd = aps.jyo_cd AND te.surface_type_cd = aps.surface_type_cd
    LEFT JOIN SireDistApt apd ON te.sire_name = apd.sire_name AND te.dist_category = apd.dist_category;

    -- 4. 結果表示
    SELECT * FROM dbo.TR_RacePredictionResult WHERE (@race_id IS NULL OR race_id = @race_id) ORDER BY race_id, final_expected_score DESC;
END;