CREATE TABLE #TargetRace
(
    race_id CHAR(12) NOT NULL PRIMARY KEY
);

-- 対象を追加
INSERT INTO #TargetRace (race_id)
VALUES
('202506050811'),
('202509050411');

DECLARE @race_id CHAR(12);

DECLARE cur CURSOR LOCAL FAST_FORWARD FOR
SELECT race_id FROM #TargetRace ORDER BY race_id;

OPEN cur;
FETCH NEXT FROM cur INTO @race_id;

WHILE @@FETCH_STATUS = 0
BEGIN
    EXEC dbo.sp_GenerateRaceEntryFromRaceResult @race_id = @race_id;
    FETCH NEXT FROM cur INTO @race_id;
END

CLOSE cur;
DEALLOCATE cur;
