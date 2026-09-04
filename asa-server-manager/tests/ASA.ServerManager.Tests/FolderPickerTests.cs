using System.Diagnostics;
using System.Runtime.ExceptionServices;
using ASA.ServerManager.Application;
using ASA.ServerManager.WinForms;

namespace ASA.ServerManager.Tests;

public sealed class WindowsFolderPickerServiceTests
{
    [Fact]
    public async Task PickFolderAsync_RunsAdapterOnBackgroundStaThreadWithoutBlockingCaller()
    {
        using ManualResetEventSlim entered = new(false);
        using ManualResetEventSlim release = new(false);
        RecordingDialogAdapter adapter = new(request =>
        {
            entered.Set();
            release.Wait(TimeSpan.FromSeconds(10));
            return FolderPickResult.Cancelled();
        });
        WindowsFolderPickerService service = new(adapter, new FakeLogger());

        Stopwatch stopwatch = Stopwatch.StartNew();
        Task<FolderPickResult> operation = service.PickFolderAsync(new FolderPickRequest("選択", null), CancellationToken.None);
        stopwatch.Stop();

        Assert.True(stopwatch.Elapsed < TimeSpan.FromSeconds(1));
        Assert.True(entered.Wait(TimeSpan.FromSeconds(10)));
        Assert.False(operation.IsCompleted);
        Assert.Equal(ApartmentState.STA, adapter.ApartmentState);
        Assert.True(adapter.IsBackgroundThread);
        release.Set();
        FolderPickResult result = await operation;
        Assert.Equal(FolderPickStatus.Cancelled, result.Status);
    }

    [Fact]
    public async Task PickFolderAsync_InvalidInitialDirectoryIsNotPassedToDialog()
    {
        RecordingDialogAdapter adapter = new(_ => FolderPickResult.Cancelled());
        WindowsFolderPickerService service = new(adapter, new FakeLogger());
        string missingPath = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString("N"));

        FolderPickResult result = await service.PickFolderAsync(new FolderPickRequest("選択", missingPath), CancellationToken.None);

        Assert.Equal(FolderPickStatus.Cancelled, result.Status);
        Assert.Null(adapter.Request?.InitialDirectory);
    }

    [Fact]
    public async Task PickFolderAsync_ExistingInitialDirectoryIsPassedToDialog()
    {
        RecordingDialogAdapter adapter = new(_ => FolderPickResult.Cancelled());
        WindowsFolderPickerService service = new(adapter, new FakeLogger());
        string existingPath = Path.GetTempPath();

        await service.PickFolderAsync(new FolderPickRequest("選択", existingPath), CancellationToken.None);

        Assert.Equal(existingPath, adapter.Request?.InitialDirectory);
    }

    [Fact]
    public async Task PickFolderAsync_CancelIsNormalResult()
    {
        WindowsFolderPickerService service = new(new RecordingDialogAdapter(_ => FolderPickResult.Cancelled()), new FakeLogger());

        FolderPickResult result = await service.PickFolderAsync(new FolderPickRequest("選択", null), CancellationToken.None);

        Assert.Equal(FolderPickStatus.Cancelled, result.Status);
        Assert.Null(result.UserMessage);
    }

    [Fact]
    public async Task PickFolderAsync_AdapterExceptionBecomesSafeFailure()
    {
        WindowsFolderPickerService service = new(new RecordingDialogAdapter(_ => throw new InvalidOperationException("shell detail")), new FakeLogger());

        FolderPickResult result = await service.PickFolderAsync(new FolderPickRequest("選択", null), CancellationToken.None);

        Assert.Equal(FolderPickStatus.Failed, result.Status);
        Assert.Contains("パスを直接入力", result.UserMessage);
        Assert.DoesNotContain("shell detail", result.UserMessage);
    }

    private sealed class RecordingDialogAdapter : IFolderPickerDialogAdapter
    {
        private readonly Func<FolderPickRequest, FolderPickResult> _show;

        internal RecordingDialogAdapter(Func<FolderPickRequest, FolderPickResult> show)
        {
            _show = show;
        }

        internal ApartmentState ApartmentState { get; private set; }
        internal bool IsBackgroundThread { get; private set; }
        internal FolderPickRequest? Request { get; private set; }

        public FolderPickResult Show(FolderPickRequest request)
        {
            Request = request;
            ApartmentState = Thread.CurrentThread.GetApartmentState();
            IsBackgroundThread = Thread.CurrentThread.IsBackground;
            return _show(request);
        }
    }
}

