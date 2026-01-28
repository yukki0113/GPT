drop table ST_BloodSirePlace;
drop table ST_CoursePlace;
drop table ST_FramePlace;
drop table ST_JockeyPlace;
drop table ST_StatBaseConfig;
drop table ST_StylePlace;
drop table TR_RaceExpectation;
drop view  VW_RaceExpectation;
drop view VW_RaceExpectationAbilityDetail;
drop view VW_RaceExpectationExplain;
drop procedure usp_Calc_RaceExpectation;

INSERT INTO MT_CodeDictionary([code_type], [code], [text], [text_sub], [is_active], [sort_order], [note]) VALUES ('GRADE', 'L', 'L', '', 1, 9, N'L(リステッド)')
