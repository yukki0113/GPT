--* BackupToTempTable
drop table [TR_RaceResult]
GO
 
--* RestoreFromTempTable
CREATE TABLE dbo.TR_RaceResult (
    -- PK
    race_id         CHAR(12)     NOT NULL,

    -- レース（IF_JV_Race）
    race_date       DATE         NOT NULL,   -- 日付
    ymd             CHAR(8)      NOT NULL,   -- 参照性のため保持（YYYYMMDD）
    jyo_cd          CHAR(2)      NOT NULL,   -- 場CD
    race_no         TINYINT      NOT NULL,   -- R

    race_name       NVARCHAR(50) NULL,       -- レース名
    jyoken_name     NVARCHAR(50) NULL,       -- 表示用の条件名（JV提供）
    grade_cd        CHAR(2)      NULL,       -- グレードコード
    jyoken_syubetu_cd NVARCHAR(10) NULL,     -- 競争種別コード
    jyoken_cd4      NVARCHAR(10) NULL,       -- 競争条件コード

    track_cd        CHAR(2)      NULL,       -- トラックコード
    distance_m      INT          NULL,       -- 距離
    hasso_time      CHAR(4)      NULL,       -- 発走時刻
    weather_cd      CHAR(1)      NULL,       -- 天気(コード)
    baba_siba_cd    CHAR(1)      NULL,       -- 馬場コード(芝)
    baba_dirt_cd    CHAR(1)      NULL,       -- 馬場コード(ダ)

    -- WIN5（IF_JV_Win5Target から反映）
    win5_flg        TINYINT      NOT NULL CONSTRAINT DF_TR_RaceResult_win5_flg DEFAULT (0),

    -- 出走馬（IF_JV_RaceUma）
    frame_no        TINYINT      NULL,       -- 枠番
    horse_no        TINYINT      NOT NULL,   -- 馬番

    horse_id        CHAR(10)     NULL,       -- 馬ID
    horse_name      NVARCHAR(30) NULL,       -- 馬名

    sex_cd          CHAR(1)      NULL,       -- 性別コード
    age             TINYINT      NULL,       -- 年齢

    jockey_code     CHAR(5)      NULL,       -- 騎手CD
    jockey_name     NVARCHAR(10) NULL,       -- 騎手

    carried_weight  DECIMAL(3,1) NULL,       -- 斤量
    odds            DECIMAL(6,2) NULL,       -- オッズ
    popularity      SMALLINT     NULL,       -- 人気

    -- 解析が揺れるものは raw + parsed
    finish_time_raw NVARCHAR(16) NULL,       -- 完走タイム（文字）
    finish_time     TIME(2)      NULL,       -- 完走タイム

    weight_raw      NVARCHAR(8)  NULL,       -- 馬体重（文字）
    horse_weight    SMALLINT     NULL,       -- 馬体重

    weight_diff_raw NVARCHAR(8)  NULL,       -- 前走比（文字）
    horse_weight_diff SMALLINT   NULL,       -- 前走比

    pos_c1          TINYINT      NULL,       -- コーナー通過順_1
    pos_c2          TINYINT      NULL,       -- コーナー通過順_2
    pos_c3          TINYINT      NULL,       -- コーナー通過順_3
    pos_c4          TINYINT      NULL,       -- コーナー通過順_4

    finish_pos      TINYINT      NULL,       -- 着順
    final_3f_raw    NVARCHAR(8)  NULL,       -- 上がり3F（文字）
    final_3f        DECIMAL(3,1) NULL,       -- 上がり3F

    CONSTRAINT PK_TR_RaceResult PRIMARY KEY (race_id, horse_no)
);
GO

-- よく使う検索（任意）
CREATE INDEX IX_TR_RaceResult_RaceDate
    ON dbo.TR_RaceResult (race_date, jyo_cd, race_no);
GO

CREATE INDEX IX_TR_RaceResult_HorseId
    ON dbo.TR_RaceResult (horse_id);
GO

-- 基準タイムマスタとの結合用
CREATE INDEX IX_TR_RaceResult_StdTime 
ON dbo.TR_RaceResult (jyo_cd, track_cd, distance_m)
INCLUDE (finish_time);

-- 日次集計用（日付と場所で検索するため）
CREATE INDEX IX_TR_RaceResult_Daily
ON dbo.TR_RaceResult (race_date, jyo_cd, baba_siba_cd, baba_dirt_cd);

-- クラス結合用
CREATE INDEX IX_TR_RaceResult_Class
ON dbo.TR_RaceResult (jyoken_cd4);