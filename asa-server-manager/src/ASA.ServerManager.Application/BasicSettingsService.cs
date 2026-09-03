using ASA.ServerManager.Domain;

namespace ASA.ServerManager.Application;

/// <summary>基本設定とDPAPI秘密情報の読み込み、検証、保存を調整します。</summary>
public sealed class BasicSettingsService
{
    private readonly IServerSettingsRepository _settingsRepository;
    private readonly ISecretRepository _secretRepository;
    private readonly IMapDefinitionRepository _mapRepository;

    /// <summary>各永続化Repositoryを指定します。</summary>
    public BasicSettingsService(IServerSettingsRepository settingsRepository, ISecretRepository secretRepository, IMapDefinitionRepository mapRepository)
    {
        _settingsRepository = settingsRepository;
        _secretRepository = secretRepository;
        _mapRepository = mapRepository;
    }

    /// <summary>基本設定、秘密情報、MAP定義を一括して読み込みます。</summary>
    public async Task<OperationResult<BasicSettingsData>> LoadAsync(CancellationToken cancellationToken)
    {
        OperationResult<ServerSettings> settingsResult = await _settingsRepository.LoadAsync(cancellationToken);
        if (!settingsResult.Succeeded || settingsResult.Value is null)
        {
            return OperationResult<BasicSettingsData>.Failure(settingsResult.ErrorMessage ?? "基本設定を読み込めません。", errorCode: "SETTINGS_LOAD_FAILED");
        }
        OperationResult<ServerSecrets> secretsResult = await _secretRepository.LoadAsync(cancellationToken);
        if (!secretsResult.Succeeded || secretsResult.Value is null)
        {
            return OperationResult<BasicSettingsData>.Failure(secretsResult.ErrorMessage ?? "秘密情報を読み込めません。", errorCode: "SECRETS_LOAD_FAILED");
        }
        OperationResult<IReadOnlyList<MapDefinition>> mapsResult = await _mapRepository.LoadAsync(cancellationToken);
        if (!mapsResult.Succeeded || mapsResult.Value is null)
        {
            return OperationResult<BasicSettingsData>.Failure(mapsResult.ErrorMessage ?? "MAP定義を読み込めません。", errorCode: mapsResult.ErrorCode ?? "MAP_CATALOG_INVALID");
        }
        return OperationResult<BasicSettingsData>.Success(new BasicSettingsData { Settings = settingsResult.Value, Secrets = secretsResult.Value, Maps = mapsResult.Value });
    }

    /// <summary>入力を検証し、平文設定と秘密情報を別々に保存して再読込を確認します。</summary>
    public async Task<OperationResult<BasicSettingsData>> SaveAsync(ServerSettings candidate, ServerSecrets secrets, bool serverIsRunning, CancellationToken cancellationToken)
    {
        OperationResult<IReadOnlyList<MapDefinition>> mapsResult = await _mapRepository.LoadAsync(cancellationToken);
        if (!mapsResult.Succeeded || mapsResult.Value is null)
        {
            return OperationResult<BasicSettingsData>.Failure(mapsResult.ErrorMessage ?? "MAP定義を読み込めません。", errorCode: mapsResult.ErrorCode ?? "MAP_CATALOG_INVALID");
        }
        OperationResult validation = BasicSettingsValidator.Validate(candidate, secrets, mapsResult.Value);
        if (!validation.Succeeded)
        {
            return OperationResult<BasicSettingsData>.Failure(validation.ErrorMessage ?? "入力内容を確認してください。", validation.Warnings, validation.ErrorCode);
        }

        // 他タブで保持しているMODとゲーム設定を、基本設定の保存で巻き戻さないよう最新値を引き継ぎます。
        OperationResult<ServerSettings> currentResult = await _settingsRepository.LoadAsync(cancellationToken);
        if (!currentResult.Succeeded || currentResult.Value is null)
        {
            return OperationResult<BasicSettingsData>.Failure(currentResult.ErrorMessage ?? "現在の設定を読み込めません。", errorCode: "SETTINGS_LOAD_FAILED");
        }
        candidate.Mods = currentResult.Value.Mods;
        candidate.GameSettings = currentResult.Value.GameSettings;

        OperationResult saveSettings = await _settingsRepository.SaveAsync(candidate, cancellationToken);
        if (!saveSettings.Succeeded)
        {
            return OperationResult<BasicSettingsData>.Failure(saveSettings.ErrorMessage ?? "基本設定を保存できません。", errorCode: "SETTINGS_SAVE_FAILED");
        }
        OperationResult saveSecrets = await _secretRepository.SaveAsync(secrets, cancellationToken);
        if (!saveSecrets.Succeeded)
        {
            return OperationResult<BasicSettingsData>.Failure(saveSecrets.ErrorMessage ?? "秘密情報を保存できません。", errorCode: "SECRETS_SAVE_FAILED");
        }
        OperationResult<BasicSettingsData> reloaded = await LoadAsync(cancellationToken);
        if (!reloaded.Succeeded || reloaded.Value is null)
        {
            return OperationResult<BasicSettingsData>.Failure("保存後の設定を再読込できません。", errorCode: "SETTINGS_ROUNDTRIP_FAILED");
        }
        List<string> warnings = [];
        if (serverIsRunning)
        {
            warnings.Add("変更は次回の起動／再起動時に反映されます。");
        }
        return OperationResult<BasicSettingsData>.Success(reloaded.Value, warnings);
    }
}

