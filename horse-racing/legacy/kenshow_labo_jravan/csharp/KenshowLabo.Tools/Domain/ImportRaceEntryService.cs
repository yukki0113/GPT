using KenshowLabo.Tools.Config;
using KenshowLabo.Tools.Db;
using KenshowLabo.Tools.Models;
using Microsoft.Extensions.Configuration;
using System;
using System.Collections.Generic;
using Microsoft.Data.SqlClient;

namespace KenshowLabo.Tools.Domain
{
    /// <summary>
    /// 出馬表をSQL Serverへ取り込むユースケースです。
    /// </summary>
    public sealed class ImportRaceEntryService
    {
        private readonly string _connectionString;
        private readonly IIfRaceEntryRepository _repository;

        /// <summary>
        /// コンストラクタ。
        /// </summary>
        public ImportRaceEntryService(string connectionString, IIfRaceEntryRepository repository)
        {
            _connectionString = connectionString;
            _repository = repository;
        }

        public void Import(string raceId, IEnumerable<IfRaceEntryRow> rows)
        {
            DbUtil.ExecuteInTransaction(_connectionString, (SqlConnection conn, SqlTransaction tx) =>
            {
                _repository.DeleteByRaceId(conn, tx, raceId);
                _repository.InsertMany(conn, tx, rows);
            });
        }
    }
}
