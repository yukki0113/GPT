/* レース分析結果テーブル (TR_RaceAnalysis)
  検証の主戦場となる指数格納テーブル
*/
--* BackupToTempTable
drop table [TR_RaceAnalysis]
GO

--* RestoreFromTempTable
CREATE TABLE dbo.TR_RaceAnalysis (
    race_id         CHAR(12) NOT NULL, -- レースID (TR_RaceResult.race_id に準拠)
    horse_id        CHAR(10) NOT NULL, -- 血統登録番号 (TR_RaceResult.horse_id に準拠)
    
    ability_idx     FLOAT,                 -- 能力指数（最終結果）
    track_variant   FLOAT,                 -- 馬場差（日次補正値）
    raw_score       FLOAT,                 -- 補正前スコア（検証用中間値）
    
    created_at      DATETIME DEFAULT GETDATE(), -- 作成日時
    updated_at      DATETIME DEFAULT GETDATE(), -- 更新日時
    
    CONSTRAINT PK_TR_RaceAnalysis PRIMARY KEY (race_id, horse_id)
);
GO