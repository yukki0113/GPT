using System;
using System.Globalization;
using Microsoft.Data.SqlClient;

namespace KenshowLabo.Tools.Db
{
    internal static class SqlValueReader
    {
        /// <summary>
        /// NULL文字列を安全に取得します。
        /// </summary>
        public static string ReadString(SqlDataReader reader, string columnName)
        {
            // 列の位置を特定する
            int ordinal = reader.GetOrdinal(columnName);

            // NULLなら空文字で返す
            if (reader.IsDBNull(ordinal))
            {
                return string.Empty;
            }

            // 文字列化して返す（型が揺れても吸収）
            object value = reader.GetValue(ordinal);
            string? s = Convert.ToString(value, CultureInfo.InvariantCulture);

            if (s == null)
            {
                return string.Empty;
            }

            return s;
        }

        /// <summary>
        /// DateTimeを取得します。NULLの場合は DateTime.MinValue を返します。
        /// </summary>
        public static DateTime ReadDateTime(SqlDataReader reader, string columnName)
        {
            int ordinal = reader.GetOrdinal(columnName);

            if (reader.IsDBNull(ordinal))
            {
                return DateTime.MinValue;
            }

            return reader.GetDateTime(ordinal);
        }

        /// <summary>
        /// intを取得します（型が文字列でも吸収します）。
        /// </summary>
        public static int ReadInt(SqlDataReader reader, string columnName)
        {
            int ordinal = reader.GetOrdinal(columnName);

            if (reader.IsDBNull(ordinal))
            {
                return 0;
            }

            object value = reader.GetValue(ordinal);

            if (value is int)
            {
                return (int)value;
            }

            string s = Convert.ToString(value, CultureInfo.InvariantCulture) ?? string.Empty;

            int n;
            if (int.TryParse(s, NumberStyles.Integer, CultureInfo.InvariantCulture, out n))
            {
                return n;
            }

            return 0;
        }

        /// <summary>
        /// nullable int を取得します。NULLまたは0以下は null とみなします。
        /// </summary>
        public static int? ReadNullableInt(SqlDataReader reader, string columnName)
        {
            int ordinal = reader.GetOrdinal(columnName);

            if (reader.IsDBNull(ordinal))
            {
                return null;
            }

            int n = ReadInt(reader, columnName);
            if (n <= 0)
            {
                return null;
            }

            return n;
        }

        /// <summary>
        /// nullable int を取得します。NULLは null とみなします。(0は有効)
        /// </summary>
        public static int? ReadNullableIntAllowZero(SqlDataReader reader, string columnName)
        {
            int ordinal = reader.GetOrdinal(columnName);

            if (reader.IsDBNull(ordinal))
            {
                return null;
            }

            int n = ReadInt(reader, columnName);
            return n;
        }

        /// <summary>
        /// decimalを取得します（double/float/文字列でも吸収します）。
        /// </summary>
        public static decimal ReadDecimal(SqlDataReader reader, string columnName)
        {
            int ordinal = reader.GetOrdinal(columnName);

            if (reader.IsDBNull(ordinal))
            {
                return 0m;
            }

            object value = reader.GetValue(ordinal);

            if (value is decimal)
            {
                return (decimal)value;
            }

            if (value is double)
            {
                return Convert.ToDecimal((double)value, CultureInfo.InvariantCulture);
            }

            if (value is float)
            {
                return Convert.ToDecimal((float)value, CultureInfo.InvariantCulture);
            }

            string s = Convert.ToString(value, CultureInfo.InvariantCulture) ?? string.Empty;

            decimal d;
            if (decimal.TryParse(s, NumberStyles.Number, CultureInfo.InvariantCulture, out d))
            {
                return d;
            }

            return 0m;
        }

        /// <summary>
        /// boolを取得します（0/1 や文字列 true/false も吸収します）。
        /// </summary>
        public static bool ReadBool(SqlDataReader reader, string columnName)
        {
            int ordinal = reader.GetOrdinal(columnName);

            if (reader.IsDBNull(ordinal))
            {
                return false;
            }

            object value = reader.GetValue(ordinal);

            if (value is bool)
            {
                return (bool)value;
            }

            string s = Convert.ToString(value, CultureInfo.InvariantCulture) ?? string.Empty;

            if (string.Equals(s, "1", StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }

            if (string.Equals(s, "true", StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }

            return false;
        }
    }
}
