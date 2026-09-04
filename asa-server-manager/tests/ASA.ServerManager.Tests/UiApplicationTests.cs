using ASA.ServerManager.Application;
using ASA.ServerManager.Domain;
using ASA.ServerManager.Infrastructure;

namespace ASA.ServerManager.Tests;

public sealed class BasicSettingsServiceTests
{
    [Fact]
    public async Task LoadAsync_MapsSettingsSecretsAndMaps()
    {
        UiSettingsRepository settings = new UiSettingsRepository(CreateValidSettings());
        UiSecretRepository secrets = new UiSecretRepository(new ServerSecrets { RconPassword = "rcon" });
        BasicSettingsService service = new BasicSettingsService(settings, secrets, new UiMapRepository());

        OperationResult<BasicSettingsData> result = await service.LoadAsync(CancellationToken.None);

        Assert.True(result.Succeeded);
        Assert.Equal("ASA", result.Value?.Settings.ServerName);
        Assert.Equal("rcon", result.Value?.Secrets.RconPassword);
        Assert.Single(result.Value?.Maps ?? []);
    }

    [Fact]
    public async Task SaveAsync_ValidSettingsSavesSecretsSeparatelyAndDoesNotRestart()
    {
        ServerSettings initial = CreateValidSettings();
        initial.Mods = [new ModDefinition { ProjectId = "100", Name = "mod", Enabled = true, Order = 0 }];
        UiSettingsRepository settings = new UiSettingsRepository(initial);
        UiSecretRepository secrets = new UiSecretRepository(new ServerSecrets());
        BasicSettingsService service = new BasicSettingsService(settings, secrets, new UiMapRepository());
        ServerSettings candidate = CreateValidSettings();
        candidate.ServerName = "Changed";

        OperationResult<BasicSettingsData> result = await service.SaveAsync(candidate, new ServerSecrets { RconPassword = "secret" }, true, CancellationToken.None);

        Assert.True(result.Succeeded, result.ErrorMessage);
        Assert.Equal("Changed", settings.Settings.ServerName);
        Assert.Equal("secret", secrets.Secrets.RconPassword);
        Assert.Single(settings.Settings.Mods);
        Assert.Contains(result.Warnings, warning => warning.Contains("次回", StringComparison.Ordinal));
    }

    [Fact]
    public void Validate_RejectsInvalidAndDuplicatePorts()
    {
        ServerSettings invalid = CreateValidSettings();
        invalid.Ports.GamePort = 0;
        invalid.Ports.PeerPort = invalid.Ports.QueryPort;

        OperationResult result = BasicSettingsValidator.Validate(invalid, new ServerSecrets { RconPassword = "rcon" }, new UiMapRepository().Maps);

        Assert.False(result.Succeeded);
        Assert.Contains("1から65535", result.ErrorMessage);
        Assert.Contains("重複", result.ErrorMessage);
    }

    [Fact]
    public void Validate_RejectsRconWithoutPasswordAndModsArgument()
    {
        ServerSettings invalid = CreateValidSettings();
        invalid.ExtraArguments = "-NoBattlEye -mods=123";

        OperationResult result = BasicSettingsValidator.Validate(invalid, new ServerSecrets(), new UiMapRepository().Maps);

        Assert.False(result.Succeeded);
        Assert.Contains("RCON Password", result.ErrorMessage);
        Assert.Contains("-mods=", result.ErrorMessage);
    }

    internal static ServerSettings CreateValidSettings()
    {
        return new ServerSettings
        {
            DedicatedServerPath = "C:\\ASA",
            SteamCmdPath = "C:\\SteamCMD",
            MapId = "the-island",
            MapLevelName = "TheIsland_WP",
            ServerName = "ASA",
            MaxPlayers = 20,
            RconEnabled = true,
            Ports = new PortSettings { GamePort = 7777, PeerPort = 7778, QueryPort = 27015, RconPort = 27020 }
        };
    }
}

