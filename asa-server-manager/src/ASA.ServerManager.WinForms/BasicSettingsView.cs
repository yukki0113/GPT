using ASA.ServerManager.Application;
using ASA.ServerManager.Domain;

namespace ASA.ServerManager.WinForms;

/// <summary>サーバー、MAP、Port、RCON、秘密情報を編集して保存します。</summary>
public sealed class BasicSettingsView : UserControl
{
    private readonly BasicSettingsService _service;
    private readonly ServerOrchestrator _serverOrchestrator;
    private readonly IApplicationStatusStore _statusStore;
    private readonly TextBox _serverName = new TextBox();
    private readonly NumericUpDown _maxPlayers = CreateNumber(1, 1000, 20);
    private readonly ComboBox _gameMode = new ComboBox();
    private readonly ComboBox _map = new ComboBox();
    private readonly TextBox _mapLevelName = new TextBox();
    private readonly TextBox _customMapModId = new TextBox();
    private readonly TextBox _serverPath = new TextBox();
    private readonly TextBox _steamCmdPath = new TextBox();
    private readonly NumericUpDown _gamePort = CreatePort(7777);
    private readonly NumericUpDown _peerPort = CreatePort(7778);
    private readonly NumericUpDown _queryPort = CreatePort(27015);
    private readonly NumericUpDown _rconPort = CreatePort(27020);
    private readonly CheckBox _rconEnabled = new CheckBox();
    private readonly CheckBox _exposeRcon = new CheckBox();
    private readonly TextBox _rconPassword = CreatePasswordBox();
    private readonly TextBox _serverPassword = CreatePasswordBox();
    private readonly TextBox _adminPassword = CreatePasswordBox();
    private readonly TextBox _spectatorPassword = CreatePasswordBox();
    private readonly TextBox _extraArguments = new TextBox();
    private readonly Button _saveButton = new Button();
    private readonly Label _statusLabel = new Label();
    private readonly ErrorProvider _errors = new ErrorProvider();
    private IReadOnlyList<MapDefinition> _maps = [];

    /// <summary>基本設定用Application serviceを受け取って画面を構築します。</summary>
    public BasicSettingsView(BasicSettingsService service, ServerOrchestrator serverOrchestrator, IApplicationStatusStore statusStore)
    {
        _service = service;
        _serverOrchestrator = serverOrchestrator;
        _statusStore = statusStore;
        AutoScaleMode = AutoScaleMode.Dpi;
        AutoScroll = true;
        _errors.ContainerControl = this;
        BuildLayout();
        Load += BasicSettingsView_Load;
    }

    private void BuildLayout()
    {
        TableLayoutPanel root = new TableLayoutPanel();
        root.AutoSize = true;
        root.AutoSizeMode = AutoSizeMode.GrowAndShrink;
        root.ColumnCount = 2;
        root.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
        root.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
        root.Dock = DockStyle.Top;
        root.Padding = new Padding(12);

        GroupBox serverGroup = CreateGroup("サーバー", CreateServerPanel());
        GroupBox mapGroup = CreateGroup("MAP", CreateMapPanel());
        GroupBox pathsGroup = CreateGroup("インストール先", CreatePathsPanel());
        GroupBox portsGroup = CreateGroup("Port", CreatePortsPanel());
        GroupBox rconGroup = CreateGroup("RCON", CreateRconPanel());
        GroupBox passwordGroup = CreateGroup("Password", CreatePasswordPanel());
        GroupBox advancedGroup = CreateGroup("高度", CreateAdvancedPanel());

        root.Controls.Add(serverGroup, 0, 0);
        root.Controls.Add(mapGroup, 1, 0);
        root.Controls.Add(pathsGroup, 0, 1);
        root.SetColumnSpan(pathsGroup, 2);
        root.Controls.Add(portsGroup, 0, 2);
        root.Controls.Add(rconGroup, 1, 2);
        root.Controls.Add(passwordGroup, 0, 3);
        root.Controls.Add(advancedGroup, 1, 3);

        FlowLayoutPanel commands = new FlowLayoutPanel();
        commands.AutoSize = true;
        commands.Dock = DockStyle.Top;
        commands.Padding = new Padding(12, 4, 12, 12);
        _saveButton.AutoSize = true;
        _saveButton.Text = "設定を保存";
        _saveButton.Click += SaveButton_Click;
        _statusLabel.AutoSize = true;
        _statusLabel.Margin = new Padding(16, 8, 0, 0);
        _statusLabel.Text = "設定を読み込んでいます。";
        commands.Controls.Add(_saveButton);
        commands.Controls.Add(_statusLabel);

        Controls.Add(commands);
        Controls.Add(root);
    }

