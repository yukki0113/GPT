using ASA.ServerManager.Domain;
using ASA.ServerManager.Infrastructure;

namespace ASA.ServerManager.Tests;

public sealed class CatalogRepositoryTests
{
    [Fact]
    public async Task LoadAsync_LoadsTheAuditedCatalogWithoutDroppingConditionalOrNullDefaultValues()
    {
        string path = Path.Combine(AppContext.BaseDirectory, "definitions", "game-settings.json");
        JsonGameSettingCatalogRepository repository = new JsonGameSettingCatalogRepository(path);

        OperationResult<IReadOnlyList<GameSettingDefinition>> result = await repository.LoadAsync(CancellationToken.None);

        Assert.True(result.Succeeded, result.ErrorMessage);
        IReadOnlyList<GameSettingDefinition> definitions = Assert.IsAssignableFrom<IReadOnlyList<GameSettingDefinition>>(result.Value);
        Assert.Equal(335, definitions.Count);
        Assert.Equal(256, definitions.Count(definition => definition.FileKind == IniFileKind.GameUserSettings));
        Assert.Equal(79, definitions.Count(definition => definition.FileKind == IniFileKind.Game));
        Assert.Equal(11, definitions.Count(definition => definition.ValueType == GameSettingValueType.Complex));
        Assert.Contains(definitions, definition => definition.SupportStatus == SupportStatus.AsaSupportedConditional);
        Assert.Contains(definitions, definition => definition.DefaultValue is null);
        Assert.Equal(definitions.Count, definitions.Select(definition => definition.Id).Distinct(StringComparer.OrdinalIgnoreCase).Count());
        Assert.Equal(definitions.Count, definitions.Select(definition => definition.GetIdentity().ToLookupKey()).Distinct(StringComparer.Ordinal).Count());
    }
}
