using ASA.ServerManager.Application;
using ASA.ServerManager.Domain;

namespace ASA.ServerManager.WinForms;

/// <summary>サーバー状態と、起動／再起動・停止の2操作だけを表示します。</summary>
public sealed class ServerControlView : UserControl
{
    private readonly ServerOrchestrator? _orchestrator;
    private readonly Label _status;
    private readonly Label _detail;
    private readonly Button _start;
    private readonly Button _stop;
    private readonly System.Windows.Forms.Timer _timer;
    private bool _operationInProgress;

    /// <summary>操作画面を構築します。</summary>
    public ServerControlView(ServerOrchestrator? orchestrator = null)
    {
        _orchestrator = orchestrator;
        _status = new Label();
        _status.AutoSize = true;
        _status.Location = new Point(24, 24);
        _status.Text = "状態: 確認中";

        _detail = new Label();
        _detail.AutoSize = true;
        _detail.Location = new Point(24, 48);
        _detail.Text = "状態を取得しています。";

        _start = new Button();
        _start.Location = new Point(24, 84);
        _start.Size = new Size(140, 32);
        _start.Text = "起動／再起動";
        _start.Click += StartButton_Click;

        _stop = new Button();
        _stop.Location = new Point(176, 84);
        _stop.Size = new Size(100, 32);
        _stop.Text = "停止";
        _stop.Click += StopButton_Click;

        Controls.Add(_status);
        Controls.Add(_detail);
        Controls.Add(_start);
        Controls.Add(_stop);

        _timer = new System.Windows.Forms.Timer { Interval = 2000 };
        _timer.Tick += RefreshTimer_Tick;
        Load += ServerControlView_Load;
        Disposed += ServerControlView_Disposed;
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
        if (_orchestrator is null || _operationInProgress)
        {
            return;
        }
        ServerSnapshot snapshot = await _orchestrator.GetSnapshotAsync(CancellationToken.None);
        if (snapshot.State == ServerState.Running && MessageBox.Show(this, "サーバーを再起動しますか？", "ASA Server Manager", MessageBoxButtons.YesNo, MessageBoxIcon.Warning) != DialogResult.Yes)
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
        if (_orchestrator is null || _operationInProgress)
        {
            return;
        }
        if (MessageBox.Show(this, "サーバーを安全に停止しますか？", "ASA Server Manager", MessageBoxButtons.YesNo, MessageBoxIcon.Warning) != DialogResult.Yes)
        {
            return;
        }
        await ExecuteOperationAsync(_orchestrator.StopAsync);
    }

    private async Task ExecuteOperationAsync(Func<IProgress<OperationProgress>?, CancellationToken, Task<OperationResult>> operation)
    {
        _operationInProgress = true;
        try
        {
            Progress<OperationProgress> progress = new Progress<OperationProgress>(UpdateProgress);
            OperationResult result = await operation(progress, CancellationToken.None);
            if (!result.Succeeded)
            {
                MessageBox.Show(this, result.UserMessage ?? result.ErrorMessage ?? "サーバー操作に失敗しました。", "ASA Server Manager", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }
        finally
        {
            _operationInProgress = false;
            await RefreshSnapshotAsync();
        }
    }

    private async Task RefreshSnapshotAsync()
    {
        if (_orchestrator is null || _operationInProgress)
        {
            ApplySnapshot(new ServerSnapshot { State = ServerState.Unconfigured, Detail = "実行環境を構成していません。" });
            return;
        }
        ServerSnapshot snapshot = await _orchestrator.GetSnapshotAsync(CancellationToken.None);
        ApplySnapshot(snapshot);
    }

    private void ApplySnapshot(ServerSnapshot snapshot)
    {
        _status.Text = $"状態: {GetStateLabel(snapshot.State)}";
        _detail.Text = snapshot.Detail;
        if (snapshot.ProcessId is not null)
        {
            _detail.Text = $"{snapshot.Detail} PID: {snapshot.ProcessId}";
        }
        bool canStart = snapshot.State == ServerState.Stopped || snapshot.State == ServerState.Running;
        _start.Enabled = !_operationInProgress && canStart;
        _stop.Enabled = !_operationInProgress && snapshot.State == ServerState.Running;
    }

    private void UpdateProgress(OperationProgress progress)
    {
        _status.Text = $"状態: {progress.StepCode}";
        _detail.Text = progress.UserMessage;
        _start.Enabled = false;
        _stop.Enabled = false;
    }

    private void ServerControlView_Disposed(object? sender, EventArgs eventArgs)
    {
        _timer.Stop();
        _timer.Dispose();
    }

    private static string GetStateLabel(ServerState state)
    {
        return state switch
        {
            ServerState.Unconfigured => "未構成",
            ServerState.Stopped => "停止中",
            ServerState.Installing => "SteamCMD導入中",
            ServerState.Updating => "更新中",
            ServerState.Starting => "起動中",
            ServerState.WaitingForRcon => "RCON待機中",
            ServerState.Running => "稼働中",
            ServerState.Saving => "保存中",
            ServerState.Stopping => "停止中",
            _ => "エラー"
        };
    }
}
