--* BackupToTempTable
drop table [TR_Payout]
GO

--* RestoreFromTempTable
CREATE TABLE dbo.TR_Payout (
    id INT IDENTITY(1,1) NOT NULL
        CONSTRAINT PK_TR_Payout PRIMARY KEY,

    race_id CHAR(12) NOT NULL,

    bet_type NVARCHAR(20) NOT NULL,     -- 式別

    horse_no_1 INT NULL,                -- 馬番1
    horse_no_2 INT NULL,                -- 馬番2
    horse_no_3 INT NULL,                -- 馬番3

    payout_amount INT NOT NULL,         -- 払戻
    popularity    INT NULL,             -- 式別人気

    CONSTRAINT UQ_TR_Payout_Race_BetType_Horses
        UNIQUE (race_id, bet_type, horse_no_1, horse_no_2, horse_no_3)
);
GO

CREATE INDEX IX_TR_Payout_Race_BetType
    ON dbo.TR_Payout (race_id, bet_type);
GO

CREATE INDEX IX_TR_Payout_Race_BetType_Horse1
    ON dbo.TR_Payout (race_id, bet_type, horse_no_1);
GO