using ASA.ServerManager.Domain;

namespace ASA.ServerManager.Application;

/// <summary>カタログ、編集状態、INIドキュメント間の変換を担います。</summary>
public sealed class ConfigurationOrchestrator
{
    /// <summary>既知の非曖昧キーだけをINIの値で有効化します。</summary>
    public OperationResult Import(IReadOnlyList<GameSettingDefinition> definitions, IEnumerable<IniDocument> documents, IList<GameSettingState> states)
    {
        Dictionary<string, GameSettingState> stateById = states.ToDictionary(state => state.DefinitionId, StringComparer.Ordinal);
        List<string> warnings = [];
        foreach (GameSettingDefinition definition in definitions)
        {
            List<IniKeyValueNode> matches = documents.Where(document => document.FileKind == definition.FileKind).SelectMany(document => document.FindKeys(definition.Section, definition.Key)).ToList();
            if (matches.Count > 1)
            {
                warnings.Add($"重複キー: {definition.FileKind}/{definition.Section}/{definition.Key}");
                continue;
            }
            if (matches.Count == 1 && stateById.TryGetValue(definition.Id, out GameSettingState? state))
            {
                state.EditedValue = matches[0].Value;
                state.CurrentIniValue = matches[0].Value;
                state.ExistsInIni = true;
                state.Enabled = true;
            }
        }
        return OperationResult.Success(warnings);
    }

    /// <summary>有効な編集状態だけをドキュメントへ反映します。無効状態は削除を意味しません。</summary>
    public OperationResult Apply(IReadOnlyList<GameSettingDefinition> definitions, IEnumerable<IniDocument> documents, IReadOnlyList<GameSettingState> states)
    {
        Dictionary<string, GameSettingDefinition> definitionById = definitions.ToDictionary(definition => definition.Id, StringComparer.Ordinal);
        Dictionary<IniFileKind, IniDocument> documentByFile = documents.ToDictionary(document => document.FileKind);
        List<string> warnings = [];
        foreach (GameSettingState state in states.Where(state => state.Enabled))
        {
            if (!definitionById.TryGetValue(state.DefinitionId, out GameSettingDefinition? definition))
            {
                warnings.Add($"不明な設定IDを保存対象から除外しました: {state.DefinitionId}");
                continue;
            }
            if (!documentByFile.TryGetValue(definition.FileKind, out IniDocument? document))
            {
                return OperationResult.Failure($"対象INIドキュメントがありません: {definition.FileKind}", warnings);
            }
            if (state.EditedValue is null)
            {
                return OperationResult.Failure($"有効な設定に値がありません: {definition.Id}", warnings);
            }
            if (document.FindKeys(definition.Section, definition.Key).Count > 1)
            {
                return OperationResult.Failure($"重複キーのため自動保存できません: {definition.Section}/{definition.Key}", warnings);
            }
            document.SetValue(definition.Section, definition.Key, state.EditedValue);
        }
        return OperationResult.Success(warnings);
    }
}