public sealed class ModSettingsServiceTests
{
    [Fact]
    public void Add_RejectsDuplicateAndEmptyProjectId()
    {
        ModSettingsService service = new ModSettingsService(new UiSettingsRepository(BasicSettingsServiceTests.CreateValidSettings()));
        IReadOnlyList<ModDefinition> mods = [new ModDefinition { ProjectId = "123", Enabled = true, Order = 0 }];

        Assert.False(service.Add(mods, "123", "duplicate").Succeeded);
        Assert.False(service.Add(mods, "", "empty").Succeeded);
        Assert.False(service.Add(mods, "abc", "text").Succeeded);
    }

    [Fact]
    public void AddRemoveAndMove_ReassignsStableOrderAndKeepsDisabledState()
    {
        ModSettingsService service = new ModSettingsService(new UiSettingsRepository(BasicSettingsServiceTests.CreateValidSettings()));
        IReadOnlyList<ModDefinition> mods = [new ModDefinition { ProjectId = "100", Name = "one", Enabled = false, Order = 0 }];
        OperationResult<IReadOnlyList<ModDefinition>> added = service.Add(mods, "200", "two");
        OperationResult<IReadOnlyList<ModDefinition>> moved = service.MoveUp(added.Value ?? [], 1);
        OperationResult<IReadOnlyList<ModDefinition>> removed = service.Remove(moved.Value ?? [], 0);

        Assert.True(removed.Succeeded);
        ModDefinition remaining = Assert.Single(removed.Value ?? []);
        Assert.Equal("100", remaining.ProjectId);
        Assert.False(remaining.Enabled);
        Assert.Equal(0, remaining.Order);
    }

    [Fact]
    public async Task SaveLoad_RoundTripsOrderAndEnabledState()
    {
        UiSettingsRepository repository = new UiSettingsRepository(BasicSettingsServiceTests.CreateValidSettings());
        ModSettingsService service = new ModSettingsService(repository);
        IReadOnlyList<ModDefinition> mods =
        [
            new ModDefinition { ProjectId = "200", Name = "two", Enabled = false, Order = 1 },
            new ModDefinition { ProjectId = "100", Name = "one", Enabled = true, Order = 0 }
        ];

        OperationResult<IReadOnlyList<ModDefinition>> result = await service.SaveAsync(mods, CancellationToken.None);

        Assert.True(result.Succeeded);
        Assert.Equal(new[] { "100", "200" }, result.Value?.Select(mod => mod.ProjectId));
        Assert.NotNull(result.Value);
        Assert.False(result.Value[1].Enabled);
    }
}

public sealed class GameSettingsSessionTests
{
    [Fact]
    public void Grouping_AssignsEveryDefinitionToExactlyOneOfEightCategories()
    {
        GameSettingsWorkspace workspace = CreateWorkspace();
        GameSettingsSession session = new GameSettingsSession(workspace);

        Assert.Equal(8, session.Categories.Count);
        int total = session.Categories.Sum(category =>
        {
            session.SelectCategory(category);
            return session.GetVisibleItems().Count;
        });
        Assert.Equal(workspace.Definitions.Count, total);
    }

    [Fact]
    public void Categories_UseDailyOperationDisplayOrder()
    {
        GameSettingsSession session = new GameSettingsSession(CreateWorkspace());
        string[] expectedCategories =
        [
            "基本・ゲーム進行",
            "プレイヤー",
            "恐竜・生物",
            "採取・テイム",
            "繁殖",
            "建築・戦闘",
            "アイテム・転送",
            "管理・高度"
        ];

        Assert.Equal(expectedCategories, session.Categories);
    }

