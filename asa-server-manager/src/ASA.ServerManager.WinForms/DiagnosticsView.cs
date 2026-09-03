using System.Diagnostics;
using System.Text;
using ASA.ServerManager.Application;
using ASA.ServerManager.Domain;

namespace ASA.ServerManager.WinForms;

/// <summary>診断Summary、最新ログ末尾、手動Savedバックアップを提供します。</summary>
public sealed class DiagnosticsView : UserControl
{
    private readonly DiagnosticsService _diagnosticsService;
    private readonly ManualBackupCoordinator _backupCoordinator;
    private readonly IApplicationStatusStore _statusStore;
    private readonly TextBox _summary = new TextBox();
    private readonly TextBox _logPath = new TextBox();
    private readonly TextBox _logTail = new TextBox();
    private readonly Button _refresh = new Button();
    private readonly Button _openLogFolder = new Button();
    private readonly Button _backup = new Button();
    private readonly Label _backupStatus = new Label();
    private bool _operationInProgress;

    /// <summary>診断およびバックアップのApplication serviceを受け取ります。</summary>
    public DiagnosticsView(DiagnosticsService diagnosticsService, ManualBackupCoordinator backupCoordinator, IApplicationStatusStore statusStore)
    {
        _diagnosticsService = diagnosticsService;
        _backupCoordinator = backupCoordinator;
        _statusStore = statusStore;
        AutoScaleMode = AutoScaleMode.Dpi;
        BuildLayout();
        Load += DiagnosticsView_Load;
    }

