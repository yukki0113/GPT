using ASA.ServerManager.Application;
using ASA.ServerManager.Domain;

namespace ASA.ServerManager.WinForms;

/// <summary>サーバー状態と、起動／再起動・停止の2操作だけを表示します。</summary>
public sealed class ServerControlView : UserControl
{
    private readonly ServerOrchestrator _orchestrator;
    private readonly IApplicationStatusStore _statusStore;
    private readonly Dictionary<string, Label> _values = new Dictionary<string, Label>(StringComparer.Ordinal);
    private readonly TextBox _lanCommand = CreateReadOnlyTextBox();
    private readonly TextBox _hamachiCommand = CreateReadOnlyTextBox();
    private readonly Label _progressText = new Label();
    private readonly ProgressBar _progressBar = new ProgressBar();
    private readonly Label _lastError = new Label();
    private readonly Button _start = new Button();
    private readonly Button _stop = new Button();
    private readonly System.Windows.Forms.Timer _timer;
    private bool _operationInProgress;

    /// <summary>実行オーケストレーターと共有状態を受け取って操作画面を構築します。</summary>
    public ServerControlView(ServerOrchestrator orchestrator, IApplicationStatusStore statusStore)
    {
        _orchestrator = orchestrator;
        _statusStore = statusStore;
        AutoScaleMode = AutoScaleMode.Dpi;
        BuildLayout();
        _timer = new System.Windows.Forms.Timer { Interval = 2000 };
        _timer.Tick += RefreshTimer_Tick;
        Load += ServerControlView_Load;
        Disposed += ServerControlView_Disposed;
    }

