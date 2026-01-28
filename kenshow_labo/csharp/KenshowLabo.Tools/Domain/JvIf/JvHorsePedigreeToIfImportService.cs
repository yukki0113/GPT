using System;
using System.Collections.Generic;
using Microsoft.Data.SqlClient;
using KenshowLabo.Tools.Db;
using KenshowLabo.Tools.Db.JvIf;
using KenshowLabo.Tools.Models.JvIf;

namespace KenshowLabo.Tools.Domain.JvIf
{
    /// <summary>
    /// 血統（SQLite→IF）補完サービス
    /// </summary>
    public sealed class JvHorsePedigreeToIfImportService
    {
        private readonly string _sqlServerConnectionString;
        private readonly string _sqliteConnectionString;

        private readonly JvSqliteHorsePedigreeReader _sqliteReader;
        private readonly IfJvHorsePedigreeRepository _repo;

        /// <summary>
        /// コンストラクタ
        /// </summary>
        public JvHorsePedigreeToIfImportService(string sqlServerConnectionString, string sqliteConnectionString)
        {
            _sqlServerConnectionString = sqlServerConnectionString;
            _sqliteConnectionString = sqliteConnectionString;

            _sqliteReader = new JvSqliteHorsePedigreeReader(_sqliteConnectionString);
            _repo = new IfJvHorsePedigreeRepository();
        }

        /// <summary>
        /// IF_JV_RaceUma を起点に、MT_HorsePedigree 未登録の馬だけ血統をIFへ補完します。
        /// </summary>
        public void ImportMissing(int batchSize = 1000)
        {
            // 未登録horse_id一覧をSQLServerから取得
            List<string> horseIds = GetMissingHorseIds();

            Console.WriteLine("[IF_JV_HorsePedigree] missing horse_ids=" + horseIds.Count.ToString());

            if (horseIds.Count == 0)
            {
                return;
            }

            // バッチで回す（IN句肥大化防止）
            int index = 0;
            while (index < horseIds.Count)
            {
                int take = batchSize;
                int remain = horseIds.Count - index;
                if (remain < take)
                {
                    take = remain;
                }

                List<string> batch = horseIds.GetRange(index, take);

                // SQLiteから取得（馬ごとに最新1件）
                List<IfJvHorsePedigreeRow> rows = _sqliteReader.ReadByHorseIds(batch);

                // 取れなかったhorse_idもあり得るので、DELETE対象は batch のままにするか、rowsに絞るか選べます。
                // IFを軽量に保つなら「取れた分だけDELETE→INSERT」でもOKですが、ここでは整合優先で batch を削除します。
                DbUtil.ExecuteInTransaction(_sqlServerConnectionString, (SqlConnection conn, SqlTransaction tx) =>
                {
                    _repo.DeleteByHorseIds(conn, tx, batch);
                    _repo.BulkInsert(conn, tx, rows);
                });

                Console.WriteLine("[IF_JV_HorsePedigree] batch=" + batch.Count.ToString() + " inserted=" + rows.Count.ToString());

                index += take;
            }
        }

        /// <summary>
        /// 未登録horse_idを抽出します（IF_JV_RaceUma → MT_HorsePedigree 未登録）
        /// </summary>
        private List<string> GetMissingHorseIds()
        {
            string sql =
@"
SELECT DISTINCT u.horse_id
FROM dbo.IF_JV_RaceUma u
LEFT JOIN dbo.MT_HorsePedigree m
  ON m.horse_id = u.horse_id
WHERE u.horse_id IS NOT NULL
  AND LTRIM(RTRIM(u.horse_id)) <> ''
  AND m.horse_id IS NULL
";

            List<string> list = DbUtil.QueryToList(
                _sqlServerConnectionString,
                sql,
                (SqlParameterCollection p) => { },
                (SqlDataReader r) =>
                {
                    string value = r.GetString(0);
                    if (value == null)
                    {
                        return string.Empty;
                    }
                    return value.Trim();
                },
                commandTimeoutSeconds: 300);

            // 念のため空を除去
            List<string> cleaned = new List<string>();
            for (int i = 0; i < list.Count; i++)
            {
                string id = list[i];
                if (!string.IsNullOrWhiteSpace(id))
                {
                    cleaned.Add(id);
                }
            }

            return cleaned;
        }
    }
}
