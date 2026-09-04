using System.Text;
using ASA.ServerManager.Application;
using ASA.ServerManager.Domain;
using ASA.ServerManager.Infrastructure;

namespace ASA.ServerManager.Tests;

public sealed class IniDocumentTests
{
    [Fact]
    public async Task LoadAndSaveAsync_PreservesCommentsBlankLinesUnknownContentAndKeyCasing()
    {
        using TestDirectory directory = new TestDirectory();
        string path = Path.Combine(directory.Path, "Game.ini");
        string original = "; comment\r\n\r\n[ServerSettings]\r\nKnownKey=old\r\nUnknownKey=value\r\nraw text\r\n[Other]\r\nKnownKey=other\r\n";
        await File.WriteAllTextAsync(path, original);
        IniDocumentService service = new IniDocumentService();

        OperationResult<IniDocument> load = await service.LoadAsync(path, IniFileKind.Game, CancellationToken.None);

        Assert.True(load.Succeeded, load.ErrorMessage);
        IniDocument document = Assert.IsType<IniDocument>(load.Value);
        Assert.Single(document.FindKeys("ServerSettings", "KnownKey"));
        Assert.Single(document.FindKeys("Other", "KnownKey"));
        document.SetValue("serversettings", "knownkey", "new");
        document.SetValue("ServerSettings", "AddedKey", "added");
        OperationResult save = await service.SaveAsync(path, document, CancellationToken.None);
        Assert.True(save.Succeeded, save.ErrorMessage);

        string saved = await File.ReadAllTextAsync(path);
        Assert.Contains("; comment\r\n\r\n", saved);
        Assert.Contains("KnownKey=new", saved);
        Assert.Contains("UnknownKey=value", saved);
        Assert.Contains("raw text", saved);
        Assert.Contains("[Other]\r\nKnownKey=other", saved);
        Assert.Contains("AddedKey=added", saved);
    }

    [Fact]
    public async Task Import_DoesNotEnableAmbiguousKeysAndLeavesMissingDisabled()
    {
        using TestDirectory directory = new TestDirectory();
        string path = Path.Combine(directory.Path, "Game.ini");
        await File.WriteAllTextAsync(path, "[Section]\nKey=one\nKey=two\n");
        IniDocumentService service = new IniDocumentService();
        OperationResult<IniDocument> load = await service.LoadAsync(path, IniFileKind.Game, CancellationToken.None);
        IniDocument document = Assert.IsType<IniDocument>(load.Value);
        GameSettingDefinition existing = CreateDefinition("existing", "Section", "Key");
        GameSettingDefinition missing = CreateDefinition("missing", "Section", "Missing");
        List<GameSettingState> states = [new GameSettingState { DefinitionId = "existing" }, new GameSettingState { DefinitionId = "missing" }];

        OperationResult result = new ConfigurationOrchestrator().Import([existing, missing], [document], states);

        Assert.True(result.Succeeded);
        Assert.Single(result.Warnings);
        Assert.False(states[0].Enabled);
        Assert.False(states[1].Enabled);
    }

    [Fact]
    public void Apply_UpdatesOrAddsOnlyEnabledSettings()
    {
        IniDocument document = new IniDocument(IniFileKind.Game, [new IniSectionNode("Section"), new IniKeyValueNode("Section", "Existing", "old"), new IniKeyValueNode("Section", "Disabled", "keep")], "\n", false);
        GameSettingDefinition existing = CreateDefinition("existing", "Section", "Existing");
        GameSettingDefinition missing = CreateDefinition("missing", "Section", "Added");
        GameSettingDefinition disabled = CreateDefinition("disabled", "Section", "Disabled");
        List<GameSettingState> states = [new GameSettingState { DefinitionId = "existing", Enabled = true, EditedValue = "new" }, new GameSettingState { DefinitionId = "missing", Enabled = true, EditedValue = "added" }, new GameSettingState { DefinitionId = "disabled", Enabled = false, EditedValue = "changed" }];

        OperationResult result = new ConfigurationOrchestrator().Apply([existing, missing, disabled], [document], states);

        Assert.True(result.Succeeded, result.ErrorMessage);
        Assert.Equal("new", Assert.Single(document.FindKeys("Section", "Existing")).Value);
        Assert.Equal("added", Assert.Single(document.FindKeys("Section", "Added")).Value);
        Assert.Equal("keep", Assert.Single(document.FindKeys("Section", "Disabled")).Value);
    }

