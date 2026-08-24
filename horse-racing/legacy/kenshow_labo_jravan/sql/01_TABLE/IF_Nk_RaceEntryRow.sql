--* BackupToTempTable
drop table [IF_Nk_RaceEntryRow]
GO
 
--* RestoreFromTempTable
CREATE TABLE dbo.IF_Nk_RaceEntryRow
(
      import_batch_id        UNIQUEIDENTIFIER NOT NULL
    , row_no                 INT              NOT NULL  -- HTML上の行順（1..N）

    -- ID（由来を明確化）
    , nk_horse_id            CHAR(10)         NULL      -- netkeiba馬ID（0埋め推奨）
    , jv_horse_id            CHAR(10)         NULL      -- JV馬ID（確定できたら）

    -- raw（文字列中心）
    , frame_no_raw           NVARCHAR(10)     NULL      -- 未確定は空など
    , horse_no_raw           NVARCHAR(10)     NULL      -- 未確定は空など
    , horse_name_raw         NVARCHAR(100)    NULL
    , sex_age_raw            NVARCHAR(10)     NULL      -- 例: "牡3"
    , jockey_name_raw        NVARCHAR(50)     NULL
    , carried_weight_raw     NVARCHAR(10)     NULL      -- 例: "57.0"

    -- 任意：将来拡張（使うなら後でALTERで追加でもOK）
    -- , odds_raw            NVARCHAR(10)     NULL
    -- , popularity_raw      NVARCHAR(10)     NULL

    CONSTRAINT PK_IF_Nk_RaceEntryRow PRIMARY KEY (import_batch_id, row_no)
);
GO

CREATE INDEX IX_IF_Nk_RaceEntryRow_batch
ON dbo.IF_Nk_RaceEntryRow (import_batch_id);
GO

CREATE INDEX IX_IF_Nk_RaceEntryRow_nkhorse
ON dbo.IF_Nk_RaceEntryRow (nk_horse_id);
GO

CREATE INDEX IX_IF_Nk_RaceEntryRow_jvhorse
ON dbo.IF_Nk_RaceEntryRow (jv_horse_id);
GO