    [Theory]
    [InlineData(SupportStatus.AsaSupported, "ASA対応")]
    [InlineData(SupportStatus.AsaSupportedConditional, "条件付き")]
    [InlineData(SupportStatus.AsaMapSpecific, "MAP固有")]
    [InlineData(SupportStatus.Unverified, "未検証")]
    [InlineData(SupportStatus.Deprecated, "非推奨")]
    [InlineData(SupportStatus.AseOnly, "ASE専用")]
    [InlineData(SupportStatus.Unknown, "状態不明")]
    public void SupportStatus_UsesJapaneseUserFacingLabel(SupportStatus status, string expected)
    {
        Assert.Equal(expected, GameSettingEditorItem.GetSupportStatusLabel(status));
    }

    [Fact]
    public void DetailText_UsesJapaneseLabelsAndKeepsUnverifiedWarning()
    {
        GameSettingDefinition definition = CreateDefinition("id", "管理・高度", "UnknownSetting", GameSettingValueType.String);
        definition = new GameSettingDefinition
        {
            Id = definition.Id,
            DisplayNameJa = definition.DisplayNameJa,
            DisplayNameEn = definition.DisplayNameEn,
            Category = definition.Category,
            UiCategory = definition.UiCategory,
            UiSubCategory = definition.UiSubCategory,
            DescriptionJa = definition.DescriptionJa,
            FileKind = definition.FileKind,
            Section = definition.Section,
            Key = definition.Key,
            ValueType = definition.ValueType,
            DefaultValue = definition.DefaultValue,
            EnumValues = definition.EnumValues,
            SupportStatus = SupportStatus.Unverified,
            Deprecated = false,
            RestartRequired = true,
            Sources = definition.Sources,
            Notes = "未検証"
        };

        string text = GameSettingDetailTextFormatter.Format(definition, new GameSettingState { DefinitionId = "id", EditedValue = "value" });

        Assert.Contains("対応状況: 未検証", text);
        Assert.Contains("再起動: 必要", text);
        Assert.Contains("INIファイル: Game.ini", text);
        Assert.Contains("セクション: Section", text);
        Assert.Contains("INIキー: UnknownSetting", text);
        Assert.Contains("英語名:", text);
        Assert.Contains("備考: 未検証", text);
        Assert.Contains("この設定は未検証です", text);
        Assert.DoesNotContain("Support Status", text);
        Assert.DoesNotContain("Restart Required", text);
    }

    [Fact]
    public void CategoryAndSearch_KeepStateAndRestorePreviousCategory()
    {
        GameSettingsSession session = new GameSettingsSession(CreateWorkspace());
        session.SelectCategory("繁殖");
        GameSettingEditorItem selected = Assert.Single(session.GetVisibleItems());
        selected.Value = "changed";
        selected.Enabled = true;

        session.SetSearch("WildDino");
        GameSettingEditorItem searchHit = Assert.Single(session.GetVisibleItems());
        Assert.Equal("恐竜・生物", searchHit.Category);
        session.SetSearch(string.Empty);

        Assert.Equal("繁殖", session.SelectedCategory);
        GameSettingEditorItem restored = Assert.Single(session.GetVisibleItems());
        Assert.Equal("changed", restored.Value);
        Assert.True(restored.Enabled);
    }

    [Theory]
    [InlineData("野生恐竜")]
    [InlineData("WildDino")]
    [InlineData("food drain")]
    [InlineData("恐竜・生物")]
    public void Search_CoversJapaneseEnglishDescriptionKeyAndCategory(string query)
    {
        GameSettingsSession session = new GameSettingsSession(CreateWorkspace());
        session.SetSearch(query);
        Assert.Contains(session.GetVisibleItems(), item => item.Definition.Key == "WildDinoCharacterFoodDrainMultiplier");
    }

    [Fact]
    public void ToggleAndReset_AffectOnlyCategoryAndResetDoesNotChangeEnabled()
    {
        GameSettingsSession session = new GameSettingsSession(CreateWorkspace());
        session.SelectCategory("繁殖");
        Assert.True(session.ToggleCurrentCategory().Succeeded);
        GameSettingEditorItem item = Assert.Single(session.GetVisibleItems());
        Assert.True(item.Enabled);
        item.Value = "9";

        Assert.True(session.ResetCurrentCategoryDefaults().Succeeded);
        Assert.Equal("1", item.Value);
        Assert.True(item.Enabled);
    }