    [Fact]
    public async Task Utf8WithoutBomJapaneseCrLfRoundTrip_PreservesUnmanagedContentAtByteLevel()
    {
        using TestDirectory directory = new TestDirectory();
        string path = Path.Combine(directory.Path, "Game.ini");
        string original = "; この行は削除しない\r\n# 日本語コメント2\r\n\r\n[/script/shootergame.shootergamemode]\r\nServerCrosshair=True\r\nUnknownSetting=日本語の値\r\nraw 日本語 line\r\n\r\n[CustomSection]\r\nMessage=日本語\r\n";
        byte[] originalBytes = new UTF8Encoding(false).GetBytes(original);
        await File.WriteAllBytesAsync(path, originalBytes);
        IniDocumentService service = new IniDocumentService();

        OperationResult<IniDocument> load = await service.LoadAsync(path, IniFileKind.Game, CancellationToken.None);

        Assert.True(load.Succeeded, load.ErrorMessage);
        IniDocument document = Assert.IsType<IniDocument>(load.Value);
        Assert.False(document.HasUtf8Bom);
        Assert.Equal("\r\n", document.NewLine);
        document.SetValue("/script/shootergame.shootergamemode", "ServerCrosshair", "False");
        OperationResult save = await service.SaveAsync(path, document, CancellationToken.None);
        Assert.True(save.Succeeded, save.ErrorMessage);

        string expected = original.Replace("ServerCrosshair=True", "ServerCrosshair=False", StringComparison.Ordinal);
        byte[] savedBytes = await File.ReadAllBytesAsync(path);
        Assert.Equal(new UTF8Encoding(false).GetBytes(expected), savedBytes);
        Assert.False(savedBytes.AsSpan().StartsWith(Encoding.UTF8.GetPreamble()));
        Assert.DoesNotContain("\n", expected.Replace("\r\n", string.Empty, StringComparison.Ordinal));

        OperationResult<IniDocument> reload = await service.LoadAsync(path, IniFileKind.Game, CancellationToken.None);
        Assert.True(reload.Succeeded, reload.ErrorMessage);
        Assert.Equal("日本語の値", Assert.Single(reload.Value?.FindKeys("/script/shootergame.shootergamemode", "UnknownSetting") ?? []).Value);
        Assert.Equal("日本語", Assert.Single(reload.Value?.FindKeys("CustomSection", "Message") ?? []).Value);
    }

    [Fact]
    public async Task Utf8WithBomJapaneseLfRoundTrip_PreservesBomNewlinesAndComments()
    {
        using TestDirectory directory = new TestDirectory();
        string path = Path.Combine(directory.Path, "GameUserSettings.ini");
        string original = "; 日本語コメント\n[ServerSettings]\nServerCrosshair=True\nCustomText=恐竜テスト\n";
        byte[] preamble = Encoding.UTF8.GetPreamble();
        byte[] content = new UTF8Encoding(false).GetBytes(original);
        byte[] originalBytes = preamble.Concat(content).ToArray();
        await File.WriteAllBytesAsync(path, originalBytes);
        IniDocumentService service = new IniDocumentService();

        OperationResult<IniDocument> load = await service.LoadAsync(path, IniFileKind.GameUserSettings, CancellationToken.None);

        Assert.True(load.Succeeded, load.ErrorMessage);
        IniDocument document = Assert.IsType<IniDocument>(load.Value);
        Assert.True(document.HasUtf8Bom);
        Assert.Equal("\n", document.NewLine);
        document.SetValue("ServerSettings", "ServerCrosshair", "False");
        OperationResult save = await service.SaveAsync(path, document, CancellationToken.None);
        Assert.True(save.Succeeded, save.ErrorMessage);

        byte[] savedBytes = await File.ReadAllBytesAsync(path);
        Assert.True(savedBytes.AsSpan().StartsWith(preamble));
        string decoded = new UTF8Encoding(true, true).GetString(savedBytes.AsSpan(preamble.Length));
        Assert.DoesNotContain("\r\n", decoded);
        Assert.Contains("; 日本語コメント\n", decoded);
        Assert.Contains("CustomText=恐竜テスト\n", decoded);
        Assert.Contains("ServerCrosshair=False\n", decoded);
        OperationResult<IniDocument> reload = await service.LoadAsync(path, IniFileKind.GameUserSettings, CancellationToken.None);
        Assert.True(reload.Succeeded, reload.ErrorMessage);
    }