    private void BuildLayout()
    {
        TableLayoutPanel root = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 4, Padding = new Padding(16) };
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));

        GroupBox statusGroup = new GroupBox { AutoSize = true, Dock = DockStyle.Top, Text = "サーバー状態", Padding = new Padding(12) };
        TableLayoutPanel status = new TableLayoutPanel { AutoSize = true, Dock = DockStyle.Top, ColumnCount = 4 };
        status.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 120));
        status.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
        status.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 120));
        status.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
        AddStatus(status, 0, "状態", "state");
        AddStatus(status, 0, "状態詳細", "detail", 2);
        AddStatus(status, 1, "PID", "pid");
        AddStatus(status, 1, "RCON状態", "rcon", 2);
        AddStatus(status, 2, "Firewall状態", "firewall");
        AddStatus(status, 2, "現在MAP", "map", 2);
        AddStatus(status, 3, "有効MOD数", "mods");
        AddStatus(status, 3, "稼働時間", "uptime", 2);
        statusGroup.Controls.Add(status);

        GroupBox networkGroup = new GroupBox { AutoSize = true, Dock = DockStyle.Top, Text = "接続情報", Padding = new Padding(12) };
        TableLayoutPanel network = new TableLayoutPanel { AutoSize = true, Dock = DockStyle.Top, ColumnCount = 2 };
        network.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 160));
        network.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        AddNetworkRow(network, "LAN IPv4", "lan", null);
        AddNetworkRow(network, "LAN接続コマンド", null, _lanCommand);
        AddNetworkRow(network, "Hamachi IPv4", "hamachi", null);
        AddNetworkRow(network, "Hamachi接続コマンド", null, _hamachiCommand);
        networkGroup.Controls.Add(network);

        GroupBox operationGroup = new GroupBox { AutoSize = true, Dock = DockStyle.Top, Text = "操作", Padding = new Padding(12) };
        TableLayoutPanel operation = new TableLayoutPanel { AutoSize = true, Dock = DockStyle.Top, ColumnCount = 1, RowCount = 4 };
        FlowLayoutPanel buttons = new FlowLayoutPanel { AutoSize = true, Dock = DockStyle.Fill };
        _start.AutoSize = true;
        _start.Text = "起動／再起動";
        _start.Click += StartButton_Click;
        _stop.AutoSize = true;
        _stop.Text = "停止";
        _stop.Click += StopButton_Click;
        buttons.Controls.AddRange([_start, _stop]);
        _progressText.AutoSize = true;
        _progressText.Text = "現在の操作: 待機中";
        _progressBar.Dock = DockStyle.Top;
        _progressBar.Style = ProgressBarStyle.Blocks;
        _lastError.AutoSize = true;
        _lastError.ForeColor = Color.Firebrick;
        _lastError.MaximumSize = new Size(1050, 0);
        _lastError.Text = "最後のエラー: -";
        operation.Controls.Add(buttons, 0, 0);
        operation.Controls.Add(_progressText, 0, 1);
        operation.Controls.Add(_progressBar, 0, 2);
        operation.Controls.Add(_lastError, 0, 3);
        operationGroup.Controls.Add(operation);

        Label note = new Label { AutoSize = true, MaximumSize = new Size(1050, 0), Text = "設定不足の場合は［基本設定］で必須項目を保存してください。サーバー操作中は多重操作を防ぐためボタンを無効化します。" };
        root.Controls.Add(statusGroup, 0, 0);
        root.Controls.Add(networkGroup, 0, 1);
        root.Controls.Add(operationGroup, 0, 2);
        root.Controls.Add(note, 0, 3);
        Controls.Add(root);
    }

    private async void ServerControlView_Load(object? sender, EventArgs eventArgs)
    {
        _timer.Start();
        await RefreshSnapshotAsync();
    }

    private async void RefreshTimer_Tick(object? sender, EventArgs eventArgs)
    {
        await RefreshSnapshotAsync();
    }

    private async void StartButton_Click(object? sender, EventArgs eventArgs)
    {
        if (_operationInProgress)
        {
            return;
        }
        ServerSnapshot snapshot = await _orchestrator.GetSnapshotAsync(CancellationToken.None);
        if (snapshot.State == ServerState.Running && MessageBox.Show(this, "サーバーを安全に再起動しますか？", "ASA Server Manager", MessageBoxButtons.YesNo, MessageBoxIcon.Warning) != DialogResult.Yes)
        {
            return;
        }
        if (snapshot.State == ServerState.Running)
        {
            await ExecuteOperationAsync(_orchestrator.RestartAsync);
            return;
        }
        await ExecuteOperationAsync(_orchestrator.StartAsync);
    }

    private async void StopButton_Click(object? sender, EventArgs eventArgs)
    {
        if (_operationInProgress)
        {
            return;
        }
        if (MessageBox.Show(this, "SaveWorld後にサーバーを安全に停止しますか？", "ASA Server Manager", MessageBoxButtons.YesNo, MessageBoxIcon.Warning) != DialogResult.Yes)
        {
            return;
        }
        await ExecuteOperationAsync(_orchestrator.StopAsync);
    }

    private async Task ExecuteOperationAsync(Func<IProgress<OperationProgress>?, CancellationToken, Task<OperationResult>> operation)
    {
        _operationInProgress = true;
        ApplyBusyState();
        try
        {
            Progress<OperationProgress> progress = new Progress<OperationProgress>(UpdateProgress);
            OperationResult result = await operation(progress, CancellationToken.None);
            _statusStore.Record(result);
            if (!result.Succeeded)
            {
                string code = result.ErrorCode ?? "UNKNOWN";
                string message = result.UserMessage ?? result.ErrorMessage ?? "サーバー操作に失敗しました。";
                _lastError.Text = $"最後のエラー: {code} / {message}";
                MessageBox.Show(this, message, "ASA Server Manager", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }
        finally
        {
            _operationInProgress = false;
            _progressBar.Style = ProgressBarStyle.Blocks;
            _progressBar.Value = 0;
            await RefreshSnapshotAsync();
        }
    }

    private async Task RefreshSnapshotAsync()
    {
        if (_operationInProgress)
        {
            return;
        }
        ServerSnapshot snapshot = await _orchestrator.GetSnapshotAsync(CancellationToken.None);
        ApplySnapshot(snapshot);
    }

    private void ApplySnapshot(ServerSnapshot snapshot)
    {
        SetValue("state", GetStateLabel(snapshot.State));
        SetValue("detail", snapshot.Detail);
        SetValue("pid", snapshot.ProcessId?.ToString() ?? "-");
        string rconStatus = "未接続";
        if (snapshot.IsRconReady)
        {
            rconStatus = "接続可能";
        }
        SetValue("rcon", rconStatus);
        SetValue("firewall", GetFirewallLabel(snapshot.Firewall?.Readiness));
        SetValue("map", snapshot.CurrentMap ?? "-");
        SetValue("mods", snapshot.EnabledModCount.ToString());
        SetValue("uptime", GetUptime(snapshot.ProcessStartedAt));
        SetValue("lan", snapshot.Network?.LanIpv4 ?? "-");
        SetValue("hamachi", snapshot.Network?.HamachiIpv4 ?? "-");
        _lanCommand.Text = snapshot.Network?.LanConnectCommand ?? string.Empty;
        _hamachiCommand.Text = snapshot.Network?.HamachiConnectCommand ?? string.Empty;
        _progressText.Text = "現在の操作: 待機中";
        bool canStart = snapshot.State == ServerState.Stopped || snapshot.State == ServerState.Running;
        _start.Enabled = canStart;
        _stop.Enabled = snapshot.State == ServerState.Running;
        if (snapshot.State == ServerState.Unconfigured)
        {
            _lastError.Text = "基本設定を保存してください。";
        }
    }

    private void UpdateProgress(OperationProgress progress)
    {
        _progressText.Text = "現在の操作: " + progress.UserMessage;
        _progressBar.Style = ProgressBarStyle.Marquee;
        if (progress.Percent is not null)
        {
            _progressBar.Style = ProgressBarStyle.Blocks;
            _progressBar.Value = Math.Clamp(progress.Percent.Value, 0, 100);
        }
        ApplyBusyState();
    }

    private void ApplyBusyState()
    {
        _start.Enabled = false;
        _stop.Enabled = false;
    }

    private void ServerControlView_Disposed(object? sender, EventArgs eventArgs)
    {
        _timer.Stop();
        _timer.Dispose();
    }

    private void SetValue(string key, string value)
    {
        _values[key].Text = value;
    }

    private void AddStatus(TableLayoutPanel panel, int row, string labelText, string key, int column = 0)
    {
        Label label = new Label { AutoSize = true, Text = labelText, Margin = new Padding(3, 6, 6, 3) };
        Label value = new Label { AutoSize = true, Text = "-", Margin = new Padding(3, 6, 16, 3), MaximumSize = new Size(430, 0) };
        _values.Add(key, value);
        panel.Controls.Add(label, column, row);
        panel.Controls.Add(value, column + 1, row);
    }

    private void AddNetworkRow(TableLayoutPanel panel, string labelText, string? key, TextBox? textBox)
    {
        int row = panel.RowCount;
        panel.RowCount++;
        panel.Controls.Add(new Label { AutoSize = true, Text = labelText, Margin = new Padding(3, 7, 8, 3) }, 0, row);
        if (textBox is not null)
        {
            textBox.Dock = DockStyle.Fill;
            panel.Controls.Add(textBox, 1, row);
            return;
        }
        Label value = new Label { AutoSize = true, Text = "-", Margin = new Padding(3, 7, 3, 3) };
        if (key is not null)
        {
            _values.Add(key, value);
        }
        panel.Controls.Add(value, 1, row);
    }

    private static TextBox CreateReadOnlyTextBox()
    {
        return new TextBox { ReadOnly = true, BackColor = SystemColors.Window };
    }

    private static string GetStateLabel(ServerState state)
    {
        if (state == ServerState.Unconfigured) return "未構成";
        if (state == ServerState.Stopped) return "停止中";
        if (state == ServerState.Firewall) return "Firewall確認中";
        if (state == ServerState.Installing) return "SteamCMD確認中";
        if (state == ServerState.Updating) return "更新中";
        if (state == ServerState.Starting) return "起動中";
        if (state == ServerState.WaitingForRcon) return "サーバー準備待ち";
        if (state == ServerState.Running) return "稼働中";
        if (state == ServerState.Saving) return "ワールド保存中";
        if (state == ServerState.Stopping) return "停止処理中";
        return "エラー";
    }

    private static string GetFirewallLabel(FirewallReadiness? readiness)
    {
        if (readiness == FirewallReadiness.Ready) return "設定済み";
        if (readiness == FirewallReadiness.NeedsUpdate) return "要更新";
        if (readiness == FirewallReadiness.Unavailable) return "確認不可";
        if (readiness == FirewallReadiness.Error) return "エラー";
        return "未確認";
    }

    private static string GetUptime(DateTimeOffset? startedAt)
    {
        if (startedAt is null)
        {
            return "-";
        }
        TimeSpan elapsed = DateTimeOffset.Now - startedAt.Value.ToLocalTime();
        if (elapsed < TimeSpan.Zero)
        {
            return "-";
        }
        return $"{(int)elapsed.TotalDays}日 {elapsed.Hours:D2}:{elapsed.Minutes:D2}:{elapsed.Seconds:D2}";
    }
}
