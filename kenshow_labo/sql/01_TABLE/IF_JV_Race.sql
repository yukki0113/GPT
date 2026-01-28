--* BackupToTempTable
drop table [IF_JV_Race]
GO
 
--* RestoreFromTempTable
CREATE TABLE dbo.IF_JV_Race (
    race_id        CHAR(12)      NOT NULL,  -- yyyymmdd + jyo(2) + racenum(2)
    ymd            CHAR(8)       NOT NULL,  -- yyyymmdd (idYear+idMonthDay)
    jyo_cd         CHAR(2)       NOT NULL,
    race_num       TINYINT       NOT NULL,

    kaiji          SMALLINT      NULL,
    nichiji        SMALLINT      NULL,

    data_kubun     CHAR(1)       NULL,      -- headDataKubun
    make_date      CHAR(8)       NULL,      -- headMakeDate (yyyymmdd)

    race_name      NVARCHAR(50)  NULL,      -- RaceInfoHondai 等から
    jyoken_name    NVARCHAR(50)  NULL,      -- JyokenName（クラス/条件のベース）
    grade_cd       CHAR(2)       NULL,      -- GradeCD（必要なら）
    jyoken_syubetu_cd NVARCHAR(10) NULL,    -- JyokenInfoSyubetuCD（年齢条件など）
    jyoken_cd4        NVARCHAR(10) NULL;    -- JyokenInfoJyokenCD4（クラス/賞金条件など）
    track_cd       CHAR(2)       NULL,      -- TrackCD（芝/ダ/障害や内外などは後で変換）
    distance_m     INT           NULL,      -- Kyori

    hasso_time     CHAR(4)       NULL,      -- HassoTime (HHMM等)
    weather_cd     CHAR(1)       NULL,      -- TenkoBabaTenkoCD
    baba_siba_cd   CHAR(1)       NULL,      -- TenkoBabaSibaBabaCD
    baba_dirt_cd   CHAR(1)       NULL,      -- TenkoBabaDirtBabaCD

    CONSTRAINT PK_IF_JV_Race PRIMARY KEY (race_id)
);

CREATE INDEX IX_IF_JV_Race_Ymd ON dbo.IF_JV_Race(ymd);