    [Fact]
    public async Task Cp932Japanese_SaveWorkflowRejectsInputBeforeBackupAndPreservesOriginalBytes()
    {
        Encoding.RegisterProvider(CodePagesEncodingProvider.Instance);
        using TestDirectory directory = new TestDirectory();
        string gameUserSettingsPath = Path.Combine(directory.Path, "GameUserSettings.ini");
        string gameIniPath = Path.Combine(directory.Path, "Game.ini");
        byte[] originalBytes = Encoding.GetEncoding(932).GetBytes("; 日本語コメント\r\n[ServerSettings]\r\nMessage=恐竜テスト\r\n");
        await File.WriteAllBytesAsync(gameUserSettingsPath, originalBytes);
        await File.WriteAllBytesAsync(gameIniPath, new UTF8Encoding(false).GetBytes("[Section]\nKey=Value\n"));
        RecordingIniBackupService backup = new RecordingIniBackupService();
        IniConfigurationSaveService service = new IniConfigurationSaveService(new IniDocumentService(), backup);

        OperationResult result = await service.SaveAsync([], [], gameUserSettingsPath, gameIniPath, CancellationToken.None);

        Assert.False(result.Succeeded);
        Assert.Equal("INI_UNSUPPORTED_ENCODING", result.ErrorCode);
        string userMessage = result.UserMessage ?? string.Empty;
        string technicalMessage = result.TechnicalMessage ?? string.Empty;
        Assert.Contains("INIファイルをUTF-8として読み込めませんでした。", userMessage);
        Assert.Contains("安全のためファイルは変更していません。", userMessage);
        Assert.DoesNotContain("DecoderFallbackException", userMessage);
        Assert.Contains("DecoderFallbackException", technicalMessage);
        Assert.Equal(0, backup.Calls);
        Assert.Equal(originalBytes, await File.ReadAllBytesAsync(gameUserSettingsPath));
    }

    [Fact]
    public async Task InvalidUtf8_LoadRejectsInputAndPreservesOriginalBytes()
    {
        using TestDirectory directory = new TestDirectory();
        string path = Path.Combine(directory.Path, "Game.ini");
        byte[] originalBytes = [0x5B, 0x53, 0x5D, 0x0A, 0x4B, 0x3D, 0xC3, 0x28, 0x0A];
        await File.WriteAllBytesAsync(path, originalBytes);
        IniDocumentService service = new IniDocumentService();

        OperationResult<IniDocument> result = await service.LoadAsync(path, IniFileKind.Game, CancellationToken.None);

        Assert.False(result.Succeeded);
        Assert.Equal("INI_UNSUPPORTED_ENCODING", result.ErrorCode);
        string userMessage = result.UserMessage ?? string.Empty;
        Assert.Contains("文字コードを確認してください。", userMessage);
        Assert.DoesNotContain("Unable to translate", userMessage);
        Assert.NotNull(result.TechnicalMessage);
        Assert.Equal(originalBytes, await File.ReadAllBytesAsync(path));
    }

    private static GameSettingDefinition CreateDefinition(string id, string section, string key)
    {
        return new GameSettingDefinition { Id = id, DisplayNameJa = id, DisplayNameEn = id, Category = "Test", UiCategory = "テスト", UiSubCategory = string.Empty, DescriptionJa = "テスト設定", FileKind = IniFileKind.Game, Section = section, Key = key, ValueType = GameSettingValueType.String, EnumValues = [], SupportStatus = SupportStatus.AsaSupported, Deprecated = false, RestartRequired = false, Sources = [], Notes = string.Empty };
    }

    private sealed class RecordingIniBackupService : IIniBackupService
    {
        internal int Calls { get; private set; }

        public Task<OperationResult<string>> BackupIniAsync(IEnumerable<string> sourcePaths, CancellationToken cancellationToken)
        {
            Calls++;
            return Task.FromResult(OperationResult<string>.Success("backup"));
        }
    }
}