public sealed class BasicSettingsFolderPickerTests
{
    [Fact]
    public void AsaBrowseAccepted_UpdatesOnlyAsaPath()
    {
        RunOnStaThread(() =>
        {
            ImmediateFolderPicker picker = new(FolderPickResult.Accepted("C:\\ChosenASA"));
            using BasicSettingsView view = CreateView(picker);
            TextBox asaPath = FindControl<TextBox>(view, "ServerPathTextBox");
            TextBox steamPath = FindControl<TextBox>(view, "SteamCmdPathTextBox");
            asaPath.Text = "C:\\OldASA";
            steamPath.Text = "C:\\OldSteam";

            view.BrowseServerPathAsync().GetAwaiter().GetResult();

            Assert.Equal("C:\\ChosenASA", asaPath.Text);
            Assert.Equal("C:\\OldSteam", steamPath.Text);
        });
    }

    [Fact]
    public void AsaBrowseCancelled_PreservesExistingPath()
    {
        RunOnStaThread(() =>
        {
            using BasicSettingsView view = CreateView(new ImmediateFolderPicker(FolderPickResult.Cancelled()));
            TextBox path = FindControl<TextBox>(view, "ServerPathTextBox");
            path.Text = "C:\\ExistingASA";

            view.BrowseServerPathAsync().GetAwaiter().GetResult();

            Assert.Equal("C:\\ExistingASA", path.Text);
        });
    }

    [Fact]
    public void SteamCmdBrowseAccepted_UpdatesOnlySteamCmdPath()
    {
        RunOnStaThread(() =>
        {
            ImmediateFolderPicker picker = new(FolderPickResult.Accepted("C:\\ChosenSteam"));
            using BasicSettingsView view = CreateView(picker);
            TextBox asaPath = FindControl<TextBox>(view, "ServerPathTextBox");
            TextBox steamPath = FindControl<TextBox>(view, "SteamCmdPathTextBox");
            asaPath.Text = "C:\\OldASA";
            steamPath.Text = "C:\\OldSteam";

            view.BrowseSteamCmdPathAsync().GetAwaiter().GetResult();

            Assert.Equal("C:\\OldASA", asaPath.Text);
            Assert.Equal("C:\\ChosenSteam", steamPath.Text);
        });
    }

    [Fact]
    public void SteamCmdBrowseCancelled_PreservesExistingPath()
    {
        RunOnStaThread(() =>
        {
            using BasicSettingsView view = CreateView(new ImmediateFolderPicker(FolderPickResult.Cancelled()));
            TextBox path = FindControl<TextBox>(view, "SteamCmdPathTextBox");
            path.Text = "C:\\ExistingSteam";

            view.BrowseSteamCmdPathAsync().GetAwaiter().GetResult();

            Assert.Equal("C:\\ExistingSteam", path.Text);
        });
    }

    [Fact]
    public void PickerFailure_PreservesPathAndDoesNotEscapeToMainUi()
    {
        RunOnStaThread(() =>
        {
            using BasicSettingsView view = CreateView(new ImmediateFolderPicker(FolderPickResult.Failed("フォルダー選択画面を開けませんでした。パスを直接入力して続行できます。")));
            TextBox path = FindControl<TextBox>(view, "ServerPathTextBox");
            path.Text = "C:\\ManualPath";

            Exception? exception = Record.Exception(() => view.BrowseServerPathAsync().GetAwaiter().GetResult());

            Assert.Null(exception);
            Assert.Equal("C:\\ManualPath", path.Text);
            Assert.Contains(FindControls<Label>(view), label => label.Text.Contains("パスを直接入力", StringComparison.Ordinal));
        });
    }

