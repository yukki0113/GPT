using System.ComponentModel;
using System.Text;
using ASA.ServerManager.Application;
using ASA.ServerManager.Domain;

namespace ASA.ServerManager.WinForms;

/// <summary>335件の設定をカテゴリ、横断検索、詳細Pane付きで編集します。</summary>
public sealed class GameSettingsView : UserControl
{
    private readonly GameSettingsService _service;
    private readonly IApplicationStatusStore _statusStore;
    private readonly Button _importButton = new Button();
    private readonly Button _saveButton = new Button();
    private readonly Button _selectButton = new Button();
    private readonly Button _resetButton = new Button();
    private readonly TextBox _searchBox = new TextBox();
    private readonly TabControl _categories = new TabControl();
    private readonly DataGridView _grid = new DataGridView();
    private readonly TextBox _details = new TextBox();
    private readonly Label _status = new Label();
    private GameSettingsWorkspace? _workspace;
    private GameSettingsSession? _session;
    private bool _bindingCategories;

    /// <summary>カタログとINI Coreを束ねたApplication serviceを受け取ります。</summary>
    public GameSettingsView(GameSettingsService service, IApplicationStatusStore statusStore)
    {
        _service = service;
        _statusStore = statusStore;
        AutoScaleMode = AutoScaleMode.Dpi;
        BuildLayout();
        Load += GameSettingsView_Load;
    }

