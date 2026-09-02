using ASA.ServerManager.Application;
using ASA.ServerManager.Domain;

namespace ASA.ServerManager.Infrastructure;

/// <summary>既存のINI保存サービスをランタイムの開始処理から利用可能にします。</summary>
public sealed class IniEnabledSettingsSaver : IEnabledIniSettingsSaver
{
    private readonly IGameSettingCatalogRepository _catalogRepository;
    private readonly IniConfigurationSaveService _saveService;

    /// <summary>カタログとINI保存サービスを指定します。</summary>
    public IniEnabledSettingsSaver(IGameSettingCatalogRepository catalogRepository, IniConfigurationSaveService saveService)
    {
        _catalogRepository = catalogRepository;
        _saveService = saveService;
    }

    /// <inheritdoc />
    public async Task<OperationResult> SaveEnabledSettingsAsync(ServerSettings settings, CancellationToken cancellationToken)
    {
        OperationResult<IReadOnlyList<GameSettingDefinition>> catalogResult = await _catalogRepository.LoadAsync(cancellationToken);
        if (!catalogResult.Succeeded || catalogResult.Value is null)
        {
            return OperationResult.Failure(catalogResult.ErrorMessage ?? "ゲーム設定カタログを読み込めません。", errorCode: "CATALOG_INVALID");
        }
        string configDirectory = Path.Combine(settings.DedicatedServerPath, "ShooterGame", "Saved", "Config", "WindowsServer");
        string gameUserSettingsPath = Path.Combine(configDirectory, "GameUserSettings.ini");
        string gameIniPath = Path.Combine(configDirectory, "Game.ini");
        return await _saveService.SaveAsync(catalogResult.Value, settings.GameSettings, gameUserSettingsPath, gameIniPath, cancellationToken);
    }
}
