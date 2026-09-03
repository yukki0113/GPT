using System.ComponentModel;
using ASA.ServerManager.Application;
using ASA.ServerManager.Domain;

namespace ASA.ServerManager.WinForms;

/// <summary>手動Project IDによるMOD追加、削除、並び替え、保存を提供します。</summary>
public sealed class ModsView : UserControl
{
    private readonly ModSettingsService _service;
    private readonly IApplicationStatusStore _statusStore;
    private readonly DataGridView _grid = new DataGridView();
    private readonly TextBox _projectId = new TextBox();
    private readonly TextBox _name = new TextBox();
    private readonly Button _add = new Button();
    private readonly Button _remove = new Button();
    private readonly Button _up = new Button();
    private readonly Button _down = new Button();
    private readonly Button _save = new Button();
    private readonly Label _status = new Label();
    private List<ModRow> _rows = [];

    /// <summary>MOD設定Application serviceを受け取って画面を構築します。</summary>
    public ModsView(ModSettingsService service, IApplicationStatusStore statusStore)
    {
        _service = service;
        _statusStore = statusStore;
        AutoScaleMode = AutoScaleMode.Dpi;
        BuildLayout();
        Load += ModsView_Load;
    }

    private void BuildLayout()
    {
        TableLayoutPanel root = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 3, Padding = new Padding(12) };
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));

        FlowLayoutPanel editor = new FlowLayoutPanel { AutoSize = true, Dock = DockStyle.Fill, WrapContents = true };
        editor.Controls.Add(new Label { AutoSize = true, Text = "Project ID", Margin = new Padding(3, 8, 3, 3) });
        _projectId.Width = 150;
        editor.Controls.Add(_projectId);
        editor.Controls.Add(new Label { AutoSize = true, Text = "MOD名（任意）", Margin = new Padding(12, 8, 3, 3) });
        _name.Width = 260;
        editor.Controls.Add(_name);
        ConfigureButton(_add, "追加", Add_Click);
        editor.Controls.Add(_add);

        _grid.Dock = DockStyle.Fill;
        _grid.AutoGenerateColumns = false;
        _grid.AllowUserToAddRows = false;
        _grid.AllowUserToDeleteRows = false;
        _grid.MultiSelect = false;
        _grid.SelectionMode = DataGridViewSelectionMode.FullRowSelect;
        _grid.RowHeadersVisible = false;
        _grid.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill;
        _grid.Columns.Add(new DataGridViewCheckBoxColumn { DataPropertyName = nameof(ModRow.Enabled), HeaderText = "有効", FillWeight = 18 });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = nameof(ModRow.Order), HeaderText = "順序", ReadOnly = true, FillWeight = 20 });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = nameof(ModRow.ProjectId), HeaderText = "Project ID", FillWeight = 42 });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = nameof(ModRow.Name), HeaderText = "MOD名", FillWeight = 80 });

        FlowLayoutPanel commands = new FlowLayoutPanel { AutoSize = true, Dock = DockStyle.Fill, WrapContents = true };
        ConfigureButton(_remove, "削除", Remove_Click);
        ConfigureButton(_up, "上へ", MoveUp_Click);
        ConfigureButton(_down, "下へ", MoveDown_Click);
        ConfigureButton(_save, "保存", Save_Click);
        _status.AutoSize = true;
        _status.Margin = new Padding(16, 8, 0, 0);
        _status.Text = "MOD設定を読み込んでいます。";
        commands.Controls.AddRange([_remove, _up, _down, _save, _status]);

        root.Controls.Add(editor, 0, 0);
        root.Controls.Add(_grid, 0, 1);
        root.Controls.Add(commands, 0, 2);
        Controls.Add(root);
    }

    private async void ModsView_Load(object? sender, EventArgs eventArgs)
    {
        SetBusy(true, "MOD設定を読み込んでいます。");
        OperationResult<IReadOnlyList<ModDefinition>> result = await _service.LoadAsync(CancellationToken.None);
        if (!result.Succeeded || result.Value is null)
        {
            ShowFailure(result);
            SetBusy(false, result.ErrorMessage ?? "MOD設定を読み込めません。");
            return;
        }
        Bind(result.Value);
        SetBusy(false, $"{_rows.Count}件のMODを読み込みました。");
    }

    private void Add_Click(object? sender, EventArgs eventArgs)
    {
        CommitGridEdits();
        OperationResult<IReadOnlyList<ModDefinition>> result = _service.Add(ToDefinitions(), _projectId.Text, _name.Text);
        if (!ApplyResult(result))
        {
            return;
        }
        _projectId.Clear();
        _name.Clear();
        _status.Text = "MODを追加しました。保存すると次回起動時に反映されます。";
    }

    private void Remove_Click(object? sender, EventArgs eventArgs)
    {
        int index = GetSelectedIndex();
        if (index < 0)
        {
            ShowFailure(OperationResult.Failure("削除するMODを選択してください。", errorCode: "MOD_SELECTION_REQUIRED"));
            return;
        }
        if (MessageBox.Show(this, "選択したMODを一覧から削除しますか？", "ASA Server Manager", MessageBoxButtons.YesNo, MessageBoxIcon.Warning) != DialogResult.Yes)
        {
            return;
        }
        CommitGridEdits();
        ApplyResult(_service.Remove(ToDefinitions(), index));
    }

    private void MoveUp_Click(object? sender, EventArgs eventArgs)
    {
        MoveSelected(true);
    }

    private void MoveDown_Click(object? sender, EventArgs eventArgs)
    {
        MoveSelected(false);
    }

    private void MoveSelected(bool moveUp)
    {
        int index = GetSelectedIndex();
        CommitGridEdits();
        OperationResult<IReadOnlyList<ModDefinition>> result;
        if (moveUp)
        {
            result = _service.MoveUp(ToDefinitions(), index);
        }
        else
        {
            result = _service.MoveDown(ToDefinitions(), index);
        }
        if (ApplyResult(result))
        {
            int selectedIndex = index + 1;
            if (moveUp)
            {
                selectedIndex = index - 1;
            }
            if (selectedIndex >= 0 && selectedIndex < _grid.Rows.Count)
            {
                _grid.Rows[selectedIndex].Selected = true;
            }
        }
    }

    private async void Save_Click(object? sender, EventArgs eventArgs)
    {
        CommitGridEdits();
        SetBusy(true, "MOD設定を保存しています。");
        OperationResult<IReadOnlyList<ModDefinition>> result = await _service.SaveAsync(ToDefinitions(), CancellationToken.None);
        if (!result.Succeeded || result.Value is null)
        {
            ShowFailure(result);
            SetBusy(false, result.ErrorMessage ?? "MOD設定を保存できません。");
            return;
        }
        Bind(result.Value);
        SetBusy(false, "MOD設定を保存しました。次回の起動／再起動時に反映されます。");
    }

    private bool ApplyResult(OperationResult<IReadOnlyList<ModDefinition>> result)
    {
        if (!result.Succeeded || result.Value is null)
        {
            ShowFailure(result);
            return false;
        }
        Bind(result.Value);
        return true;
    }

    private void Bind(IReadOnlyList<ModDefinition> definitions)
    {
        _rows = definitions.OrderBy(mod => mod.Order).Select(mod => new ModRow(mod)).ToList();
        _grid.DataSource = new BindingList<ModRow>(_rows);
    }

    private IReadOnlyList<ModDefinition> ToDefinitions()
    {
        return _rows.Select((row, index) => new ModDefinition { ProjectId = row.ProjectId.Trim(), Name = row.Name.Trim(), Enabled = row.Enabled, Order = index }).ToList();
    }

    private void CommitGridEdits()
    {
        _grid.EndEdit();
        object? dataSource = _grid.DataSource;
        if (dataSource is null)
        {
            return;
        }
        CurrencyManager? manager = BindingContext[dataSource] as CurrencyManager;
        manager?.EndCurrentEdit();
    }

    private int GetSelectedIndex()
    {
        if (_grid.CurrentRow is null)
        {
            return -1;
        }
        return _grid.CurrentRow.Index;
    }

    private void ShowFailure(OperationResult result)
    {
        _statusStore.Record(result);
        MessageBox.Show(this, result.UserMessage ?? result.ErrorMessage ?? "MOD操作に失敗しました。", "ASA Server Manager", MessageBoxButtons.OK, MessageBoxIcon.Error);
    }

    private void SetBusy(bool busy, string message)
    {
        _add.Enabled = !busy;
        _remove.Enabled = !busy;
        _up.Enabled = !busy;
        _down.Enabled = !busy;
        _save.Enabled = !busy;
        _status.Text = message;
    }

    private static void ConfigureButton(Button button, string text, EventHandler handler)
    {
        button.AutoSize = true;
        button.Text = text;
        button.Click += handler;
    }

    private sealed class ModRow
    {
        public ModRow(ModDefinition definition)
        {
            Enabled = definition.Enabled;
            Order = definition.Order + 1;
            ProjectId = definition.ProjectId;
            Name = definition.Name;
        }

        public bool Enabled { get; set; }
        public int Order { get; set; }
        public string ProjectId { get; set; }
        public string Name { get; set; }
    }
}
