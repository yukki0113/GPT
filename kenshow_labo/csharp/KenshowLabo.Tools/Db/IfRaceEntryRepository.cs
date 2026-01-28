using KenshowLabo.Tools.Models;
using System.Collections.Generic;
using Microsoft.Data.SqlClient;

namespace KenshowLabo.Tools.Db
{
    /// <summary>
    /// IF系の出馬表（RaceEntry）永続化を担当します。
    /// </summary>
    public interface IIfRaceEntryRepository
    {
        /// <summary>
        /// 指定 race_id の出馬表行を削除します。
        /// </summary>
        int DeleteByRaceId(SqlConnection conn, SqlTransaction tx, string raceId);

        /// <summary>
        /// 出馬表行を一括挿入します。
        /// </summary>
        int InsertMany(SqlConnection conn, SqlTransaction tx, IEnumerable<IfRaceEntryRow> rows);
    }
}
