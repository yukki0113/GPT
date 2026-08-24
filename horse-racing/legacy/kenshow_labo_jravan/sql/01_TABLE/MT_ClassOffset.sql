/* クラス補正マスタ (MT_ClassOffset)
  3勝クラス(016)を基準(0)とした時の、各クラスの補正秒数を定義
*/
--* BackupToTempTable
drop table [MT_ClassOffset]
GO

--* RestoreFromTempTable
CREATE TABLE dbo.MT_ClassOffset (
    jyoken_cd4   NVARCHAR(10) NOT NULL, -- 条件コード4
    offset_index FLOAT        NOT NULL, -- 指数への加減点（例：G1なら +20 / 未勝利なら -30）
    description  NVARCHAR(50),
    update_at    DATETIME DEFAULT GETDATE(),
    CONSTRAINT PK_MT_ClassOffset PRIMARY KEY (jyoken_cd4)
)
GO