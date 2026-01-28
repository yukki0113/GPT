CREATE OR ALTER PROCEDURE dbo.usp_RebuildAllIndices
    @TargetStartDate DATE = '2010-01-01',
    @TargetEndDate   DATE = '2099-12-31' 
AS
BEGIN
    SET NOCOUNT ON;
    
    PRINT '=== 1. 基準タイムマスタ (MT_StandardTime) 再構築開始 ===';
    TRUNCATE TABLE dbo.MT_StandardTime;

    INSERT INTO dbo.MT_StandardTime (jyo_cd, track_cd, distance_m, std_time, dist_coef, update_at)
    SELECT 
        jyo_cd,
        track_cd,
        [距離],
        AVG(CAST(DATEDIFF(MILLISECOND, '00:00:00', [走破時計]) AS FLOAT) / 1000.0) AS std_time,
        20.0 AS dist_coef,
        GETDATE()
    FROM dbo.VW_RaceResultContract
    WHERE jyoken_cd4 = '016' 
      AND (baba_siba_cd = '1' OR baba_dirt_cd = '1')
      AND [着順] = 1
      AND [走破時計] <> '00:00:00'
      AND [走破時計] IS NOT NULL
    GROUP BY jyo_cd, track_cd, [距離];
    
    PRINT '完了: 基準タイム作成';

    -------------------------------------------------------

    PRINT '=== 2. 距離係数 (dist_coef) の更新 ===';
    UPDATE dbo.MT_StandardTime SET dist_coef = 25.0 WHERE distance_m <= 1200;
    UPDATE dbo.MT_StandardTime SET dist_coef = 20.0 WHERE distance_m > 1200 AND distance_m <= 1800;
    UPDATE dbo.MT_StandardTime SET dist_coef = 15.0 WHERE distance_m > 1800 AND distance_m <= 2400;
    UPDATE dbo.MT_StandardTime SET dist_coef = 10.0 WHERE distance_m > 2400;
    
    PRINT '完了: 距離係数更新';

    -------------------------------------------------------

    PRINT '=== 3. クラス補正マスタ (MT_ClassOffset) 自動学習 ===';
    TRUNCATE TABLE dbo.MT_ClassOffset;

    INSERT INTO dbo.MT_ClassOffset (jyoken_cd4, offset_index, description, update_at)
    SELECT 
        v.unified_class_cd,
        ROUND(AVG(
            (s.std_time - (CAST(DATEDIFF(MILLISECOND, '00:00:00', v.[走破時計]) AS FLOAT) / 1000.0)) * s.dist_coef
        ), 0) AS offset_index,
        MAX(v.[クラス]) AS description, -- [統合クラス] -> [クラス]
        GETDATE()
    FROM dbo.VW_RaceResultContract v
    JOIN dbo.MT_StandardTime s ON v.jyo_cd = s.jyo_cd AND v.track_cd = s.track_cd AND v.[距離] = s.distance_m
    WHERE v.[着順] = 1 
      AND (v.baba_siba_cd = '1' OR v.baba_dirt_cd = '1') 
      AND v.[走破時計] <> '00:00:00'
      AND v.[走破時計] IS NOT NULL
    GROUP BY v.unified_class_cd;
    
    PRINT '完了: クラス補正値の自動算出';

    -------------------------------------------------------

    PRINT '=== 4. 能力指数 (TR_RaceAnalysis) の算出と保存 ===';
    PRINT '対象期間: ' + CAST(@TargetStartDate AS VARCHAR) + ' ～ ' + CAST(@TargetEndDate AS VARCHAR);

    -- 既存データをクリア（物理テーブル TR_RaceResult の race_date を使用）
    DELETE a
    FROM dbo.TR_RaceAnalysis a
    JOIN dbo.TR_RaceResult r ON a.race_id = r.race_id
    WHERE r.race_date BETWEEN @TargetStartDate AND @TargetEndDate; -- kaisai_date -> race_date

    -- 日次馬場差算出
    SELECT 
        v.jyo_cd,
        v.baba_siba_cd,
        v.baba_dirt_cd,
        v.[日付], -- [開催日] -> [日付]
        AVG(
            ((s.std_time - (CAST(DATEDIFF(MILLISECOND, '00:00:00', v.[走破時計]) AS FLOAT) / 1000.0)) * s.dist_coef) 
            + o.offset_index
        ) AS daily_variant
    INTO #DailyVariant
    FROM dbo.VW_RaceResultContract v
    JOIN dbo.MT_StandardTime s ON v.jyo_cd = s.jyo_cd AND v.track_cd = s.track_cd AND v.[距離] = s.distance_m
    JOIN dbo.MT_ClassOffset o ON v.unified_class_cd = o.jyoken_cd4
    WHERE v.[日付] BETWEEN @TargetStartDate AND @TargetEndDate -- [開催日] -> [日付]
      AND v.[着順] <= 10
      AND v.[走破時計] <> '00:00:00'
      AND v.[走破時計] IS NOT NULL
    GROUP BY v.jyo_cd, v.baba_siba_cd, v.baba_dirt_cd, v.[日付]; -- [開催日] -> [日付]

    -- 指数保存
    INSERT INTO dbo.TR_RaceAnalysis (race_id, horse_id, ability_idx, track_variant, raw_score, created_at, updated_at)
    SELECT 
        v.race_id,
        v.horse_id,
        (
          ((s.std_time - (CAST(DATEDIFF(MILLISECOND, '00:00:00', v.[走破時計]) AS FLOAT) / 1000.0)) * s.dist_coef) 
          + o.offset_index - dv.daily_variant
        ) + 80 AS ability_idx,
        dv.daily_variant,
        (
          ((s.std_time - (CAST(DATEDIFF(MILLISECOND, '00:00:00', v.[走破時計]) AS FLOAT) / 1000.0)) * s.dist_coef) 
          + o.offset_index + 80
        ) AS raw_score,
        GETDATE(),
        GETDATE()
    FROM dbo.VW_RaceResultContract v
    JOIN dbo.MT_StandardTime s ON v.jyo_cd = s.jyo_cd AND v.track_cd = s.track_cd AND v.[距離] = s.distance_m
    JOIN dbo.MT_ClassOffset o ON v.unified_class_cd = o.jyoken_cd4
    JOIN #DailyVariant dv ON v.jyo_cd = dv.jyo_cd 
                         AND v.baba_siba_cd = dv.baba_siba_cd 
                         AND v.baba_dirt_cd = dv.baba_dirt_cd 
                         AND v.[日付] = dv.[日付] -- [開催日] -> [日付]
    WHERE v.[日付] BETWEEN @TargetStartDate AND @TargetEndDate
      AND v.[走破時計] <> '00:00:00'
      AND v.[走破時計] IS NOT NULL;

    DROP TABLE #DailyVariant;

    PRINT '=== 全工程完了 ===';
END;