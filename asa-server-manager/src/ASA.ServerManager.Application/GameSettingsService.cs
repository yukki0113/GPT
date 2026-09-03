using System.Globalization;
using ASA.ServerManager.Domain;

namespace ASA.ServerManager.Application;

/// <summary>ゲーム設定カタログと1セッション分の編集状態を保持します。</summary>
public sealed class GameSettingsWorkspace
{
    /// <summary>カタログと対応する編集状態を指定します。</summary>
    public GameSettingsWorkspace(IReadOnlyList<GameSettingDefinition> definitions, IReadOnlyList<GameSettingState> states)
    {
        Definitions = definitions;
        States = states;
    }

    public IReadOnlyList<GameSettingDefinition> Definitions { get; }
    public IReadOnlyList<GameSettingState> States { get; }
}

/// <summary>DataGridへ表示する定義と編集状態の組です。</summary>
public sealed class GameSettingEditorItem
{
    /// <summary>定義と状態を関連付けます。</summary>
    public GameSettingEditorItem(GameSettingDefinition definition, GameSettingState state)
    {
        Definition = definition;
        State = state;
    }

    public GameSettingDefinition Definition { get; }
    public GameSettingState State { get; }
    public string Category => Definition.UiCategory;
    public string Name => Definition.DisplayNameJa;
    public bool Enabled { get => State.Enabled; set => State.Enabled = value; }
    public string? Value { get => State.EditedValue; set => State.EditedValue = value; }
    public string? CurrentIniValue => State.CurrentIniValue;
    public string? DefaultValue => Definition.DefaultValue;
    public string Status => GetStatusLabel(Definition.SupportStatus);

    private static string GetStatusLabel(SupportStatus status)
    {
        if (status == SupportStatus.AsaSupported)
        {
            return "ASA対応";
        }
        if (status == SupportStatus.AsaSupportedConditional)
        {
            return "条件付き";
        }
        if (status == SupportStatus.Unverified)
        {
            return "未検証";
        }
        if (status == SupportStatus.Deprecated)
        {
            return "非推奨";
        }
        return status.ToString();
    }
}

/// <summary>カテゴリ、横断検索、選択、既定値復元を純粋なUI状態として管理します。</summary>
public sealed class GameSettingsSession
{
    private readonly IReadOnlyList<GameSettingDefinition> _definitions;
    private readonly Dictionary<string, GameSettingState> _states;
    private string _selectedCategory;
    private string _previousCategory;
    private string _searchQuery = string.Empty;

    /// <summary>カタログと一意な編集状態からセッションを作成します。</summary>
    public GameSettingsSession(GameSettingsWorkspace workspace)
    {
        _definitions = workspace.Definitions;
        _states = workspace.States.ToDictionary(state => state.DefinitionId, StringComparer.Ordinal);
        Categories = _definitions.Select(definition => definition.UiCategory).Distinct(StringComparer.Ordinal).ToList();
        _selectedCategory = Categories.FirstOrDefault() ?? string.Empty;
        _previousCategory = _selectedCategory;
    }

    public IReadOnlyList<string> Categories { get; }
    public string SelectedCategory => _selectedCategory;
    public string SearchQuery => _searchQuery;
    public bool IsSearchMode => _searchQuery.Length > 0;

    /// <summary>通常表示のカテゴリを切り替えます。</summary>
    public void SelectCategory(string category)
    {
        if (!Categories.Contains(category, StringComparer.Ordinal))
        {
            return;
        }
        _selectedCategory = category;
        if (!IsSearchMode)
        {
            _previousCategory = category;
        }
    }

    /// <summary>検索文字列を設定し、空文字では直前カテゴリへ戻します。</summary>
    public void SetSearch(string query)
    {
        string normalized = query.Trim();
        if (_searchQuery.Length == 0 && normalized.Length > 0)
        {
            _previousCategory = _selectedCategory;
        }
        _searchQuery = normalized;
        if (_searchQuery.Length == 0)
        {
            _selectedCategory = _previousCategory;
        }
    }

