using ASA.ServerManager.Domain;

namespace ASA.ServerManager.Application;

/// <summary>INIの再読込、バックアップ、反映、保存を安全な順序で実行します。</summary>
public sealed class IniConfigurationSaveService(IIniDocumentService iniDocumentService, IBackupService backupService)
{
    private readonly IIniDocumentService _iniDocumentService = iniDocumentService;
    private readonly IBackupService _backupService = backupService;
    private readonly ConfigurationOrchestrator _orchestrator = new ConfigurationOrchestrator();

    /// <summary>現在のINIを読み直してから、バックアップを作成し、編集値を保存します。</summary>
    public async Task<OperationResult> SaveAsync(
        IReadOnlyList<GameSettingDefinition> definitions,
        IReadOnlyList<GameSettingState> states,
        string gameUserSettingsPath,
        string gameIniPath,
        CancellationToken cancellationToken)
    {
        // 保存直前にファイルを読み直し、画面表示時点との差分を上書きしないようにします。
        OperationResult<IniDocument> gusResult = await _iniDocumentService.LoadAsync(gameUserSettingsPath, IniFileKind.GameUserSettings, cancellationToken);
        if (!gusResult.Succeeded || gusResult.Value is null)
        {
            return OperationResult.Failure(gusResult.ErrorMessage ?? "GameUserSettings.iniを読み込めません。");
        }
        OperationResult<IniDocument> gameResult = await _iniDocumentService.LoadAsync(gameIniPath, IniFileKind.Game, cancellationToken);
        if (!gameResult.Succeeded || gameResult.Value is null)
        {
            return OperationResult.Failure(gameResult.ErrorMessage ?? "Game.iniを読み込めません。");
        }

        List<IniDocument> documents = [gusResult.Value, gameResult.Value];
        OperationResult applyResult = _orchestrator.Apply(definitions, documents, states);
        if (!applyResult.Succeeded)
        {
            return applyResult;
        }

        // バックアップ成功を確認するまで元INIへは書き込みません。
        OperationResult<string> backupResult = await _backupService.BackupIniAsync([gameUserSettingsPath, gameIniPath], cancellationToken);
        if (!backupResult.Succeeded)
        {
            return OperationResult.Failure(backupResult.ErrorMessage ?? "INIバックアップに失敗しました。", applyResult.Warnings);
        }

        OperationResult gusSave = await _iniDocumentService.SaveAsync(gameUserSettingsPath, gusResult.Value, cancellationToken);
        if (!gusSave.Succeeded)
        {
            return gusSave;
        }
        OperationResult gameSave = await _iniDocumentService.SaveAsync(gameIniPath, gameResult.Value, cancellationToken);
        if (!gameSave.Succeeded)
        {
            return gameSave;
        }

        // 保存後に再読込できることを確認して、部分的な壊れ方を早期に検知します。
        OperationResult<IniDocument> gusVerification = await _iniDocumentService.LoadAsync(gameUserSettingsPath, IniFileKind.GameUserSettings, cancellationToken);
        OperationResult<IniDocument> gameVerification = await _iniDocumentService.LoadAsync(gameIniPath, IniFileKind.Game, cancellationToken);
        if (!gusVerification.Succeeded || !gameVerification.Succeeded)
        {
            return OperationResult.Failure("保存後のINI再読込検証に失敗しました。", applyResult.Warnings);
        }
        return OperationResult.Success(applyResult.Warnings);
    }
}
