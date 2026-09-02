using System.ComponentModel;
using ASA.ServerManager.Application;
using ASA.ServerManager.Domain;
using ASA.ServerManager.Infrastructure;

namespace ASA.ServerManager.WinForms;

/// <summary>JSONカタログからゲーム設定を表示・編集する最小UIです。</summary>
public sealed class GameSettingsView : UserControl
{
    private readonly TextBox _searchBox = new TextBox();
    private readonly Label _statusLabel = new Label();
    private readonly DataGridView _grid = new DataGridView();
    private List<SettingRow> _allRows = [];

    /// <summary>ゲーム設定画面を構築し、カタログ読込を開始します。</summary>
    public GameSettingsView()
    {
        BuildLayout();
        Load += OnLoad;
    }

    private void BuildLayout()
    {
        _searchBox.Dock = DockStyle.Top;
        _searchBox.PlaceholderText = "検索";
        _searchBox.TextChanged += OnSearchTextChanged;

        _statusLabel.Dock = DockStyle.Top;
        _statusLabel.Height = 26;
        _statusLabel.Padding = new Padding(6, 4, 0, 0);
        _statusLabel.Text = "カタログを読み込んでいます。";

        _grid.Dock = DockStyle.Fill;
        _grid.AutoGenerateColumns = false;
        _grid.AllowUserToAddRows = false;
        _grid.RowHeadersVisible = false;
        AddColumns();

        Controls.Add(_grid);
        Controls.Add(_statusLabel);
        Controls.Add(_searchBox);
    }

    private void AddColumns()
    {
        _grid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = nameof(SettingRow.Category), HeaderText = "Category", ReadOnly = true, Width = 130 });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = nameof(SettingRow.Name), HeaderText = "Setting名", ReadOnly = true, Width = 260 });
        _grid.Columns.Add(new DataGridViewCheckBoxColumn { DataPropertyName = nameof(SettingRow.Enabled), HeaderText = "Enabled", Width = 65 });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = nameof(SettingRow.Value), HeaderText = "Value", Width = 180 });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = nameof(SettingRow.CurrentIniValue), HeaderText = "CurrentIniValue", ReadOnly = true, Width = 160 });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = nameof(SettingRow.DefaultValue), HeaderText = "DefaultValue", ReadOnly = true, Width = 140 });
    }

    private async void OnLoad(object? sender, EventArgs eventArgs)
    {
        string catalogPath = Path.Combine(AppContext.BaseDirectory, "definitions", "game-settings.json");
        JsonGameSettingCatalogRepository repository = new JsonGameSettingCatalogRepository(catalogPath);
        OperationResult<IReadOnlyList<GameSettingDefinition>> result = await repository.LoadAsync(CancellationToken.None);
        if (!result.Succeeded || result.Value is null)
        {
            _statusLabel.Text = $"カタログ読込失敗: {result.ErrorMessage}";
            return;
        }
        _allRows = result.Value.Select(definition => new SettingRow(definition)).ToList();
        _statusLabel.Text = $"{_allRows.Count} 件の設定を読み込みました。";
        BindRows(_allRows);
    }

    private void OnSearchTextChanged(object? sender, EventArgs eventArgs)
    {
        string query = _searchBox.Text.Trim();
        if (query.Length == 0)
        {
            BindRows(_allRows);
            return;
        }
        List<SettingRow> filtered = _allRows.Where(row => row.Category.Contains(query, StringComparison.OrdinalIgnoreCase) || row.Name.Contains(query, StringComparison.OrdinalIgnoreCase)).ToList();
        BindRows(filtered);
    }

    private void BindRows(IEnumerable<SettingRow> rows)
    {
        _grid.DataSource = new BindingList<SettingRow>(rows.ToList());
    }

    /// <summary>INI取込後の編集状態を画面の表示行へ反映します。</summary>
    public void UpdateFromImportedStates(IEnumerable<GameSettingState> states)
    {
        Dictionary<string, GameSettingState> stateById = states.ToDictionary(state => state.DefinitionId, StringComparer.Ordinal);
        foreach (SettingRow row in _allRows)
        {
            if (stateById.TryGetValue(row.DefinitionId, out GameSettingState? state))
            {
                row.Enabled = state.Enabled;
                row.Value = state.EditedValue;
                row.CurrentIniValue = state.CurrentIniValue;
            }
        }
        BindRows(_allRows);
    }

    private sealed class SettingRow(GameSettingDefinition definition)
    {
        public string DefinitionId { get; } = definition.Id;
        public string Category { get; } = definition.Category;
        public string Name { get; } = definition.DisplayNameJa;
        public bool Enabled { get; set; }
        public string? Value { get; set; }
        public string? CurrentIniValue { get; set; }
        public string? DefaultValue { get; } = definition.DefaultValue;
    }
}
