/* 基準タイムマスタ (MT_StandardTime)
  各コース条件ごとの基準タイム（3勝クラス・良馬場想定）を定義
*/
--* BackupToTempTable
drop table [MT_StandardTime]
GO

--* RestoreFromTempTable
CREATE TABLE dbo.MT_StandardTime (
    jyo_cd       CHAR(2)  NOT NULL, -- 競馬場コード (TR_RaceResult.jyo_cd に準拠)
    track_cd     CHAR(2)  NOT NULL, -- トラックコード (TR_RaceResult.track_cd に準拠)
    distance_m   INT      NOT NULL, -- 距離 (TR_RaceResult.distance_m に準拠)
    
    std_time     FLOAT    NOT NULL, -- 基準タイム（秒）
    dist_coef    FLOAT    NOT NULL, -- 距離係数（1秒あたりの指数重み）
    
    update_at    DATETIME DEFAULT GETDATE(), -- 更新日時
    
    CONSTRAINT PK_MT_StandardTime PRIMARY KEY (jyo_cd, track_cd, distance_m)
);
GO