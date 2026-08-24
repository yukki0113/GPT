using System;
using Microsoft.Data.Sqlite;

namespace ExportSiteSQLite
{
    /// <summary>
    /// SQLite書き込み（Prepared + Transaction 前提）。
    /// </summary>
    public static class SqliteWriters
    {
        /// <summary>
        /// dim_race をINSERTする（過去側）。
        /// </summary>
        public static void InsertDimRaceHistory(SqliteConnection conn, SqliteTransaction tx, DimRaceRow[] rows)
        {
            using (SqliteCommand cmd = conn.CreateCommand())
            {
                cmd.Transaction = tx;
                cmd.CommandText = @"
                    INSERT INTO dim_race
                    (race_id, race_date, jyo_cd, race_no, race_name, track_name, surface_type, distance_m, class_simple, win5_flg, has_result, has_entry, data_group)
                    VALUES
                    (@race_id, @race_date, @jyo_cd, @race_no, @race_name, @track_name, @surface_type, @distance_m, @class_simple, @win5_flg, 1, 0, 'history');";

                cmd.Parameters.Add(new SqliteParameter("@race_id", SqliteType.Text));
                cmd.Parameters.Add(new SqliteParameter("@race_date", SqliteType.Text));
                cmd.Parameters.Add(new SqliteParameter("@jyo_cd", SqliteType.Text));
                cmd.Parameters.Add(new SqliteParameter("@race_no", SqliteType.Integer));
                cmd.Parameters.Add(new SqliteParameter("@race_name", SqliteType.Text));
                cmd.Parameters.Add(new SqliteParameter("@track_name", SqliteType.Text));
                cmd.Parameters.Add(new SqliteParameter("@surface_type", SqliteType.Text));
                cmd.Parameters.Add(new SqliteParameter("@distance_m", SqliteType.Integer));
                cmd.Parameters.Add(new SqliteParameter("@class_simple", SqliteType.Text));
                cmd.Parameters.Add(new SqliteParameter("@win5_flg", SqliteType.Integer));

                int i;
                for (i = 0; i < rows.Length; i++)
                {
                    DimRaceRow r = rows[i];

                    cmd.Parameters["@race_id"].Value = r.RaceId;
                    cmd.Parameters["@race_date"].Value = r.RaceDate;
                    cmd.Parameters["@jyo_cd"].Value = r.JyoCd;
                    cmd.Parameters["@race_no"].Value = r.RaceNo;
                    cmd.Parameters["@race_name"].Value = (object?)r.RaceName ?? DBNull.Value;
                    cmd.Parameters["@track_name"].Value = (object?)r.TrackName ?? DBNull.Value;
                    cmd.Parameters["@surface_type"].Value = (object?)r.SurfaceType ?? DBNull.Value;
                    cmd.Parameters["@distance_m"].Value = (object?)r.DistanceM ?? DBNull.Value;
                    cmd.Parameters["@class_simple"].Value = (object?)r.ClassSimple ?? DBNull.Value;
                    cmd.Parameters["@win5_flg"].Value = r.Win5Flg;

                    cmd.ExecuteNonQuery();
                }
            }
        }