    /// <summary>現在のカテゴリまたは全カテゴリ横断検索結果を返します。</summary>
    public IReadOnlyList<GameSettingEditorItem> GetVisibleItems()
    {
        IEnumerable<GameSettingDefinition> selected = _definitions;
        if (IsSearchMode)
        {
            selected = selected.Where(MatchesSearch);
        }
        else
        {
            selected = selected.Where(definition => string.Equals(definition.UiCategory, _selectedCategory, StringComparison.Ordinal));
        }
        return selected.Select(definition => new GameSettingEditorItem(definition, _states[definition.Id])).ToList();
    }

    /// <summary>現在カテゴリの反映状態を全選択または全解除します。検索中は拒否します。</summary>
    public OperationResult ToggleCurrentCategory()
    {
        if (IsSearchMode)
        {
            return OperationResult.Failure("検索中は全選択／全解除を使用できません。", errorCode: "GAME_SETTINGS_SEARCH_SCOPE");
        }
        IReadOnlyList<GameSettingEditorItem> items = GetVisibleItems();
        bool enable = items.Any(item => !item.Enabled);
        foreach (GameSettingEditorItem item in items)
        {
            item.Enabled = enable;
        }
        return OperationResult.Success();
    }

    /// <summary>現在カテゴリの編集値だけを既定値へ戻します。</summary>
    public OperationResult ResetCurrentCategoryDefaults()
    {
        if (IsSearchMode)
        {
            return OperationResult.Failure("検索中はカテゴリの既定値復元を使用できません。", errorCode: "GAME_SETTINGS_SEARCH_SCOPE");
        }
        foreach (GameSettingEditorItem item in GetVisibleItems())
        {
            item.Value = item.Definition.DefaultValue;
        }
        return OperationResult.Success();
    }

    private bool MatchesSearch(GameSettingDefinition definition)
    {
        return Contains(definition.DisplayNameJa) || Contains(definition.DisplayNameEn) || Contains(definition.DescriptionJa) || Contains(definition.Key) || Contains(definition.Category) || Contains(definition.UiCategory) || Contains(definition.UiSubCategory) || Contains(definition.Notes);
    }

    private bool Contains(string? value)
    {
        return value is not null && value.Contains(_searchQuery, StringComparison.OrdinalIgnoreCase);
    }
}

/// <summary>ValueTypeに応じてINIへ保存可能な文字列かを検証します。</summary>
public static class GameSettingValueValidator
{
    /// <summary>無効項目は許可し、有効項目の型と範囲を検証します。</summary>
    public static OperationResult Validate(GameSettingDefinition definition, GameSettingState state)
    {
        if (!state.Enabled)
        {
            return OperationResult.Success();
        }
        string? value = state.EditedValue;
        if (value is null)
        {
            return OperationResult.Failure($"{definition.DisplayNameJa}に値を入力してください。", errorCode: "GAME_SETTING_VALUE_REQUIRED");
        }
        if (definition.ValueType == GameSettingValueType.Integer)
        {
            if (!long.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out long integerValue))
            {
                return OperationResult.Failure($"{definition.DisplayNameJa}は整数で入力してください。", errorCode: "GAME_SETTING_VALUE_INVALID");
            }
            return ValidateRange(definition, integerValue);
        }
        if (definition.ValueType == GameSettingValueType.Decimal)
        {
            if (!decimal.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out decimal decimalValue))
            {
                return OperationResult.Failure($"{definition.DisplayNameJa}は数値で入力してください。", errorCode: "GAME_SETTING_VALUE_INVALID");
            }
            return ValidateRange(definition, decimalValue);
        }
        if (definition.ValueType == GameSettingValueType.Boolean && !string.Equals(value, "True", StringComparison.OrdinalIgnoreCase) && !string.Equals(value, "False", StringComparison.OrdinalIgnoreCase))
        {
            return OperationResult.Failure($"{definition.DisplayNameJa}はTrueまたはFalseで入力してください。", errorCode: "GAME_SETTING_VALUE_INVALID");
        }
        if (definition.ValueType == GameSettingValueType.Enum && definition.EnumValues.Count > 0 && !definition.EnumValues.Contains(value, StringComparer.OrdinalIgnoreCase))
        {
            return OperationResult.Failure($"{definition.DisplayNameJa}は選択肢から指定してください。", errorCode: "GAME_SETTING_VALUE_INVALID");
        }
        if ((definition.ValueType == GameSettingValueType.List || definition.ValueType == GameSettingValueType.Complex) && string.IsNullOrWhiteSpace(value))
        {
            return OperationResult.Failure($"{definition.DisplayNameJa}のRaw値を入力してください。", errorCode: "GAME_SETTING_VALUE_REQUIRED");
        }
        return OperationResult.Success();
    }

    private static OperationResult ValidateRange(GameSettingDefinition definition, decimal value)
    {
        if (decimal.TryParse(definition.Minimum, NumberStyles.Float, CultureInfo.InvariantCulture, out decimal minimum) && value < minimum)
        {
            return OperationResult.Failure($"{definition.DisplayNameJa}は{minimum}以上で入力してください。", errorCode: "GAME_SETTING_VALUE_OUT_OF_RANGE");
        }
        if (decimal.TryParse(definition.Maximum, NumberStyles.Float, CultureInfo.InvariantCulture, out decimal maximum) && value > maximum)
        {
            return OperationResult.Failure($"{definition.DisplayNameJa}は{maximum}以下で入力してください。", errorCode: "GAME_SETTING_VALUE_OUT_OF_RANGE");
        }
        return OperationResult.Success();
    }
}

