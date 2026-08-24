CREATE TABLE dbo.MT_CodeDictionary (
    code_type  NVARCHAR(50)  NOT NULL,  -- 例: 'TRACK', 'WEATHER', 'GOING'
    code       NVARCHAR(50)  NOT NULL,  -- 例: '01', '2', 'A'

    [text]     NVARCHAR(200) NOT NULL,   -- 表示名（基本ここ）
    text_sub   NVARCHAR(200) NULL,       -- 略称、別表記など

    is_active  BIT           NOT NULL
        CONSTRAINT DF_MT_CodeDictionary_is_active DEFAULT (1),

    sort_order INT           NULL,

    note       NVARCHAR(200) NULL,

    CONSTRAINT PK_MT_CodeDictionary PRIMARY KEY (code_type, code)
);
GO

-- 種別ごとの一覧表示・JOIN後のフィルタ（is_active）・並び順に効かせる
CREATE INDEX IX_MT_CodeDictionary_Type_Active_Sort
    ON dbo.MT_CodeDictionary (code_type, is_active, sort_order, code);
GO

-- 画面検索や調査用（必要なければ省略可）
CREATE INDEX IX_MT_CodeDictionary_Type_Text
    ON dbo.MT_CodeDictionary (code_type, [text]);
GO