        /// <summary>
        /// dim_race（週末）をUPSERTする（存在すれば has_entry=1 に更新）。
        /// </summary>
        public static void UpsertDimRaceWeekend(SqliteConnection conn, SqliteTransaction tx, DimRaceRow[] rows)
        {
            using (SqliteCommand update = conn.CreateCommand())
            using (SqliteCommand insert = conn.CreateCommand())
            {
                update.Transaction = tx;
                insert.Transaction = tx;

                update.CommandText = @"
                    UPDATE dim_race
                    SET has_entry = 1
                    , data_group = CASE WHEN data_group IS NULL THEN 'weekend' ELSE data_group END
                    WHERE race_id = @race_id;";

                insert.CommandText = @"
                    INSERT INTO dim_race
                    (race_id, race_date, jyo_cd, race_no, race_name, track_name, surface_type, distance_m, class_simple, win5_flg, has_result, has_entry, data_group)
                    VALUES
                    (@race_id, @race_date, @jyo_cd, @race_no, @race_name, @track_name, @surface_type, @distance_m, @class_simple, @win5_flg, 0, 1, 'weekend');";

                update.Parameters.Add(new SqliteParameter("@race_id", SqliteType.Text));

                insert.Parameters.Add(new SqliteParameter("@race_id", SqliteType.Text));
                insert.Parameters.Add(new SqliteParameter("@race_date", SqliteType.Text));
                insert.Parameters.Add(new SqliteParameter("@jyo_cd", SqliteType.Text));
                insert.Parameters.Add(new SqliteParameter("@race_no", SqliteType.Integer));
                insert.Parameters.Add(new SqliteParameter("@race_name", SqliteType.Text));
                insert.Parameters.Add(new SqliteParameter("@track_name", SqliteType.Text));
                insert.Parameters.Add(new SqliteParameter("@surface_type", SqliteType.Text));
                insert.Parameters.Add(new SqliteParameter("@distance_m", SqliteType.Integer));
                insert.Parameters.Add(new SqliteParameter("@class_simple", SqliteType.Text));
                insert.Parameters.Add(new SqliteParameter("@win5_flg", SqliteType.Integer));

                int i;
                for (i = 0; i < rows.Length; i++)
                {
                    DimRaceRow r = rows[i];

                    /* 1) UPDATE */
                    update.Parameters["@race_id"].Value = r.RaceId;
                    int updated = update.ExecuteNonQuery();

                    /* 2) 無ければ INSERT */
                    if (updated == 0)
                    {
                        insert.Parameters["@race_id"].Value = r.RaceId;
                        insert.Parameters["@race_date"].Value = r.RaceDate;
                        insert.Parameters["@jyo_cd"].Value = r.JyoCd;
                        insert.Parameters["@race_no"].Value = r.RaceNo;
                        insert.Parameters["@race_name"].Value = (object?)r.RaceName ?? DBNull.Value;
                        insert.Parameters["@track_name"].Value = (object?)r.TrackName ?? DBNull.Value;
                        insert.Parameters["@surface_type"].Value = (object?)r.SurfaceType ?? DBNull.Value;
                        insert.Parameters["@distance_m"].Value = (object?)r.DistanceM ?? DBNull.Value;
                        insert.Parameters["@class_simple"].Value = (object?)r.ClassSimple ?? DBNull.Value;
                        insert.Parameters["@win5_flg"].Value = r.Win5Flg;

                        insert.ExecuteNonQuery();
                    }
                }
            }
        }

        /// <summary>
        /// fact_race_result をINSERTする。
        /// </summary>
        public static void InsertRaceResults(SqliteConnection conn, SqliteTransaction tx, RaceResultRow[] rows)
        {
            using (SqliteCommand cmd = conn.CreateCommand())
            {
                cmd.Transaction = tx;
                cmd.CommandText = @"
                    INSERT INTO fact_race_result
                    (race_id, horse_id, horse_name, umaban, wakuban, finish_pos, time_text, margin_text, jockey_name, weight_carried, odds, popularity)
                    VALUES
                    (@race_id, @horse_id, @horse_name, @umaban, @wakuban, @finish_pos, @time_text, @margin_text, @jockey_name, @weight_carried, @odds, @popularity);";

                cmd.Parameters.Add(new SqliteParameter("@race_id", SqliteType.Text));
                cmd.Parameters.Add(new SqliteParameter("@horse_id", SqliteType.Text));
                cmd.Parameters.Add(new SqliteParameter("@horse_name", SqliteType.Text));
                cmd.Parameters.Add(new SqliteParameter("@umaban", SqliteType.Integer));
                cmd.Parameters.Add(new SqliteParameter("@wakuban", SqliteType.Integer));
                cmd.Parameters.Add(new SqliteParameter("@finish_pos", SqliteType.Integer));
                cmd.Parameters.Add(new SqliteParameter("@time_text", SqliteType.Text));
                cmd.Parameters.Add(new SqliteParameter("@margin_text", SqliteType.Text));
                cmd.Parameters.Add(new SqliteParameter("@jockey_name", SqliteType.Text));
                cmd.Parameters.Add(new SqliteParameter("@weight_carried", SqliteType.Real));
                cmd.Parameters.Add(new SqliteParameter("@odds", SqliteType.Real));
                cmd.Parameters.Add(new SqliteParameter("@popularity", SqliteType.Integer));

                int i;
                for (i = 0; i < rows.Length; i++)
                {
                    RaceResultRow r = rows[i];

                    cmd.Parameters["@race_id"].Value = r.RaceId;
                    cmd.Parameters["@horse_id"].Value = r.HorseId;
                    cmd.Parameters["@horse_name"].Value = r.HorseName;
                    cmd.Parameters["@umaban"].Value = (object?)r.Umaban ?? DBNull.Value;
                    cmd.Parameters["@wakuban"].Value = (object?)r.Wakuban ?? DBNull.Value;
                    cmd.Parameters["@finish_pos"].Value = (object?)r.FinishPos ?? DBNull.Value;
                    cmd.Parameters["@time_text"].Value = (object?)r.TimeText ?? DBNull.Value;
                    cmd.Parameters["@margin_text"].Value = (object?)r.MarginText ?? DBNull.Value;
                    cmd.Parameters["@jockey_name"].Value = (object?)r.JockeyName ?? DBNull.Value;
                    cmd.Parameters["@weight_carried"].Value = (object?)r.WeightCarried ?? DBNull.Value;
                    cmd.Parameters["@odds"].Value = (object?)r.Odds ?? DBNull.Value;
                    cmd.Parameters["@popularity"].Value = (object?)r.Popularity ?? DBNull.Value;

                    cmd.ExecuteNonQuery();
                }
            }
        }