    private Control CreateServerPanel()
    {
        _gameMode.DropDownStyle = ComboBoxStyle.DropDownList;
        _gameMode.Items.AddRange(["PvE", "PvP"]);
        TableLayoutPanel panel = CreateFormPanel();
        AddField(panel, "サーバー名", _serverName);
        AddField(panel, "最大参加人数", _maxPlayers);
        AddField(panel, "ゲームモード", _gameMode);
        return panel;
    }

    private Control CreateMapPanel()
    {
        _map.DropDownStyle = ComboBoxStyle.DropDownList;
        _map.DisplayMember = nameof(MapChoice.DisplayName);
        _map.SelectedIndexChanged += Map_SelectedIndexChanged;
        AddFieldTooltip(_mapLevelName, "公式MAPでは選択内容から自動設定されます。カスタムMAPではLevel Nameを入力してください。");
        TableLayoutPanel panel = CreateFormPanel();
        AddField(panel, "MAP選択", _map);
        AddField(panel, "MAP Level Name", _mapLevelName);
        AddField(panel, "Custom Map MOD Project ID", _customMapModId);
        return panel;
    }

    private Control CreatePathsPanel()
    {
        TableLayoutPanel panel = CreateFormPanel();
        AddPathField(panel, "ASA Dedicated Server Path", _serverPath, SelectServerPath_Click);
        AddPathField(panel, "SteamCMD Path", _steamCmdPath, SelectSteamCmdPath_Click);
        return panel;
    }

    private Control CreatePortsPanel()
    {
        TableLayoutPanel panel = CreateFormPanel();
        AddField(panel, "Game Port", _gamePort);
        AddField(panel, "Peer Port", _peerPort);
        AddField(panel, "Query Port", _queryPort);
        AddField(panel, "RCON Port", _rconPort);
        return panel;
    }

    private Control CreateRconPanel()
    {
        _rconEnabled.Text = "RCONを有効にする";
        _exposeRcon.Text = "RCONを外部へ公開する";
        TableLayoutPanel panel = CreateFormPanel();
        AddField(panel, string.Empty, _rconEnabled);
        AddField(panel, string.Empty, _exposeRcon);
        AddField(panel, "RCON Password", _rconPassword);
        return panel;
    }

    private Control CreatePasswordPanel()
    {
        TableLayoutPanel panel = CreateFormPanel();
        AddField(panel, "Server Password", _serverPassword);
        AddField(panel, "Admin Password", _adminPassword);
        AddField(panel, "Spectator Password", _spectatorPassword);
        return panel;
    }

    private Control CreateAdvancedPanel()
    {
        _extraArguments.Multiline = true;
        _extraArguments.Height = 78;
        _extraArguments.ScrollBars = ScrollBars.Vertical;
        TableLayoutPanel panel = CreateFormPanel();
        AddField(panel, "Extra Arguments", _extraArguments);
        return panel;
    }

    private async void BasicSettingsView_Load(object? sender, EventArgs eventArgs)
    {
        await LoadSettingsAsync();
    }

    private async Task LoadSettingsAsync()
    {
        SetBusy(true, "設定を読み込んでいます。");
        OperationResult<BasicSettingsData> result = await _service.LoadAsync(CancellationToken.None);
        if (!result.Succeeded || result.Value is null)
        {
            ShowResult(result);
            SetBusy(false, result.ErrorMessage ?? "設定を読み込めません。");
            return;
        }
        _maps = result.Value.Maps;
        BindMaps(result.Value.Settings.MapId);
        ApplyData(result.Value);
        SetBusy(false, "保存内容を読み込みました。");
    }

    private async void SaveButton_Click(object? sender, EventArgs eventArgs)
    {
        _errors.Clear();
        SetBusy(true, "入力内容を確認しています。");
        ServerSnapshot snapshot = await _serverOrchestrator.GetSnapshotAsync(CancellationToken.None);
        OperationResult<BasicSettingsData> result = await _service.SaveAsync(CreateSettings(), CreateSecrets(), snapshot.State == ServerState.Running, CancellationToken.None);
        ShowResult(result);
        if (!result.Succeeded || result.Value is null)
        {
            SetBusy(false, result.ErrorMessage ?? "保存できませんでした。");
            _errors.SetError(_saveButton, result.ErrorMessage ?? "入力内容を確認してください。");
            return;
        }
        ApplyData(result.Value);
        string message = "設定を保存しました。";
        if (result.Warnings.Count > 0)
        {
            message = message + " " + string.Join(" ", result.Warnings);
        }
        SetBusy(false, message);
    }

