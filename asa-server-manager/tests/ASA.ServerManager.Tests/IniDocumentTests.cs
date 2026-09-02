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

    private static GameSettingDefinition CreateDefinition(string id, string section, string key)
    {
        return new GameSettingDefinition { Id = id, DisplayNameJa = id, DisplayNameEn = id, Category = "Test", FileKind = IniFileKind.Game, Section = section, Key = key, ValueType = GameSettingValueType.String, SupportStatus = SupportStatus.AsaSupported, Sources = [], Notes = string.Empty };
    }
}