/// <summary>カタログ、保存済み状態、INI import/saveを一つのUI用窓口へまとめます。</summary>
public sealed class GameSettingsService
{
    private readonly IGameSettingCatalogRepository _catalogRepository;
    private readonly IServerSettingsRepository _settingsRepository;
    private readonly IIniDocumentService _iniDocumentService;
    private readonly IniConfigurationSaveService _iniSaveService;
    private readonly ConfigurationOrchestrator _configurationOrchestrator = new ConfigurationOrchestrator();

    /// <summary>ゲーム設定UIが利用する既存Coreを指定します。</summary>
    public GameSettingsService(IGameSettingCatalogRepository catalogRepository, IServerSettingsRepository settingsRepository, IIniDocumentService iniDocumentService, IniConfigurationSaveService iniSaveService)
    {
        _catalogRepository = catalogRepository;
        _settingsRepository = settingsRepository;
        _iniDocumentService = iniDocumentService;
        _iniSaveService = iniSaveService;
    }

    /// <summary>335件の定義と保存済み編集状態を一対一で読み込みます。</summary>
    public async Task<OperationResult<GameSettingsWorkspace>> LoadAsync(CancellationToken cancellationToken)
    {
        OperationResult<IReadOnlyList<GameSettingDefinition>> catalogResult = await _catalogRepository.LoadAsync(cancellationToken);
        if (!catalogResult.Succeeded || catalogResult.Value is null)
        {
            return OperationResult<GameSettingsWorkspace>.Failure(catalogResult.ErrorMessage ?? "ゲーム設定カタログを読み込めません。", errorCode: "CATALOG_INVALID");
        }
        OperationResult<ServerSettings> settingsResult = await _settingsRepository.LoadAsync(cancellationToken);
        if (!settingsResult.Succeeded || settingsResult.Value is null)
        {
            return OperationResult<GameSettingsWorkspace>.Failure(settingsResult.ErrorMessage ?? "基本設定を読み込めません。", errorCode: "SETTINGS_LOAD_FAILED");
        }
        Dictionary<string, GameSettingState> saved = settingsResult.Value.GameSettings
            .GroupBy(state => state.DefinitionId, StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.First(), StringComparer.Ordinal);
        List<GameSettingState> states = [];
        foreach (GameSettingDefinition definition in catalogResult.Value)
        {
            if (saved.TryGetValue(definition.Id, out GameSettingState? state))
            {
                states.Add(state);
                continue;
            }
            states.Add(new GameSettingState { DefinitionId = definition.Id, Enabled = false, EditedValue = definition.DefaultValue });
        }
        return OperationResult<GameSettingsWorkspace>.Success(new GameSettingsWorkspace(catalogResult.Value, states));
    }