    private void BuildLayout()
    {
        TableLayoutPanel root = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 2, Padding = new Padding(10) };
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 72));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 28));

        GroupBox logGroup = new GroupBox { Dock = DockStyle.Fill, Text = "ログ・診断", Padding = new Padding(8) };
        TableLayoutPanel logLayout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 4 };
        logLayout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        logLayout.RowStyles.Add(new RowStyle(SizeType.Absolute, 126));
        logLayout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        logLayout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        FlowLayoutPanel commands = new FlowLayoutPanel { AutoSize = true, Dock = DockStyle.Fill };
        ConfigureButton(_refresh, "更新", Refresh_Click);
        ConfigureButton(_openLogFolder, "Log folderを開く", OpenLogFolder_Click);
        commands.Controls.AddRange([_refresh, _openLogFolder]);
        _summary.Dock = DockStyle.Fill;
        _summary.Multiline = true;
        _summary.ReadOnly = true;
        _summary.BackColor = SystemColors.Window;
        _summary.ScrollBars = ScrollBars.Vertical;
        _logPath.Dock = DockStyle.Fill;
        _logPath.ReadOnly = true;
        _logPath.BackColor = SystemColors.Window;
        _logTail.Dock = DockStyle.Fill;
        _logTail.Multiline = true;
        _logTail.ReadOnly = true;
        _logTail.BackColor = SystemColors.Window;
        _logTail.ScrollBars = ScrollBars.Both;
        _logTail.WordWrap = false;
        logLayout.Controls.Add(commands, 0, 0);
        logLayout.Controls.Add(_summary, 0, 1);
        logLayout.Controls.Add(_logPath, 0, 2);
        logLayout.Controls.Add(_logTail, 0, 3);
        logGroup.Controls.Add(logLayout);

        GroupBox backupGroup = new GroupBox { Dock = DockStyle.Fill, Text = "バックアップ", Padding = new Padding(8) };
        FlowLayoutPanel backupLayout = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.TopDown, WrapContents = false };
        ConfigureButton(_backup, "Savedバックアップを作成", Backup_Click);
        _backup.AutoSize = true;
        _backupStatus.AutoSize = true;
        _backupStatus.MaximumSize = new Size(1000, 0);
        _backupStatus.Text = "停止中は直接、稼働中はSaveWorld後にライブバックアップします。";
        backupLayout.Controls.Add(_backup);
        backupLayout.Controls.Add(_backupStatus);
        backupGroup.Controls.Add(backupLayout);

        root.Controls.Add(logGroup, 0, 0);
        root.Controls.Add(backupGroup, 0, 1);
        Controls.Add(root);
    }

    private async void DiagnosticsView_Load(object? sender, EventArgs eventArgs)
    {
        await RefreshAsync();
    }

    private async void Refresh_Click(object? sender, EventArgs eventArgs)
    {
        await RefreshAsync();
    }

    private void OpenLogFolder_Click(object? sender, EventArgs eventArgs)
    {
        try
        {
            string directory = _diagnosticsService.GetLogDirectory();
            Directory.CreateDirectory(directory);
            Process.Start(new ProcessStartInfo { FileName = directory, UseShellExecute = true });
        }
        catch (Exception exception)
        {
            OperationResult result = OperationResult.Failure("Log folderを開けません。", errorCode: "LOG_FOLDER_OPEN_FAILED", technicalMessage: exception.Message);
            ShowFailure(result);
        }
    }

    private async void Backup_Click(object? sender, EventArgs eventArgs)
    {
        if (_operationInProgress)
        {
            return;
        }
        if (MessageBox.Show(this, "Savedバックアップを作成しますか？\n稼働中はSaveWorld後に約15秒待機します。", "ASA Server Manager", MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes)
        {
            return;
        }
        _operationInProgress = true;
        SetButtons(false);
        try
        {
            Progress<OperationProgress> progress = new Progress<OperationProgress>(item => _backupStatus.Text = item.UserMessage);
            OperationResult<ManualBackupResult> result = await _backupCoordinator.CreateAsync(progress, CancellationToken.None);
            if (!result.Succeeded || result.Value is null)
            {
                ShowFailure(result);
                _backupStatus.Text = result.ErrorMessage ?? "バックアップに失敗しました。";
                return;
            }
            BackupInfo backup = result.Value.Backup;
            StringBuilder message = new StringBuilder();
            message.AppendLine("Savedバックアップを作成しました。");
            message.AppendLine($"保存先: {backup.Path}");
            message.AppendLine($"ファイル数: {backup.FileCount:N0}");
            message.AppendLine($"合計サイズ: {FormatBytes(backup.TotalBytes)}");
            if (!string.IsNullOrWhiteSpace(result.Value.Warning))
            {
                message.AppendLine($"注意: {result.Value.Warning}");
            }
            _backupStatus.Text = message.ToString();
            MessageBox.Show(this, message.ToString(), "ASA Server Manager", MessageBoxButtons.OK, MessageBoxIcon.Information);
        }
        finally
        {
            _operationInProgress = false;
            await RefreshAsync();
        }
    }

    private async Task RefreshAsync()
    {
        SetButtons(false);
        OperationResult<DiagnosticsSnapshot> result = await _diagnosticsService.LoadAsync(1000, CancellationToken.None);
        if (!result.Succeeded || result.Value is null)
        {
            ShowFailure(result);
            _summary.Text = result.ErrorMessage ?? "診断情報を読み込めません。";
            SetButtons(true);
            return;
        }
        DiagnosticsSnapshot snapshot = result.Value;
        _summary.Text = BuildSummary(snapshot);
        _logPath.Text = "現在Log: " + (snapshot.CurrentLogPath ?? "-");
        _logTail.Lines = snapshot.LogLines.ToArray();
        bool backupEnabled = snapshot.ServerState == ServerState.Running || snapshot.ServerState == ServerState.Stopped;
        _refresh.Enabled = !_operationInProgress;
        _openLogFolder.Enabled = !_operationInProgress;
        _backup.Enabled = !_operationInProgress && backupEnabled;
        if (!backupEnabled && !_operationInProgress)
        {
            _backupStatus.Text = "サーバー操作中または未構成のため、バックアップを実行できません。";
        }
    }

    private void SetButtons(bool enabled)
    {
        _refresh.Enabled = enabled;
        _openLogFolder.Enabled = enabled;
        _backup.Enabled = enabled;
    }

    private void ShowFailure(OperationResult result)
    {
        _statusStore.Record(result);
        MessageBox.Show(this, result.UserMessage ?? result.ErrorMessage ?? "操作に失敗しました。", "ASA Server Manager", MessageBoxButtons.OK, MessageBoxIcon.Error);
    }

    private static string BuildSummary(DiagnosticsSnapshot snapshot)
    {
        StringBuilder builder = new StringBuilder();
        builder.AppendLine($"App version: {snapshot.AppVersion}");
        builder.AppendLine($"Server state: {GetStateLabel(snapshot.ServerState)}");
        builder.AppendLine($"Server path: {ValueOrDash(snapshot.ServerPath)}");
        builder.AppendLine($"SteamCMD path: {ValueOrDash(snapshot.SteamCmdPath)}");
        builder.AppendLine($"Firewall: {snapshot.Firewall?.ToString() ?? "-"}");
        builder.AppendLine($"LAN IP: {ValueOrDash(snapshot.LanIpv4)}");
        builder.AppendLine($"Hamachi IP: {ValueOrDash(snapshot.HamachiIpv4)}");
        builder.AppendLine($"Last ErrorCode: {ValueOrDash(snapshot.LastErrorCode)}");
        return builder.ToString();
    }

    private static string GetStateLabel(ServerState state)
    {
        if (state == ServerState.Running)
        {
            return "稼働中";
        }
        if (state == ServerState.Stopped)
        {
            return "停止中";
        }
        if (state == ServerState.Unconfigured)
        {
            return "未構成";
        }
        if (state == ServerState.Error)
        {
            return "エラー";
        }
        return "操作中: " + state;
    }

    private static string ValueOrDash(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "-";
        }
        return value;
    }

    private static string FormatBytes(long bytes)
    {
        if (bytes >= 1024L * 1024L * 1024L)
        {
            return $"{bytes / (1024d * 1024d * 1024d):N2} GB";
        }
        if (bytes >= 1024L * 1024L)
        {
            return $"{bytes / (1024d * 1024d):N2} MB";
        }
        if (bytes >= 1024L)
        {
            return $"{bytes / 1024d:N2} KB";
        }
        return $"{bytes:N0} bytes";
    }

    private static void ConfigureButton(Button button, string text, EventHandler handler)
    {
        button.AutoSize = true;
        button.Text = text;
        button.Click += handler;
    }
}