        /// <summary>
        /// fact_payout をINSERTする。
        /// </summary>
        public static void InsertPayouts(SqliteConnection conn, SqliteTransaction tx, PayoutRow[] rows)
        {
            using (SqliteCommand cmd = conn.CreateCommand())
            {
                cmd.Transaction = tx;
                cmd.CommandText = @"
                    INSERT INTO fact_payout
                    (race_id, bet_type, combo_text, payout_yen, popularity)
                    VALUES
                    (@race_id, @bet_type, @combo_text, @payout_yen, @popularity);";

                cmd.Parameters.Add(new SqliteParameter("@race_id", SqliteType.Text));
                cmd.Parameters.Add(new SqliteParameter("@bet_type", SqliteType.Text));
                cmd.Parameters.Add(new SqliteParameter("@combo_text", SqliteType.Text));
                cmd.Parameters.Add(new SqliteParameter("@payout_yen", SqliteType.Integer));
                cmd.Parameters.Add(new SqliteParameter("@popularity", SqliteType.Integer));

                int i;
                for (i = 0; i < rows.Length; i++)
                {
                    PayoutRow r = rows[i];

                    cmd.Parameters["@race_id"].Value = r.RaceId;
                    cmd.Parameters["@bet_type"].Value = r.BetType;
                    cmd.Parameters["@combo_text"].Value = r.ComboText;
                    cmd.Parameters["@payout_yen"].Value = r.PayoutYen;
                    cmd.Parameters["@popularity"].Value = (object?)r.Popularity ?? DBNull.Value;

                    cmd.ExecuteNonQuery();
                }
            }
        }

        /// <summary>
        /// fact_race_entry をINSERTする。
        /// </summary>
        public static void InsertRaceEntries(SqliteConnection conn, SqliteTransaction tx, RaceEntryRow[] rows)
        {
            using (SqliteCommand cmd = conn.CreateCommand())
            {
                cmd.Transaction = tx;
                cmd.CommandText = @"
                    INSERT INTO fact_race_entry
                    (race_id, horse_id, horse_name, umaban, wakuban, jockey_name, trainer_name, weight_carried)
                    VALUES
                    (@race_id, @horse_id, @horse_name, @umaban, @wakuban, @jockey_name, @trainer_name, @weight_carried);";

                cmd.Parameters.Add(new SqliteParameter("@race_id", SqliteType.Text));
                cmd.Parameters.Add(new SqliteParameter("@horse_id", SqliteType.Text));
                cmd.Parameters.Add(new SqliteParameter("@horse_name", SqliteType.Text));
                cmd.Parameters.Add(new SqliteParameter("@umaban", SqliteType.Integer));
                cmd.Parameters.Add(new SqliteParameter("@wakuban", SqliteType.Integer));
                cmd.Parameters.Add(new SqliteParameter("@jockey_name", SqliteType.Text));
                cmd.Parameters.Add(new SqliteParameter("@trainer_name", SqliteType.Text));
                cmd.Parameters.Add(new SqliteParameter("@weight_carried", SqliteType.Real));

                int i;
                for (i = 0; i < rows.Length; i++)
                {
                    RaceEntryRow r = rows[i];

                    cmd.Parameters["@race_id"].Value = r.RaceId;
                    cmd.Parameters["@horse_id"].Value = r.HorseId;
                    cmd.Parameters["@horse_name"].Value = r.HorseName;
                    cmd.Parameters["@umaban"].Value = (object?)r.Umaban ?? DBNull.Value;
                    cmd.Parameters["@wakuban"].Value = (object?)r.Wakuban ?? DBNull.Value;
                    cmd.Parameters["@jockey_name"].Value = (object?)r.JockeyName ?? DBNull.Value;
                    cmd.Parameters["@trainer_name"].Value = (object?)r.TrainerName ?? DBNull.Value;
                    cmd.Parameters["@weight_carried"].Value = (object?)r.WeightCarried ?? DBNull.Value;

                    cmd.ExecuteNonQuery();
                }
            }
        }