    /// <summary>既存INIの非曖昧な既知Keyをセッションへ取り込み、状態を保存します。</summary>
    public async Task<OperationResult> ImportFromIniAsync(GameSettingsWorkspace workspace, CancellationToken cancellationToken)
    {
        OperationResult<ServerSettings> settingsResult = await _settingsRepository.LoadAsync(cancellationToken);
        if (!settingsResult.Succeeded || settingsResult.Value is null)
        {
            return OperationResult.Failure(settingsResult.ErrorMessage ?? "基本設定を読み込めません。", errorCode: "SETTINGS_LOAD_FAILED");
        }
        (string gameUserSettingsPath, string gameIniPath) = GetIniPaths(settingsResult.Value);
        OperationResult<IniDocument> gusResult = await _iniDocumentService.LoadAsync(gameUserSettingsPath, IniFileKind.GameUserSettings, cancellationToken);
        OperationResult<IniDocument> gameResult = await _iniDocumentService.LoadAsync(gameIniPath, IniFileKind.Game, cancellationToken);
        if (!gusResult.Succeeded || gusResult.Value is null)
        {
            return OperationResult.Failure(gusResult.ErrorMessage ?? "GameUserSettings.iniを読み込めません。", errorCode: "INI_IMPORT_FAILED");
        }
        if (!gameResult.Succeeded || gameResult.Value is null)
        {
            return OperationResult.Failure(gameResult.ErrorMessage ?? "Game.iniを読み込めません。", errorCode: "INI_IMPORT_FAILED");
        }
        OperationResult importResult = _configurationOrchestrator.Import(workspace.Definitions, [gusResult.Value, gameResult.Value], workspace.States.ToList());
        settingsResult.Value.GameSettings = workspace.States.ToList();
        OperationResult persistResult = await _settingsRepository.SaveAsync(settingsResult.Value, cancellationToken);
        if (!persistResult.Succeeded)
        {
            return OperationResult.Failure(persistResult.ErrorMessage ?? "取り込んだ状態を保存できません。", importResult.Warnings, "SETTINGS_SAVE_FAILED");
        }
        return importResult;
    }

    /// <summary>全有効値を検証し、編集状態とINIを非破壊保存します。</summary>
    public async Task<OperationResult> SaveToIniAsync(GameSettingsWorkspace workspace, CancellationToken cancellationToken)
    {
        Dictionary<string, GameSettingDefinition> definitions = workspace.Definitions.ToDictionary(definition => definition.Id, StringComparer.Ordinal);
        foreach (GameSettingState state in workspace.States)
        {
            if (!definitions.TryGetValue(state.DefinitionId, out GameSettingDefinition? definition))
            {
                return OperationResult.Failure("不明なゲーム設定状態があります。", errorCode: "CATALOG_STATE_MISMATCH");
            }
            OperationResult validation = GameSettingValueValidator.Validate(definition, state);
            if (!validation.Succeeded)
            {
                state.ValidationState = ValidationState.Invalid;
                return validation;
            }
            state.ValidationState = ValidationState.Valid;
        }
        OperationResult<ServerSettings> settingsResult = await _settingsRepository.LoadAsync(cancellationToken);
        if (!settingsResult.Succeeded || settingsResult.Value is null)
        {
            return OperationResult.Failure(settingsResult.ErrorMessage ?? "基本設定を読み込めません。", errorCode: "SETTINGS_LOAD_FAILED");
        }
        settingsResult.Value.GameSettings = workspace.States.ToList();
        OperationResult settingsSave = await _settingsRepository.SaveAsync(settingsResult.Value, cancellationToken);
        if (!settingsSave.Succeeded)
        {
            return OperationResult.Failure(settingsSave.ErrorMessage ?? "編集状態を保存できません。", errorCode: "SETTINGS_SAVE_FAILED");
        }
        (string gameUserSettingsPath, string gameIniPath) = GetIniPaths(settingsResult.Value);
        OperationResult saveResult = await _iniSaveService.SaveAsync(workspace.Definitions, workspace.States, gameUserSettingsPath, gameIniPath, cancellationToken);
        if (!saveResult.Succeeded)
        {
            return saveResult;
        }
        return await ImportFromIniAsync(workspace, cancellationToken);
    }

    private static (string GameUserSettingsPath, string GameIniPath) GetIniPaths(ServerSettings settings)
    {
        string directory = Path.Combine(settings.DedicatedServerPath, "ShooterGame", "Saved", "Config", "WindowsServer");
        return (Path.Combine(directory, "GameUserSettings.ini"), Path.Combine(directory, "Game.ini"));
    }
}