    private ServerSettings CreateSettings()
    {
        MapChoice? selected = _map.SelectedItem as MapChoice;
        string mapId = selected?.Id ?? string.Empty;
        ServerGameMode gameMode = ServerGameMode.Pve;
        if (_gameMode.SelectedIndex == 1)
        {
            gameMode = ServerGameMode.Pvp;
        }
        return new ServerSettings
        {
            DedicatedServerPath = _serverPath.Text.Trim(),
            SteamCmdPath = _steamCmdPath.Text.Trim(),
            MapId = mapId,
            MapLevelName = _mapLevelName.Text.Trim(),
            ServerName = _serverName.Text.Trim(),
            MaxPlayers = Decimal.ToInt32(_maxPlayers.Value),
            GameMode = gameMode,
            RconEnabled = _rconEnabled.Checked,
            ExposeRcon = _exposeRcon.Checked,
            ExtraArguments = _extraArguments.Text.Trim(),
            CustomMapModProjectId = NullIfEmpty(_customMapModId.Text),
            Ports = new PortSettings { GamePort = Decimal.ToInt32(_gamePort.Value), PeerPort = Decimal.ToInt32(_peerPort.Value), QueryPort = Decimal.ToInt32(_queryPort.Value), RconPort = Decimal.ToInt32(_rconPort.Value) }
        };
    }

    private ServerSecrets CreateSecrets()
    {
        return new ServerSecrets { RconPassword = _rconPassword.Text, ServerPassword = _serverPassword.Text, AdminPassword = _adminPassword.Text, SpectatorPassword = _spectatorPassword.Text };
    }

    private void ApplyData(BasicSettingsData data)
    {
        ServerSettings settings = data.Settings;
        _serverName.Text = settings.ServerName;
        SetNumber(_maxPlayers, settings.MaxPlayers);
        _gameMode.SelectedIndex = 0;
        if (settings.GameMode == ServerGameMode.Pvp)
        {
            _gameMode.SelectedIndex = 1;
        }
        SelectMap(settings.MapId);
        _mapLevelName.Text = settings.MapLevelName;
        _customMapModId.Text = settings.CustomMapModProjectId ?? string.Empty;
        _serverPath.Text = settings.DedicatedServerPath;
        _steamCmdPath.Text = settings.SteamCmdPath;
        SetNumber(_gamePort, settings.Ports.GamePort);
        SetNumber(_peerPort, settings.Ports.PeerPort);
        SetNumber(_queryPort, settings.Ports.QueryPort);
        SetNumber(_rconPort, settings.Ports.RconPort);
        _rconEnabled.Checked = settings.RconEnabled;
        _exposeRcon.Checked = settings.ExposeRcon;
        _extraArguments.Text = settings.ExtraArguments;
        _rconPassword.Text = data.Secrets.RconPassword;
        _serverPassword.Text = data.Secrets.ServerPassword;
        _adminPassword.Text = data.Secrets.AdminPassword;
        _spectatorPassword.Text = data.Secrets.SpectatorPassword;
        UpdateMapEditingState();
    }

    private void BindMaps(string selectedMapId)
    {
        List<MapChoice> choices = _maps.Select(map => new MapChoice(map.Id, map.DisplayNameJa, map.LevelName, false)).ToList();
        choices.Add(new MapChoice("custom", "カスタムMAP", string.Empty, true));
        _map.DataSource = choices;
        SelectMap(selectedMapId);
    }

    private void SelectMap(string mapId)
    {
        for (int index = 0; index < _map.Items.Count; index++)
        {
            MapChoice? choice = _map.Items[index] as MapChoice;
            if (choice is not null && string.Equals(choice.Id, mapId, StringComparison.OrdinalIgnoreCase))
            {
                _map.SelectedIndex = index;
                return;
            }
        }
        if (_map.Items.Count > 0)
        {
            _map.SelectedIndex = 0;
        }
    }

    private void Map_SelectedIndexChanged(object? sender, EventArgs eventArgs)
    {
        MapChoice? choice = _map.SelectedItem as MapChoice;
        if (choice is not null && !choice.IsCustom)
        {
            _mapLevelName.Text = choice.LevelName;
            _customMapModId.Text = string.Empty;
        }
        UpdateMapEditingState();
    }