    [Fact]
    public void SearchMode_DisablesCategoryBulkOperations()
    {
        GameSettingsSession session = new GameSettingsSession(CreateWorkspace());
        session.SetSearch("恐竜");
        Assert.False(session.ToggleCurrentCategory().Succeeded);
        Assert.False(session.ResetCurrentCategoryDefaults().Succeeded);
    }

    [Fact]
    public void ValueValidator_ValidatesIntegerDecimalBooleanAndComplex()
    {
        GameSettingState state = new GameSettingState { DefinitionId = "x", Enabled = true, EditedValue = "bad" };
        Assert.False(GameSettingValueValidator.Validate(CreateDefinition("x", "プレイヤー", "IntegerValue", GameSettingValueType.Integer), state).Succeeded);
        Assert.False(GameSettingValueValidator.Validate(CreateDefinition("x", "プレイヤー", "DecimalValue", GameSettingValueType.Decimal), state).Succeeded);
        Assert.False(GameSettingValueValidator.Validate(CreateDefinition("x", "プレイヤー", "BooleanValue", GameSettingValueType.Boolean), state).Succeeded);
        state.EditedValue = string.Empty;
        Assert.False(GameSettingValueValidator.Validate(CreateDefinition("x", "プレイヤー", "ComplexValue", GameSettingValueType.Complex), state).Succeeded);
    }

    private static GameSettingsWorkspace CreateWorkspace()
    {
        string[] categories = ["基本・ゲーム進行", "プレイヤー", "恐竜・生物", "採取・テイム", "繁殖", "建築・戦闘", "アイテム・転送", "管理・高度"];
        List<GameSettingDefinition> definitions = [];
        List<GameSettingState> states = [];
        for (int index = 0; index < categories.Length; index++)
        {
            string key = "Key" + index;
            if (categories[index] == "恐竜・生物") key = "WildDinoCharacterFoodDrainMultiplier";
            GameSettingDefinition definition = CreateDefinition("id-" + index, categories[index], key, GameSettingValueType.Decimal);
            definitions.Add(definition);
            states.Add(new GameSettingState { DefinitionId = definition.Id, Enabled = false, EditedValue = definition.DefaultValue });
        }
        return new GameSettingsWorkspace(definitions, states);
    }

    private static GameSettingDefinition CreateDefinition(string id, string category, string key, GameSettingValueType valueType)
    {
        string displayNameJa = category + "設定";
        string descriptionJa = "説明";
        if (key == "WildDinoCharacterFoodDrainMultiplier")
        {
            displayNameJa = "野生恐竜の食料消費倍率";
            descriptionJa = "food drainの設定";
        }

        return new GameSettingDefinition
        {
            Id = id,
            DisplayNameJa = displayNameJa,
            DisplayNameEn = key,
            Category = category,
            UiCategory = category,
            UiSubCategory = category,
            DescriptionJa = descriptionJa,
            FileKind = IniFileKind.Game,
            Section = "Section",
            Key = key,
            ValueType = valueType,
            DefaultValue = "1",
            EnumValues = [],
            SupportStatus = SupportStatus.AsaSupported,
            Deprecated = false,
            RestartRequired = true,
            Sources = [],
            Notes = string.Empty
        };
    }
}