/// <summary>基本設定の画面入力を保存前に検証します。</summary>
public static class BasicSettingsValidator
{
    /// <summary>必須値、ポート、RCON、MAP、追加引数を検証します。</summary>
    public static OperationResult Validate(ServerSettings settings, ServerSecrets secrets, IReadOnlyList<MapDefinition> maps)
    {
        List<string> errors = [];
        if (string.IsNullOrWhiteSpace(settings.DedicatedServerPath))
        {
            errors.Add("ASA Dedicated Server Pathを入力してください。");
        }
        if (string.IsNullOrWhiteSpace(settings.SteamCmdPath))
        {
            errors.Add("SteamCMD Pathを入力してください。");
        }
        if (string.IsNullOrWhiteSpace(settings.ServerName))
        {
            errors.Add("サーバー名を入力してください。");
        }
        if (settings.MaxPlayers < 1 || settings.MaxPlayers > 1000)
        {
            errors.Add("最大参加人数は1から1000で入力してください。");
        }
        ValidateMap(settings, maps, errors);
        ValidatePorts(settings.Ports, errors);
        if (settings.RconEnabled && string.IsNullOrWhiteSpace(secrets.RconPassword))
        {
            errors.Add("RCONを有効にする場合はRCON Passwordが必要です。");
        }
        if (settings.ExposeRcon && !settings.RconEnabled)
        {
            errors.Add("RCON外部公開にはRCON有効化が必要です。");
        }
        if (settings.ExtraArguments.Contains("-mods=", StringComparison.OrdinalIgnoreCase))
        {
            errors.Add("Extra Argumentsへ-mods=を指定できません。MODタブを使用してください。");
        }
        if (errors.Count > 0)
        {
            return OperationResult.Failure(string.Join(Environment.NewLine, errors), errorCode: "CFG_VALIDATION_FAILED");
        }
        return OperationResult.Success();
    }

    private static void ValidateMap(ServerSettings settings, IReadOnlyList<MapDefinition> maps, List<string> errors)
    {
        if (string.IsNullOrWhiteSpace(settings.MapId) || string.IsNullOrWhiteSpace(settings.MapLevelName))
        {
            errors.Add("MAPとMAP Level Nameを指定してください。");
            return;
        }
        if (string.Equals(settings.MapId, "custom", StringComparison.OrdinalIgnoreCase))
        {
            if (string.IsNullOrWhiteSpace(settings.CustomMapModProjectId) || !settings.CustomMapModProjectId.All(char.IsDigit))
            {
                errors.Add("カスタムMAPには数字のMOD Project IDが必要です。");
            }
            return;
        }
        MapDefinition? map = maps.FirstOrDefault(item => string.Equals(item.Id, settings.MapId, StringComparison.OrdinalIgnoreCase));
        if (map is null)
        {
            errors.Add("MAP定義に存在するMAPを選択してください。");
            return;
        }
        if (!string.Equals(map.LevelName, settings.MapLevelName, StringComparison.Ordinal))
        {
            errors.Add("選択MAPとMAP Level Nameが一致していません。");
        }
        if (!string.IsNullOrWhiteSpace(settings.CustomMapModProjectId))
        {
            errors.Add("公式MAPではCustom Map MOD Project IDを空にしてください。");
        }
    }

    private static void ValidatePorts(PortSettings ports, List<string> errors)
    {
        int[] values = [ports.GamePort, ports.PeerPort, ports.QueryPort, ports.RconPort];
        if (values.Any(port => port < 1 || port > 65535))
        {
            errors.Add("Portは1から65535で入力してください。");
        }
        if (values.Distinct().Count() != values.Length)
        {
            errors.Add("各Portは重複しない値を指定してください。");
        }
    }
}