    private void UpdateMapEditingState()
    {
        MapChoice? choice = _map.SelectedItem as MapChoice;
        bool isCustom = choice is not null && choice.IsCustom;
        _mapLevelName.ReadOnly = !isCustom;
        _customMapModId.Enabled = isCustom;
    }

    private void SelectServerPath_Click(object? sender, EventArgs eventArgs)
    {
        SelectFolder(_serverPath, "ASA Dedicated Serverのインストール先を選択してください");
    }

    private void SelectSteamCmdPath_Click(object? sender, EventArgs eventArgs)
    {
        SelectFolder(_steamCmdPath, "SteamCMDの保存先を選択してください");
    }

    private void SelectFolder(TextBox target, string description)
    {
        using FolderBrowserDialog dialog = new FolderBrowserDialog { Description = description, ShowNewFolderButton = true };
        if (Directory.Exists(target.Text))
        {
            dialog.SelectedPath = target.Text;
        }
        if (dialog.ShowDialog(this) == DialogResult.OK)
        {
            target.Text = dialog.SelectedPath;
        }
    }

    private void ShowResult(OperationResult result)
    {
        _statusStore.Record(result);
        if (!result.Succeeded)
        {
            MessageBox.Show(this, result.UserMessage ?? result.ErrorMessage ?? "操作に失敗しました。", "ASA Server Manager", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private void SetBusy(bool busy, string message)
    {
        _saveButton.Enabled = !busy;
        _statusLabel.Text = message;
    }

    private static GroupBox CreateGroup(string title, Control content)
    {
        GroupBox group = new GroupBox();
        group.AutoSize = true;
        group.AutoSizeMode = AutoSizeMode.GrowAndShrink;
        group.Dock = DockStyle.Fill;
        group.Padding = new Padding(10);
        group.Text = title;
        content.Dock = DockStyle.Top;
        group.Controls.Add(content);
        return group;
    }

    private static TableLayoutPanel CreateFormPanel()
    {
        TableLayoutPanel panel = new TableLayoutPanel();
        panel.AutoSize = true;
        panel.ColumnCount = 2;
        panel.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 190));
        panel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        panel.Dock = DockStyle.Top;
        return panel;
    }

    private static void AddField(TableLayoutPanel panel, string labelText, Control control)
    {
        int row = panel.RowCount;
        panel.RowCount++;
        Label label = new Label { AutoSize = true, Text = labelText, Anchor = AnchorStyles.Left, Margin = new Padding(3, 8, 8, 3) };
        control.Dock = DockStyle.Fill;
        control.Margin = new Padding(3, 4, 12, 4);
        panel.Controls.Add(label, 0, row);
        panel.Controls.Add(control, 1, row);
    }

    private static void AddPathField(TableLayoutPanel panel, string labelText, TextBox textBox, EventHandler clickHandler)
    {
        FlowLayoutPanel field = new FlowLayoutPanel { AutoSize = true, Dock = DockStyle.Fill, WrapContents = false };
        textBox.Width = 700;
        textBox.Anchor = AnchorStyles.Left | AnchorStyles.Right;
        Button selectButton = new Button { AutoSize = true, Text = "参照..." };
        selectButton.Click += clickHandler;
        field.Controls.Add(textBox);
        field.Controls.Add(selectButton);
        AddField(panel, labelText, field);
    }

    private static NumericUpDown CreatePort(int value)
    {
        return CreateNumber(1, 65535, value);
    }

    private static NumericUpDown CreateNumber(int minimum, int maximum, int value)
    {
        return new NumericUpDown { Minimum = minimum, Maximum = maximum, Value = value, ThousandsSeparator = false };
    }

    private static TextBox CreatePasswordBox()
    {
        return new TextBox { UseSystemPasswordChar = true };
    }

    private static void SetNumber(NumericUpDown control, int value)
    {
        if (value < control.Minimum)
        {
            control.Value = control.Minimum;
            return;
        }
        if (value > control.Maximum)
        {
            control.Value = control.Maximum;
            return;
        }
        control.Value = value;
    }

    private static string? NullIfEmpty(string value)
    {
        string normalized = value.Trim();
        if (normalized.Length == 0)
        {
            return null;
        }
        return normalized;
    }

    private static void AddFieldTooltip(Control control, string text)
    {
        ToolTip toolTip = new ToolTip();
        toolTip.SetToolTip(control, text);
    }

    private sealed record MapChoice(string Id, string DisplayName, string LevelName, bool IsCustom);
}
