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
        Assert.All(definitions, definition => Assert.False(string.IsNullOrWhiteSpace(definition.UiCategory)));
        Assert.All(definitions, definition => Assert.False(string.IsNullOrWhiteSpace(definition.UiSubCategory)));
        Assert.All(definitions, definition => Assert.False(string.IsNullOrWhiteSpace(definition.DisplayNameJa)));
        Assert.All(definitions, definition => Assert.False(string.IsNullOrWhiteSpace(definition.DescriptionJa)));
        Assert.DoesNotContain(definitions, definition => string.Equals(definition.DisplayNameJa, definition.Key, StringComparison.Ordinal));
        Assert.DoesNotContain(definitions, definition => definition.DisplayNameJa.Contains("に関する設定（", StringComparison.Ordinal));
        Dictionary<string, int> expectedCategoryCounts = new Dictionary<string, int>(StringComparer.Ordinal)
        {
            ["基本・ゲーム進行"] = 86,
            ["プレイヤー"] = 16,
            ["恐竜・生物"] = 49,
            ["採取・テイム"] = 11,
            ["繁殖"] = 29,
            ["建築・戦闘"] = 65,
            ["アイテム・転送"] = 20,
            ["管理・高度"] = 59
        };
        Dictionary<string, int> actualCategoryCounts = definitions
            .GroupBy(definition => definition.UiCategory, StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.Count(), StringComparer.Ordinal);
        Assert.Equal(expectedCategoryCounts.Count, actualCategoryCounts.Count);
        foreach (KeyValuePair<string, int> expected in expectedCategoryCounts)
        {
            Assert.True(actualCategoryCounts.TryGetValue(expected.Key, out int actualCount));
            Assert.Equal(expected.Value, actualCount);
        }
        Assert.Equal(definitions.Count, definitions.GroupBy(definition => definition.UiCategory, StringComparer.Ordinal).Sum(group => group.Count()));
    }
}