    [Fact]
    public void PickerInProgress_DisablesBothButtonsAndPreventsMultipleLaunches()
    {
        RunOnStaThread(() =>
        {
            PendingFolderPicker picker = new();
            using BasicSettingsView view = CreateView(picker);
            Button asaButton = FindControl<Button>(view, "ServerPathBrowseButton");
            Button steamButton = FindControl<Button>(view, "SteamCmdPathBrowseButton");

            Task first = view.BrowseServerPathAsync();
            Task second = view.BrowseSteamCmdPathAsync();

            Assert.False(asaButton.Enabled);
            Assert.False(steamButton.Enabled);
            Assert.Equal(1, picker.CallCount);
            Assert.True(second.IsCompleted);
            picker.Complete(FolderPickResult.Cancelled());
            first.GetAwaiter().GetResult();
            Assert.True(asaButton.Enabled);
            Assert.True(steamButton.Enabled);
        });
    }

    [Fact]
    public void DelayedResultAfterViewDispose_IsIgnoredWithoutException()
    {
        RunOnStaThread(() =>
        {
            PendingFolderPicker picker = new();
            BasicSettingsView view = CreateView(picker);
            Task operation = view.BrowseServerPathAsync();
            view.Dispose();

            picker.Complete(FolderPickResult.Accepted("C:\\TooLate"));
            Exception? exception = Record.Exception(() => operation.GetAwaiter().GetResult());

            Assert.Null(exception);
        });
    }

    private static BasicSettingsView CreateView(IFolderPickerService picker)
    {
        RuntimeFakes fakes = new();
        ServerOrchestrator orchestrator = fakes.CreateOrchestrator();
        BasicSettingsService service = new(fakes.Settings, fakes.Secrets, new UiMapRepository());
        return new BasicSettingsView(service, orchestrator, new ApplicationStatusStore(), picker);
    }

    private static TControl FindControl<TControl>(Control root, string name) where TControl : Control
    {
        return Assert.Single(FindControls<TControl>(root).Where(control => control.Name == name));
    }

    private static IEnumerable<TControl> FindControls<TControl>(Control root) where TControl : Control
    {
        foreach (Control child in root.Controls)
        {
            if (child is TControl match)
            {
                yield return match;
            }
            foreach (TControl descendant in FindControls<TControl>(child))
            {
                yield return descendant;
            }
        }
    }

    private static void RunOnStaThread(Action action)
    {
        Exception? failure = null;
        Thread thread = new(() =>
        {
            try
            {
                action();
            }
            catch (Exception exception)
            {
                failure = exception;
            }
        });
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        thread.Join();
        if (failure is not null)
        {
            ExceptionDispatchInfo.Capture(failure).Throw();
        }
    }

    private sealed class ImmediateFolderPicker : IFolderPickerService
    {
        private readonly FolderPickResult _result;

        internal ImmediateFolderPicker(FolderPickResult result)
        {
            _result = result;
        }

        public Task<FolderPickResult> PickFolderAsync(FolderPickRequest request, CancellationToken cancellationToken)
        {
            return Task.FromResult(_result);
        }
    }

    private sealed class PendingFolderPicker : IFolderPickerService
    {
        private readonly TaskCompletionSource<FolderPickResult> _completion = new();

        internal int CallCount { get; private set; }

        public Task<FolderPickResult> PickFolderAsync(FolderPickRequest request, CancellationToken cancellationToken)
        {
            CallCount++;
            return _completion.Task;
        }

        internal void Complete(FolderPickResult result)
        {
            _completion.SetResult(result);
        }
    }
}