public sealed class ManualBackupCoordinatorTests
{
    [Fact]
    public async Task Stopped_CreatesDirectBackupWithoutSaveWorld()
    {
        RuntimeFakes fakes = new RuntimeFakes();
        fakes.Process.IsRunning = false;
        UiBackupService backup = new UiBackupService();
        await using ServerOrchestrator orchestrator = fakes.CreateOrchestrator();
        await using ManualBackupCoordinator coordinator = new ManualBackupCoordinator(orchestrator, fakes.Settings, fakes.Secrets, fakes.Rcon, backup, new FakeDelay());

        OperationResult<ManualBackupResult> result = await coordinator.CreateAsync(null, CancellationToken.None);

        Assert.True(result.Succeeded, result.ErrorMessage);
        Assert.False(result.Value?.IsLiveBackup);
        Assert.Empty(fakes.Rcon.Commands);
        Assert.Equal(1, backup.Calls);
    }

    [Fact]
    public async Task Running_SaveWorldThenDelayThenBackupAndReturnsWarning()
    {
        RuntimeFakes fakes = new RuntimeFakes();
        fakes.Process.IsRunning = true;
        UiBackupService backup = new UiBackupService();
        UiRecordingDelay delay = new UiRecordingDelay();
        await using ServerOrchestrator orchestrator = fakes.CreateOrchestrator();
        await using ManualBackupCoordinator coordinator = new ManualBackupCoordinator(orchestrator, fakes.Settings, fakes.Secrets, fakes.Rcon, backup, delay);

        OperationResult<ManualBackupResult> result = await coordinator.CreateAsync(null, CancellationToken.None);

        Assert.True(result.Succeeded, result.ErrorMessage);
        Assert.Equal(new[] { "SaveWorld" }, fakes.Rcon.Commands);
        Assert.Equal(TimeSpan.FromSeconds(15), Assert.Single(delay.Delays));
        Assert.Equal(1, backup.Calls);
        Assert.True(result.Value?.IsLiveBackup);
        Assert.NotEmpty(result.Warnings);
    }

    [Fact]
    public async Task Running_SaveWorldFailureDoesNotBackup()
    {
        RuntimeFakes fakes = new RuntimeFakes();
        fakes.Process.IsRunning = true;
        fakes.Rcon.CommandResults.Enqueue(RconConnectionResult.Failure("SAVEWORLD_FAILED", "failed"));
        UiBackupService backup = new UiBackupService();
        await using ServerOrchestrator orchestrator = fakes.CreateOrchestrator();
        await using ManualBackupCoordinator coordinator = new ManualBackupCoordinator(orchestrator, fakes.Settings, fakes.Secrets, fakes.Rcon, backup, new FakeDelay());

        OperationResult<ManualBackupResult> result = await coordinator.CreateAsync(null, CancellationToken.None);

        Assert.False(result.Succeeded);
        Assert.Equal("SAVEWORLD_FAILED", result.ErrorCode);
        Assert.Equal(0, backup.Calls);
    }

    [Fact]
    public async Task WaitingForRcon_RejectsBackupWithoutSaveWorldOrCopy()
    {
        RuntimeFakes fakes = new RuntimeFakes();
        fakes.Process.IsRunning = true;
        fakes.Rcon.TestResult = RconConnectionResult.Failure("RCON_NOT_READY", "not ready");
        UiBackupService backup = new UiBackupService();
        await using ServerOrchestrator orchestrator = fakes.CreateOrchestrator();
        await using ManualBackupCoordinator coordinator = new ManualBackupCoordinator(orchestrator, fakes.Settings, fakes.Secrets, fakes.Rcon, backup, new FakeDelay());

        OperationResult<ManualBackupResult> result = await coordinator.CreateAsync(null, CancellationToken.None);

        Assert.False(result.Succeeded);
        Assert.Equal("BACKUP_STATE_INVALID", result.ErrorCode);
        Assert.Empty(fakes.Rcon.Commands);
        Assert.Equal(0, backup.Calls);
    }
}

