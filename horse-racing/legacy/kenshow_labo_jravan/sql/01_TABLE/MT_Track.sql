--* BackupToTempTable
drop table [MT_Track]
GO
 
--* RestoreFromTempTable
CREATE TABLE dbo.MT_TRACK
(
      JyoCD      CHAR(2)        NOT NULL  -- 場所CD
    , Kyori      INT            NOT NULL  -- 距離
    , ShibaDirt  CHAR(1)        NOT NULL  -- 芝'1' / ダ'2'
    , TrackCD    CHAR(2)        NOT NULL  -- TRACK_CD（MT_CodeDictionary: TRACK を想定）

    /* 手動管理列（必要に応じて辞書化） */
    , TurnDirCD  CHAR(1)        NULL      -- 回り: '1'=右, '2'=左, '3'=直線(必要なら)
    , CourseRingCD CHAR(1)      NULL      -- 内外: '1'=内, '2'=外, '3'=内外, '9'=不明 等

    , CourseEx   NVARCHAR(1500)  NULL      -- 場所解説

    , CONSTRAINT PK_MT_TRACK PRIMARY KEY (JyoCD, Kyori, ShibaDirt, TrackCD)

    , CONSTRAINT CK_MT_TRACK_ShibaDirt CHECK (ShibaDirt IN ('1', '2'))
    , CONSTRAINT CK_MT_TRACK_Kyori CHECK (Kyori > 0)

    , CONSTRAINT CK_MT_TRACK_TurnDirCD
        CHECK (TurnDirCD IS NULL OR TurnDirCD IN ('1', '2', '3'))

    , CONSTRAINT CK_MT_TRACK_CourseRingCD
        CHECK (CourseRingCD IS NULL OR CourseRingCD IN ('1', '2', '3', '9'))
)
GO

/* TrackCD から逆引きする用途があるなら */
CREATE INDEX IX_MT_TRACK_TrackCD
    ON dbo.MT_TRACK (TrackCD)
GO

/* 集計で「右/左」「内/外」で引くことが多いなら（任意） */
CREATE INDEX IX_MT_TRACK_TurnRing
    ON dbo.MT_TRACK (TurnDirCD, CourseRingCD)
GO