        /// <summary>
        /// fact_race_expectation をINSERTする。
        /// </summary>
        public static void InsertExpectations(SqliteConnection conn, SqliteTransaction tx, ExpectationRow[] rows)
        {
            using (SqliteCommand cmd = conn.CreateCommand())
            {
                cmd.Transaction = tx;
                cmd.CommandText = @"
                    INSERT INTO fact_race_expectation
                    (race_id, umaban, horse_id, horse_name, ability, mult_course, mult_style, mult_frame, mult_blood, mult_jockey, expected_raw, expected_100)
                    VALUES
                    (@race_id, @umaban, @horse_id, @horse_name, @ability, @mult_course, @mult_style, @mult_frame, @mult_blood, @mult_jockey, @expected_raw, @expected_100);";

                cmd.Parameters.Add(new SqliteParameter("@race_id", SqliteType.Text));
                cmd.Parameters.Add(new SqliteParameter("@umaban", SqliteType.Integer));
                cmd.Parameters.Add(new SqliteParameter("@horse_id", SqliteType.Text));
                cmd.Parameters.Add(new SqliteParameter("@horse_name", SqliteType.Text));
                cmd.Parameters.Add(new SqliteParameter("@ability", SqliteType.Real));
                cmd.Parameters.Add(new SqliteParameter("@mult_course", SqliteType.Real));
                cmd.Parameters.Add(new SqliteParameter("@mult_style", SqliteType.Real));
                cmd.Parameters.Add(new SqliteParameter("@mult_frame", SqliteType.Real));
                cmd.Parameters.Add(new SqliteParameter("@mult_blood", SqliteType.Real));
                cmd.Parameters.Add(new SqliteParameter("@mult_jockey", SqliteType.Real));
                cmd.Parameters.Add(new SqliteParameter("@expected_raw", SqliteType.Real));
                cmd.Parameters.Add(new SqliteParameter("@expected_100", SqliteType.Real));

                int i;
                for (i = 0; i < rows.Length; i++)
                {
                    ExpectationRow r = rows[i];

                    cmd.Parameters["@race_id"].Value = r.RaceId;
                    cmd.Parameters["@umaban"].Value = r.Umaban;
                    cmd.Parameters["@horse_id"].Value = (object?)r.HorseId ?? DBNull.Value;
                    cmd.Parameters["@horse_name"].Value = (object?)r.HorseName ?? DBNull.Value;
                    cmd.Parameters["@ability"].Value = (object?)r.Ability ?? DBNull.Value;
                    cmd.Parameters["@mult_course"].Value = (object?)r.MultCourse ?? DBNull.Value;
                    cmd.Parameters["@mult_style"].Value = (object?)r.MultStyle ?? DBNull.Value;
                    cmd.Parameters["@mult_frame"].Value = (object?)r.MultFrame ?? DBNull.Value;
                    cmd.Parameters["@mult_blood"].Value = (object?)r.MultBlood ?? DBNull.Value;
                    cmd.Parameters["@mult_jockey"].Value = (object?)r.MultJockey ?? DBNull.Value;
                    cmd.Parameters["@expected_raw"].Value = (object?)r.ExpectedRaw ?? DBNull.Value;
                    cmd.Parameters["@expected_100"].Value = (object?)r.Expected100 ?? DBNull.Value;

                    cmd.ExecuteNonQuery();
                }
            }
        }

        /// <summary>
        /// dim_horse_pedigree をINSERTする。
        /// </summary>
        public static void InsertPedigrees(SqliteConnection conn, SqliteTransaction tx, PedigreeRow[] rows)
        {
            using (SqliteCommand cmd = conn.CreateCommand())
            {
                cmd.Transaction = tx;
                cmd.CommandText = @"
                    INSERT INTO dim_horse_pedigree (horse_id, sire, dam, siresire)
                    VALUES (@horse_id, @sire, @dam, @siresire);";

                cmd.Parameters.Add(new SqliteParameter("@horse_id", SqliteType.Text));
                cmd.Parameters.Add(new SqliteParameter("@sire", SqliteType.Text));
                cmd.Parameters.Add(new SqliteParameter("@dam", SqliteType.Text));
                cmd.Parameters.Add(new SqliteParameter("@siresire", SqliteType.Text));

                int i;
                for (i = 0; i < rows.Length; i++)
                {
                    PedigreeRow r = rows[i];

                    cmd.Parameters["@horse_id"].Value = r.HorseId;
                    cmd.Parameters["@sire"].Value = (object?)r.Sire ?? DBNull.Value;
                    cmd.Parameters["@dam"].Value = (object?)r.Dam ?? DBNull.Value;
                    cmd.Parameters["@siresire"].Value = (object?)r.SireSire ?? DBNull.Value;

                    cmd.ExecuteNonQuery();
                }
            }
        }
    }
}
