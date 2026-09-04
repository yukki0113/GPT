using ASA.ServerManager.Application;

namespace ASA.ServerManager.WinForms;

/// <summary>フォルダー選択要求です。初期パスは存在確認後にのみダイアログへ渡されます。</summary>
public sealed record FolderPickRequest(string Title, string? InitialDirectory);

/// <summary>フォルダー選択の終了状態です。</summary>
public enum FolderPickStatus
{
    Accepted,
    Cancelled,
    Failed
}

/// <summary>フォルダー選択結果です。</summary>
public sealed record FolderPickResult(FolderPickStatus Status, string? SelectedPath = null, string? UserMessage = null)
{
    /// <summary>選択確定結果を作成します。</summary>
    public static FolderPickResult Accepted(string selectedPath) => new(FolderPickStatus.Accepted, selectedPath);

    /// <summary>利用者によるキャンセル結果を作成します。</summary>
    public static FolderPickResult Cancelled() => new(FolderPickStatus.Cancelled);

    /// <summary>安全に表示できる失敗結果を作成します。</summary>
    public static FolderPickResult Failed(string userMessage) => new(FolderPickStatus.Failed, UserMessage: userMessage);
}

/// <summary>ViewからWindows Shell Folder Pickerを分離します。</summary>
public interface IFolderPickerService
{
    /// <summary>呼び出し元を同期ブロックせず、フォルダーを選択します。</summary>
    Task<FolderPickResult> PickFolderAsync(FolderPickRequest request, CancellationToken cancellationToken);
}

/// <summary>実ダイアログをテスト用Fakeへ差し替える境界です。</summary>
public interface IFolderPickerDialogAdapter
{
    /// <summary>STA thread上でダイアログを表示します。</summary>
    FolderPickResult Show(FolderPickRequest request);
}

/// <summary>専用のbackground STA threadでFolderBrowserDialogを実行します。</summary>
public sealed class WindowsFolderPickerService : IFolderPickerService
{
    private const string FailureMessage = "フォルダー選択画面を開けませんでした。パスを直接入力して続行できます。";
    private readonly IFolderPickerDialogAdapter _dialogAdapter;
    private readonly IAppLogger _logger;

    /// <summary>本番用FolderBrowserDialog adapterを使用します。</summary>
    public WindowsFolderPickerService(IAppLogger logger)
        : this(new WinFormsFolderPickerDialogAdapter(), logger)
    {
    }

    /// <summary>テスト可能なdialog adapterを指定します。</summary>
    public WindowsFolderPickerService(IFolderPickerDialogAdapter dialogAdapter, IAppLogger logger)
    {
        _dialogAdapter = dialogAdapter;
        _logger = logger;
    }

    /// <inheritdoc />
    public Task<FolderPickResult> PickFolderAsync(FolderPickRequest request, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(request);
        _logger.Info("Folder picker requested");
        if (cancellationToken.IsCancellationRequested)
        {
            _logger.Info("Folder picker cancelled");
            return Task.FromResult(FolderPickResult.Cancelled());
        }

        TaskCompletionSource<FolderPickResult> completion = new(TaskCreationOptions.RunContinuationsAsynchronously);
        try
        {
            Thread pickerThread = new Thread(() => RunPicker(request, cancellationToken, completion))
            {
                IsBackground = true,
                Name = "ASA Folder Picker"
            };
            pickerThread.SetApartmentState(ApartmentState.STA);
            pickerThread.Start();
        }
        catch (Exception exception)
        {
            _logger.Error(exception, "Folder picker failed");
            completion.TrySetResult(FolderPickResult.Failed(FailureMessage));
        }
        return completion.Task;
    }

    private void RunPicker(FolderPickRequest request, CancellationToken cancellationToken, TaskCompletionSource<FolderPickResult> completion)
    {
        try
        {
            if (cancellationToken.IsCancellationRequested)
            {
                _logger.Info("Folder picker cancelled");
                completion.TrySetResult(FolderPickResult.Cancelled());
                return;
            }

            string? initialDirectory = GetExistingDirectory(request.InitialDirectory);
            FolderPickRequest safeRequest = request with { InitialDirectory = initialDirectory };
            _logger.Info("Folder picker shown");
            FolderPickResult result = _dialogAdapter.Show(safeRequest);
            if (result.Status == FolderPickStatus.Accepted)
            {
                _logger.Info("Folder picker accepted");
            }
            else if (result.Status == FolderPickStatus.Cancelled)
            {
                _logger.Info("Folder picker cancelled");
            }
            else
            {
                _logger.Warn("Folder picker failed");
            }
            completion.TrySetResult(result);
        }
        catch (Exception exception)
        {
            _logger.Error(exception, "Folder picker failed");
            completion.TrySetResult(FolderPickResult.Failed(FailureMessage));
        }
    }

    private static string? GetExistingDirectory(string? candidate)
    {
        if (string.IsNullOrWhiteSpace(candidate))
        {
            return null;
        }
        try
        {
            return Directory.Exists(candidate) ? candidate : null;
        }
        catch (Exception)
        {
            return null;
        }
    }
}

/// <summary>.NET 8 WinForms標準FolderBrowserDialog adapterです。</summary>
public sealed class WinFormsFolderPickerDialogAdapter : IFolderPickerDialogAdapter
{
    /// <inheritdoc />
    public FolderPickResult Show(FolderPickRequest request)
    {
        using FolderBrowserDialog dialog = new()
        {
            Description = request.Title,
            ShowNewFolderButton = true,
            UseDescriptionForTitle = true
        };
        if (!string.IsNullOrWhiteSpace(request.InitialDirectory))
        {
            dialog.SelectedPath = request.InitialDirectory;
        }

        // ownerを別threadのControlにしない。ownerなしで表示し、MainFormの操作と終了を妨げない。
        return dialog.ShowDialog() == DialogResult.OK
            ? FolderPickResult.Accepted(dialog.SelectedPath)
            : FolderPickResult.Cancelled();
    }
}
