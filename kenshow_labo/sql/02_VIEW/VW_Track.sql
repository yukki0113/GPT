CREATE OR ALTER VIEW dbo.VW_Track
AS
SELECT
      t.JyoCD
    , rc.[text]                        AS [場名]

    , t.Kyori
    , t.ShibaDirt
    , sd.[text]                        AS [芝ダ]

    , t.TrackCD
    , tr.[text]                        AS [トラック]

    , t.TurnDirCD
    , td.[text]                        AS [回り]

    , t.CourseRingCD
    , cr.[text]                        AS [内外]

    , t.CourseEx                       AS [コース解説]
FROM dbo.MT_TRACK AS t
LEFT JOIN dbo.MT_CodeDictionary AS rc
    ON rc.code_type = N'RACE_COURSE'
   AND rc.code      = t.JyoCD
   AND rc.is_active = 1
LEFT JOIN dbo.MT_CodeDictionary AS sd
    ON sd.code_type = N'SHIBA_DIRT'
   AND sd.code      = t.ShibaDirt
   AND sd.is_active = 1
LEFT JOIN dbo.MT_CodeDictionary AS tr
    ON tr.code_type = N'TRACK'
   AND tr.code      = t.TrackCD
   AND tr.is_active = 1
LEFT JOIN dbo.MT_CodeDictionary AS td
    ON td.code_type = N'TURN_DIR'
   AND td.code      = t.TurnDirCD
   AND td.is_active = 1
LEFT JOIN dbo.MT_CodeDictionary AS cr
    ON cr.code_type = N'COURSE_RING'
   AND cr.code      = t.CourseRingCD
   AND cr.is_active = 1
GO