public sealed class UiInfrastructureServiceTests
{
    [Fact]
    public async Task FileLogService_ReadsOnlyBoundedTail()
    {
        using TestDirectory directory = new TestDirectory();
        string path = Path.Combine(directory.Path, "20260903.log");
        await File.WriteAllLinesAsync(path, Enumerable.Range(1, 2000).Select(index => "line-" + index));

        OperationResult<LogTailSnapshot> result = await new FileLogService(directory.Path).ReadTailAsync(100, CancellationToken.None);

        Assert.True(result.Succeeded);
        Assert.Equal(100, result.Value?.Lines.Count);
        Assert.Equal("line-1901", result.Value?.Lines[0]);
        Assert.Equal("line-2000", result.Value?.Lines[99]);
    }

    [Fact]
    public async Task JsonMapRepository_LoadsExternalDefinitions()
    {
        string path = Path.Combine(AppContext.BaseDirectory, "definitions", "maps.json");
        OperationResult<IReadOnlyList<MapDefinition>> result = await new JsonMapDefinitionRepository(path).LoadAsync(CancellationToken.None);
        Assert.True(result.Succeeded, result.ErrorMessage);
        Assert.Equal(10, result.Value?.Count);
        Assert.Equal(result.Value?.Count, result.Value?.Select(map => map.LevelName).Distinct(StringComparer.OrdinalIgnoreCase).Count());
    }

    [Fact]
    public void DiagnosticsSnapshot_HasNoSecretOrPasswordProperty()
    {
        string[] names = typeof(DiagnosticsSnapshot).GetProperties().Select(property => property.Name).ToArray();
        Assert.DoesNotContain(names, name => name.Contains("Password", StringComparison.OrdinalIgnoreCase) || name.Contains("Secret", StringComparison.OrdinalIgnoreCase));
    }
}

internal sealed class UiSettingsRepository : IServerSettingsRepository
{
    internal UiSettingsRepository(ServerSettings settings) { Settings = settings; }
    internal ServerSettings Settings { get; private set; }
    public Task<OperationResult<ServerSettings>> LoadAsync(CancellationToken cancellationToken) => Task.FromResult(OperationResult<ServerSettings>.Success(Settings));
    public Task<OperationResult> SaveAsync(ServerSettings settings, CancellationToken cancellationToken) { Settings = settings; return Task.FromResult(OperationResult.Success()); }
}

internal sealed class UiSecretRepository : ISecretRepository
{
    internal UiSecretRepository(ServerSecrets secrets) { Secrets = secrets; }
    internal ServerSecrets Secrets { get; private set; }
    public Task<OperationResult<ServerSecrets>> LoadAsync(CancellationToken cancellationToken) => Task.FromResult(OperationResult<ServerSecrets>.Success(Secrets));
    public Task<OperationResult> SaveAsync(ServerSecrets secrets, CancellationToken cancellationToken) { Secrets = secrets; return Task.FromResult(OperationResult.Success()); }
}

internal sealed class UiMapRepository : IMapDefinitionRepository
{
    internal IReadOnlyList<MapDefinition> Maps { get; } = [new MapDefinition { Id = "the-island", LevelName = "TheIsland_WP", DisplayNameJa = "The Island" }];
    public Task<OperationResult<IReadOnlyList<MapDefinition>>> LoadAsync(CancellationToken cancellationToken) => Task.FromResult(OperationResult<IReadOnlyList<MapDefinition>>.Success(Maps));
}

internal sealed class UiBackupService : IBackupService
{
    internal int Calls { get; private set; }
    public Task<OperationResult<BackupInfo>> CreateSavedBackupAsync(string serverRoot, CancellationToken cancellationToken)
    {
        Calls++;
        BackupInfo value = new BackupInfo { Path = "C:\\Backup", CreatedAt = DateTimeOffset.UtcNow, FileCount = 10, TotalBytes = 100 };
        return Task.FromResult(OperationResult<BackupInfo>.Success(value));
    }
}

internal sealed class UiRecordingDelay : IOperationDelay
{
    internal List<TimeSpan> Delays { get; } = [];
    public Task DelayAsync(TimeSpan delay, CancellationToken cancellationToken) { Delays.Add(delay); return Task.CompletedTask; }
}
