using System.Text.Json;
using ASA.ServerManager.Application;
using ASA.ServerManager.Domain;

namespace ASA.ServerManager.Infrastructure;

/// <summary>外部JSONのゲーム設定カタログを検証して読み込みます。</summary>
public sealed class JsonGameSettingCatalogRepository(string catalogPath) : IGameSettingCatalogRepository
{
    private readonly string _catalogPath = catalogPath;
    private static readonly JsonSerializerOptions Options = new() { PropertyNameCaseInsensitive = true };
    /// <inheritdoc />
    public async Task<OperationResult<IReadOnlyList<GameSettingDefinition>>> LoadAsync(CancellationToken cancellationToken)
    {
        try
        {
            if (!File.Exists(_catalogPath)) { return OperationResult<IReadOnlyList<GameSettingDefinition>>.Failure($"設定カタログが見つかりません: {_catalogPath}"); }
            await using FileStream stream = File.OpenRead(_catalogPath);
            List<CatalogDto>? records = await JsonSerializer.DeserializeAsync<List<CatalogDto>>(stream, Options, cancellationToken);
            if (records is null) { return OperationResult<IReadOnlyList<GameSettingDefinition>>.Failure("設定カタログが空です。"); }
            List<string> dtoErrors = ValidateDtos(records);
            if (dtoErrors.Count > 0) { return OperationResult<IReadOnlyList<GameSettingDefinition>>.Failure(string.Join(Environment.NewLine, dtoErrors)); }
            List<GameSettingDefinition> definitions = records.Select(Convert).ToList();
            List<string> errors = Validate(definitions);
            if (errors.Count > 0) { return OperationResult<IReadOnlyList<GameSettingDefinition>>.Failure(string.Join(Environment.NewLine, errors)); }
            return OperationResult<IReadOnlyList<GameSettingDefinition>>.Success(definitions);
        }
        catch (JsonException exception) { return OperationResult<IReadOnlyList<GameSettingDefinition>>.Failure($"設定カタログJSONが不正です: {exception.Message}"); }
        catch (Exception exception) { return OperationResult<IReadOnlyList<GameSettingDefinition>>.Failure($"設定カタログの読込に失敗しました: {exception.Message}"); }
    }
    private static List<string> Validate(IReadOnlyList<GameSettingDefinition> definitions)
    {
        List<string> errors = [];
        if (definitions.Any(x => string.IsNullOrWhiteSpace(x.Id) || string.IsNullOrWhiteSpace(x.DisplayNameJa) || string.IsNullOrWhiteSpace(x.Category) || string.IsNullOrWhiteSpace(x.Section) || string.IsNullOrWhiteSpace(x.Key))) { errors.Add("設定カタログに必須項目が不足しています。"); }
        if (definitions.GroupBy(x => x.Id, StringComparer.OrdinalIgnoreCase).Any(x => x.Count() > 1)) { errors.Add("設定カタログにID重複があります。"); }
        if (definitions.GroupBy(x => x.GetIdentity().ToLookupKey(), StringComparer.Ordinal).Any(x => x.Count() > 1)) { errors.Add("設定カタログにfile + section + key重複があります。"); }
        return errors;
    }

    private static List<string> ValidateDtos(IReadOnlyList<CatalogDto> records)
    {
        List<string> errors = [];
        foreach (CatalogDto record in records)
        {
            if (!string.Equals(record.File, "Game.ini", StringComparison.OrdinalIgnoreCase) && !string.Equals(record.File, "GameUserSettings.ini", StringComparison.OrdinalIgnoreCase))
            {
                errors.Add($"設定カタログに未対応のfile値があります: {record.File}");
            }
            if (!IsSupportedValueType(record.ValueType))
            {
                errors.Add($"設定カタログに未対応のvalueType値があります: {record.ValueType}");
            }
            if (!IsSupportedStatus(record.SupportStatus))
            {
                errors.Add($"設定カタログに未対応のsupportStatus値があります: {record.SupportStatus}");
            }
        }
        return errors;
    }

    private static bool IsSupportedValueType(string? value)
    {
        return string.Equals(value, "boolean", StringComparison.OrdinalIgnoreCase) || string.Equals(value, "integer", StringComparison.OrdinalIgnoreCase) || string.Equals(value, "decimal", StringComparison.OrdinalIgnoreCase) || string.Equals(value, "string", StringComparison.OrdinalIgnoreCase) || string.Equals(value, "enum", StringComparison.OrdinalIgnoreCase) || string.Equals(value, "list", StringComparison.OrdinalIgnoreCase) || string.Equals(value, "complex", StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsSupportedStatus(string? value)
    {
        return string.Equals(value, "ASA_SUPPORTED", StringComparison.Ordinal) || string.Equals(value, "ASA_SUPPORTED_CONDITIONAL", StringComparison.Ordinal) || string.Equals(value, "ASA_MAP_SPECIFIC", StringComparison.Ordinal) || string.Equals(value, "DEPRECATED", StringComparison.Ordinal) || string.Equals(value, "ASE_ONLY", StringComparison.Ordinal) || string.Equals(value, "UNVERIFIED", StringComparison.Ordinal);
    }
    private static GameSettingDefinition Convert(CatalogDto dto)
    {
        IniFileKind fileKind = IniFileKind.GameUserSettings;
        if (string.Equals(dto.File, "Game.ini", StringComparison.OrdinalIgnoreCase))
        {
            fileKind = IniFileKind.Game;
        }
        return new GameSettingDefinition { Id = dto.Id ?? string.Empty, DisplayNameJa = dto.DisplayNameJa ?? string.Empty, DisplayNameEn = dto.DisplayNameEn ?? string.Empty, Category = dto.Category ?? string.Empty, FileKind = fileKind, Section = dto.Section ?? string.Empty, Key = dto.Key ?? string.Empty, ValueType = ParseValueType(dto.ValueType), DefaultValue = dto.DefaultValue?.ToString(), SupportStatus = ParseSupportStatus(dto.SupportStatus), Deprecated = dto.Deprecated, RestartRequired = dto.RestartRequired, Sources = dto.Source ?? [], Notes = dto.Notes ?? string.Empty };
    }
    private static GameSettingValueType ParseValueType(string? value) => value?.ToLowerInvariant() switch { "boolean" => GameSettingValueType.Boolean, "integer" => GameSettingValueType.Integer, "decimal" => GameSettingValueType.Decimal, "enum" => GameSettingValueType.Enum, "list" => GameSettingValueType.List, "complex" => GameSettingValueType.Complex, _ => GameSettingValueType.String };
    private static SupportStatus ParseSupportStatus(string? value) => value switch { "ASA_SUPPORTED" => SupportStatus.AsaSupported, "ASA_SUPPORTED_CONDITIONAL" => SupportStatus.AsaSupportedConditional, "ASA_MAP_SPECIFIC" => SupportStatus.AsaMapSpecific, "DEPRECATED" => SupportStatus.Deprecated, "ASE_ONLY" => SupportStatus.AseOnly, "UNVERIFIED" => SupportStatus.Unverified, _ => SupportStatus.Unknown };
    private sealed class CatalogDto { public string? Id { get; set; } public string? DisplayNameJa { get; set; } public string? DisplayNameEn { get; set; } public string? Category { get; set; } public string? File { get; set; } public string? Section { get; set; } public string? Key { get; set; } public string? ValueType { get; set; } public JsonElement? DefaultValue { get; set; } public string? SupportStatus { get; set; } public bool Deprecated { get; set; } public bool RestartRequired { get; set; } public List<string>? Source { get; set; } public string? Notes { get; set; } }
}
