/* 【検証ラボ】予測結果保存テーブル
   SQLiteへのエクスポートや、モバイルサイトでの表示用ソースとして使用します。
*/
--* BackupToTempTable
drop table [TR_RacePredictionResult]
GO

--* RestoreFromTempTable
CREATE TABLE dbo.TR_RacePredictionResult (
    race_id              CHAR(12)      NOT NULL,
    target_date          DATE          NOT NULL,
    race_no              TINYINT       NOT NULL,
    frame_no             TINYINT       NULL,
    horse_no             TINYINT       NOT NULL,
    horse_name           NVARCHAR(30)  NOT NULL,
    race_class           NVARCHAR(20)  NULL,
    ability_last5_avg    DECIMAL(5,1)  NULL, -- 能力_近5走平均
    momentum_score       DECIMAL(4,1)  NULL, -- 勢い値
    aptitude_site_score  DECIMAL(4,1)  NULL, -- 適性_場所
    aptitude_dist_score  DECIMAL(4,1)  NULL, -- 適性_距離
    final_expected_score DECIMAL(5,1)  NULL, -- 最終期待値
    career_count         INT           NULL, -- キャリア
    site_experience_count INT           NULL, -- 場経
    dist_experience_count INT           NULL, -- 距経
    created_at           DATETIME      DEFAULT GETDATE(),
    
    CONSTRAINT PK_TR_RacePredictionResult PRIMARY KEY (race_id, horse_no)
);