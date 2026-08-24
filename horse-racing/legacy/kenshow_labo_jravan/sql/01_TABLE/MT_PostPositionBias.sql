/* 【検証ラボ】予測結果保存テーブル
   SQLiteへのエクスポートや、モバイルサイトでの表示用ソースとして使用します。
*/
--* BackupToTempTable
drop table [MT_PostPositionBias]
GO

--* RestoreFromTempTable
CREATE TABLE dbo.MT_PostPositionBias (
    jyo_cd       CHAR(2)      NOT NULL,
    surface_type CHAR(1)      NOT NULL, -- 1:芝, 2:ダ
    distance_m   SMALLINT     NOT NULL, -- 0の場合は全距離対象
    frame_no     TINYINT      NOT NULL,
    bias_score   DECIMAL(3,1) NOT NULL, -- 加減点（例: 3.0, -5.0）
    description  NVARCHAR(50) NULL,
    
    CONSTRAINT PK_MT_PostPositionBias PRIMARY KEY (jyo_cd, surface_type, distance_m, frame_no)
);