    private void BuildLayout()
    {
        TableLayoutPanel root = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 4, Padding = new Padding(8) };
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));

        FlowLayoutPanel toolbar = new FlowLayoutPanel { AutoSize = true, Dock = DockStyle.Fill, WrapContents = true };
        ConfigureButton(_importButton, "INIから読み込み", ImportButton_Click);
        ConfigureButton(_saveButton, "INIへ保存", SaveButton_Click);
        ConfigureButton(_selectButton, "全選択／全解除", SelectButton_Click);
        ConfigureButton(_resetButton, "既定値に戻す", ResetButton_Click);
        toolbar.Controls.AddRange([_importButton, _saveButton, _selectButton, _resetButton]);
        toolbar.Controls.Add(new Label { AutoSize = true, Text = "検索", Margin = new Padding(18, 8, 3, 3) });
        _searchBox.Width = 320;
        _searchBox.PlaceholderText = "日本語名・英語名・Key・説明・カテゴリを横断検索";
        _searchBox.TextChanged += SearchBox_TextChanged;
        toolbar.Controls.Add(_searchBox);

        _categories.Dock = DockStyle.Fill;
        _categories.Height = 32;
        _categories.SelectedIndexChanged += Categories_SelectedIndexChanged;

        SplitContainer content = new SplitContainer { Dock = DockStyle.Fill, Orientation = Orientation.Vertical, SplitterDistance = 820, Panel1MinSize = 520, Panel2MinSize = 260 };
        ConfigureGrid();
        content.Panel1.Controls.Add(_grid);
        GroupBox detailsGroup = new GroupBox { Dock = DockStyle.Fill, Text = "設定詳細", Padding = new Padding(8) };
        _details.Dock = DockStyle.Fill;
        _details.Multiline = true;
        _details.ReadOnly = true;
        _details.ScrollBars = ScrollBars.Vertical;
        _details.BackColor = SystemColors.Window;
        detailsGroup.Controls.Add(_details);
        content.Panel2.Controls.Add(detailsGroup);

        _status.AutoSize = true;
        _status.Dock = DockStyle.Fill;
        _status.Padding = new Padding(4);
        _status.Text = "カタログを読み込んでいます。";

        root.Controls.Add(toolbar, 0, 0);
        root.Controls.Add(_categories, 0, 1);
        root.Controls.Add(content, 0, 2);
        root.Controls.Add(_status, 0, 3);
        Controls.Add(root);
    }

    private void ConfigureGrid()
    {
        _grid.Dock = DockStyle.Fill;
        _grid.AutoGenerateColumns = false;
        _grid.AllowUserToAddRows = false;
        _grid.AllowUserToDeleteRows = false;
        _grid.RowHeadersVisible = false;
        _grid.SelectionMode = DataGridViewSelectionMode.FullRowSelect;
        _grid.MultiSelect = false;
        _grid.RowTemplate.Height = 26;
        _grid.CellValidating += Grid_CellValidating;
        _grid.CellValueChanged += Grid_CellValueChanged;
        _grid.CurrentCellDirtyStateChanged += Grid_CurrentCellDirtyStateChanged;
        _grid.SelectionChanged += Grid_SelectionChanged;
        _grid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = nameof(GameSettingEditorItem.Category), HeaderText = "カテゴリ", ReadOnly = true, Width = 130, Visible = false });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = nameof(GameSettingEditorItem.Name), HeaderText = "設定項目", ReadOnly = true, Width = 270 });
        _grid.Columns.Add(new DataGridViewCheckBoxColumn { DataPropertyName = nameof(GameSettingEditorItem.Enabled), HeaderText = "反映", Width = 54 });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = nameof(GameSettingEditorItem.Value), HeaderText = "設定値", Width = 155 });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = nameof(GameSettingEditorItem.CurrentIniValue), HeaderText = "現在のINI値", ReadOnly = true, Width = 145 });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = nameof(GameSettingEditorItem.DefaultValue), HeaderText = "既定値", ReadOnly = true, Width = 110 });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = nameof(GameSettingEditorItem.Status), HeaderText = "状態", ReadOnly = true, Width = 80 });
    }

    private async void GameSettingsView_Load(object? sender, EventArgs eventArgs)
    {
        SetBusy(true, "ゲーム設定カタログを読み込んでいます。");
        OperationResult<GameSettingsWorkspace> result = await _service.LoadAsync(CancellationToken.None);
        if (!result.Succeeded || result.Value is null)
        {
            ShowFailure(result);
            SetBusy(false, result.ErrorMessage ?? "カタログを読み込めません。");
            return;
        }
        _workspace = result.Value;
        _session = new GameSettingsSession(result.Value);
        BindCategoryTabs();
        BindVisibleItems();
        SetBusy(false, $"{result.Value.Definitions.Count}件を{_session.Categories.Count}カテゴリへ読み込みました。");
    }

    private async void ImportButton_Click(object? sender, EventArgs eventArgs)
    {
        if (_workspace is null)
        {
            return;
        }
        CommitGridEdits();
        SetBusy(true, "INIから設定を読み込んでいます。");
        OperationResult result = await _service.ImportFromIniAsync(_workspace, CancellationToken.None);
        if (!result.Succeeded)
        {
            ShowFailure(result);
            SetBusy(false, result.ErrorMessage ?? "INIから読み込めません。");
            return;
        }
        BindVisibleItems();
        SetBusy(false, CreateSuccessMessage("INIから既知設定を読み込みました。", result.Warnings));
    }

    private async void SaveButton_Click(object? sender, EventArgs eventArgs)
    {
        if (_workspace is null)
        {
            return;
        }
        CommitGridEdits();
        if (MessageBox.Show(this, "反映ONの設定をINIへ保存しますか？\n反映OFFの既存Keyは削除しません。", "ASA Server Manager", MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes)
        {
            return;
        }
        SetBusy(true, "INIをバックアップして保存しています。");
        OperationResult result = await _service.SaveToIniAsync(_workspace, CancellationToken.None);
        if (!result.Succeeded)
        {
            ShowFailure(result);
            SetBusy(false, result.ErrorMessage ?? "INIへ保存できません。");
            return;
        }
        BindVisibleItems();
        SetBusy(false, CreateSuccessMessage("INIへ保存し、再読込を確認しました。", result.Warnings));
    }

    private void SelectButton_Click(object? sender, EventArgs eventArgs)
    {
        if (_session is null)
        {
            return;
        }
        CommitGridEdits();
        OperationResult result = _session.ToggleCurrentCategory();
        if (!result.Succeeded)
        {
            ShowFailure(result);
            return;
        }
        BindVisibleItems();
        _status.Text = "現在カテゴリの反映状態を切り替えました。値は変更していません。";
    }

    private void ResetButton_Click(object? sender, EventArgs eventArgs)
    {
        if (_session is null || _session.IsSearchMode)
        {
            return;
        }
        if (MessageBox.Show(this, "現在カテゴリの編集値を既定値へ戻しますか？\n反映状態とINIファイルは変更しません。", "ASA Server Manager", MessageBoxButtons.YesNo, MessageBoxIcon.Warning) != DialogResult.Yes)
        {
            return;
        }
        CommitGridEdits();
        OperationResult result = _session.ResetCurrentCategoryDefaults();
        if (!result.Succeeded)
        {
            ShowFailure(result);
            return;
        }
        BindVisibleItems();
        _status.Text = "現在カテゴリの編集値を既定値へ戻しました。";
    }

    private void SearchBox_TextChanged(object? sender, EventArgs eventArgs)
    {
        if (_session is null)
        {
            return;
        }
        CommitGridEdits();
        _session.SetSearch(_searchBox.Text);
        _categories.Enabled = !_session.IsSearchMode;
        _selectButton.Enabled = !_session.IsSearchMode;
        _resetButton.Enabled = !_session.IsSearchMode;
        SelectCategoryTab(_session.SelectedCategory);
        BindVisibleItems();
        if (_session.IsSearchMode)
        {
            _status.Text = $"全カテゴリ横断の検索結果: {_grid.Rows.Count}件。検索中はカテゴリ一括操作を無効化しています。";
        }
    }

    private void Categories_SelectedIndexChanged(object? sender, EventArgs eventArgs)
    {
        if (_bindingCategories || _session is null || _categories.SelectedTab is null)
        {
            return;
        }
        CommitGridEdits();
        _session.SelectCategory(_categories.SelectedTab.Text);
        BindVisibleItems();
    }

    private void Grid_CellValidating(object? sender, DataGridViewCellValidatingEventArgs eventArgs)
    {
        if (eventArgs.RowIndex < 0 || eventArgs.ColumnIndex != 3)
        {
            return;
        }
        GameSettingEditorItem? item = _grid.Rows[eventArgs.RowIndex].DataBoundItem as GameSettingEditorItem;
        if (item is null)
        {
            return;
        }
        string? oldValue = item.State.EditedValue;
        item.State.EditedValue = eventArgs.FormattedValue?.ToString();
        OperationResult validation = GameSettingValueValidator.Validate(item.Definition, item.State);
        item.State.EditedValue = oldValue;
        if (!validation.Succeeded)
        {
            eventArgs.Cancel = true;
            _grid.Rows[eventArgs.RowIndex].ErrorText = validation.ErrorMessage ?? "設定値を確認してください。";
            _status.Text = _grid.Rows[eventArgs.RowIndex].ErrorText;
            return;
        }
        _grid.Rows[eventArgs.RowIndex].ErrorText = string.Empty;
    }

    private void Grid_CurrentCellDirtyStateChanged(object? sender, EventArgs eventArgs)
    {
        if (_grid.IsCurrentCellDirty)
        {
            _grid.CommitEdit(DataGridViewDataErrorContexts.Commit);
        }
    }

    private void Grid_CellValueChanged(object? sender, DataGridViewCellEventArgs eventArgs)
    {
        if (eventArgs.RowIndex >= 0)
        {
            ShowSelectedDetails();
        }
    }

    private void Grid_SelectionChanged(object? sender, EventArgs eventArgs)
    {
        ShowSelectedDetails();
    }

    private void BindCategoryTabs()
    {
        if (_session is null)
        {
            return;
        }
        _bindingCategories = true;
        _categories.TabPages.Clear();
        foreach (string category in _session.Categories)
        {
            _categories.TabPages.Add(new TabPage(category));
        }
        SelectCategoryTab(_session.SelectedCategory);
        _bindingCategories = false;
    }

    private void SelectCategoryTab(string category)
    {
        foreach (TabPage page in _categories.TabPages)
        {
            if (string.Equals(page.Text, category, StringComparison.Ordinal))
            {
                _categories.SelectedTab = page;
                return;
            }
        }
    }

    private void BindVisibleItems()
    {
        if (_session is null)
        {
            return;
        }
        IReadOnlyList<GameSettingEditorItem> items = _session.GetVisibleItems();
        _grid.Columns[0].Visible = _session.IsSearchMode;
        _grid.DataSource = new BindingList<GameSettingEditorItem>(items.ToList());
        ConfigureValueCells(items);
        ShowSelectedDetails();
    }

    private void ConfigureValueCells(IReadOnlyList<GameSettingEditorItem> items)
    {
        for (int index = 0; index < items.Count; index++)
        {
            GameSettingDefinition definition = items[index].Definition;
            if (definition.ValueType == GameSettingValueType.Boolean)
            {
                DataGridViewComboBoxCell booleanCell = new DataGridViewComboBoxCell();
                booleanCell.Items.AddRange("True", "False");
                booleanCell.Value = items[index].Value;
                _grid.Rows[index].Cells[3] = booleanCell;
            }
            else if (definition.ValueType == GameSettingValueType.Enum && definition.EnumValues.Count > 0)
            {
                DataGridViewComboBoxCell enumCell = new DataGridViewComboBoxCell();
                enumCell.Items.AddRange(definition.EnumValues.Cast<object>().ToArray());
                enumCell.Value = items[index].Value;
                _grid.Rows[index].Cells[3] = enumCell;
            }
            if (definition.ValueType == GameSettingValueType.Complex)
            {
                _grid.Rows[index].Cells[3].ToolTipText = "複合設定です。構造を維持したRaw文字列を編集してください。";
            }
            _grid.Rows[index].Cells[1].ToolTipText = definition.DisplayNameJa;
        }
    }

    private void ShowSelectedDetails()
    {
        GameSettingEditorItem? item = _grid.CurrentRow?.DataBoundItem as GameSettingEditorItem;
        if (item is null)
        {
            _details.Text = "設定を選択すると詳細を表示します。";
            return;
        }
        GameSettingDefinition definition = item.Definition;
        StringBuilder builder = new StringBuilder();
        AppendDetail(builder, "日本語設定名", definition.DisplayNameJa);
        AppendDetail(builder, "説明", definition.DescriptionJa);
        AppendDetail(builder, "カテゴリ", definition.UiCategory);
        AppendDetail(builder, "サブカテゴリ", definition.UiSubCategory);
        AppendDetail(builder, "現在の編集値", item.State.EditedValue);
        AppendDetail(builder, "現在のINI値", item.State.CurrentIniValue);
        AppendDetail(builder, "既定値", definition.DefaultValue);
        AppendDetail(builder, "Support Status", definition.SupportStatus.ToString());
        string restartRequired = "不要";
        if (definition.RestartRequired)
        {
            restartRequired = "必要";
        }
        AppendDetail(builder, "再起動要否", restartRequired);
        string iniFile = "GameUserSettings.ini";
        if (definition.FileKind == IniFileKind.Game)
        {
            iniFile = "Game.ini";
        }
        AppendDetail(builder, "INIファイル", iniFile);
        AppendDetail(builder, "Section", definition.Section);
        AppendDetail(builder, "Key", definition.Key);
        AppendDetail(builder, "英語名", definition.DisplayNameEn);
        AppendDetail(builder, "値形式", definition.ValueType.ToString());
        AppendDetail(builder, "Notes", definition.Notes);
        if (definition.SupportStatus == SupportStatus.Unverified)
        {
            builder.AppendLine();
            builder.AppendLine("注意: この設定は未検証です。実機確認後に使用してください。");
        }
        if (definition.ValueType == GameSettingValueType.Complex)
        {
            builder.AppendLine();
            builder.AppendLine("注意: 複合設定です。Raw文字列の構造を保持してください。");
        }
        _details.Text = builder.ToString();
    }

    private void CommitGridEdits()
    {
        _grid.EndEdit();
        object? dataSource = _grid.DataSource;
        if (dataSource is null)
        {
            return;
        }
        BindingContext? context = BindingContext;
        if (context is null)
        {
            return;
        }
        CurrencyManager? manager = context[dataSource] as CurrencyManager;
        manager?.EndCurrentEdit();
    }

    private void ShowFailure(OperationResult result)
    {
        _statusStore.Record(result);
        MessageBox.Show(this, result.UserMessage ?? result.ErrorMessage ?? "ゲーム設定操作に失敗しました。", "ASA Server Manager", MessageBoxButtons.OK, MessageBoxIcon.Error);
    }

    private void SetBusy(bool busy, string message)
    {
        _importButton.Enabled = !busy;
        _saveButton.Enabled = !busy;
        bool categoryActionEnabled = !busy;
        if (_session is not null && _session.IsSearchMode)
        {
            categoryActionEnabled = false;
        }
        _selectButton.Enabled = categoryActionEnabled;
        _resetButton.Enabled = categoryActionEnabled;
        _searchBox.Enabled = !busy;
        _categories.Enabled = !busy && (_session is null || !_session.IsSearchMode);
        _grid.Enabled = !busy;
        _status.Text = message;
    }

    private static void ConfigureButton(Button button, string text, EventHandler handler)
    {
        button.AutoSize = true;
        button.Text = text;
        button.Click += handler;
    }

    private static void AppendDetail(StringBuilder builder, string label, string? value)
    {
        builder.Append(label);
        builder.Append(": ");
        if (string.IsNullOrWhiteSpace(value))
        {
            builder.AppendLine("-");
            return;
        }
        builder.AppendLine(value);
    }

    private static string CreateSuccessMessage(string message, IReadOnlyList<string> warnings)
    {
        if (warnings.Count == 0)
        {
            return message;
        }
        return message + " 警告: " + string.Join(" / ", warnings);
    }
}
