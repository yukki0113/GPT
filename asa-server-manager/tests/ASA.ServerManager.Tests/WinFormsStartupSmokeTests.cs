using System.Runtime.ExceptionServices;
using ASA.ServerManager.Application;
using ASA.ServerManager.Domain;
using ASA.ServerManager.Infrastructure;
using ASA.ServerManager.WinForms;

namespace ASA.ServerManager.Tests;

public sealed class WinFormsStartupSmokeTests
{
    [Fact]
    public void MainFormAndPrimaryViews_ConstructAndDisposeAcrossStartupSizes()
    {
        RunOnStaThread(() =>
        {
            RuntimeFakes fakes = new RuntimeFakes();
            ApplicationStatusStore statusStore = new ApplicationStatusStore();
            ServerOrchestrator orchestrator = fakes.CreateOrchestrator();
            ManualBackupCoordinator backupCoordinator = new ManualBackupCoordinator(orchestrator, fakes.Settings, fakes.Secrets, fakes.Rcon, new UiBackupService(), new FakeDelay());

            BasicSettingsService basicSettingsService = new BasicSettingsService(fakes.Settings, fakes.Secrets, new UiMapRepository());
            ModSettingsService modSettingsService = new ModSettingsService(fakes.Settings);
            GameSettingsService gameSettingsService = CreateGameSettingsService(fakes.Settings);
            DiagnosticsService diagnosticsService = new DiagnosticsService(orchestrator, fakes.Settings, new StartupSmokeLogFileService(), statusStore, "test");

            using (ServerControlView serverControl = new ServerControlView(orchestrator, statusStore))
            {
                Button[] operationButtons = FindControls<Button>(serverControl).ToArray();
                Assert.Equal(2, operationButtons.Length);
                Assert.Equal(new[] { "起動／再起動", "停止" }, operationButtons.Select(button => button.Text));
                Assert.All(operationButtons, button =>
                {
                    Assert.InRange(button.Width, 150, 220);
                    Assert.InRange(button.Height, 40, 50);
                });
            }
            using (BasicSettingsView basicSettings = new BasicSettingsView(basicSettingsService, orchestrator, statusStore))
            {
                string[] texts = FindControls<Control>(basicSettings).Select(control => control.Text).ToArray();
                string[] expectedLabels =
                [
                    "MAP",
                    "MAP内部名",
                    "カスタムMAP MOD ID",
                    "ASAサーバーフォルダー",
                    "SteamCMDフォルダー",
                    "ゲームポート",
                    "Peerポート",
                    "Queryポート",
                    "RCONポート",
                    "RCONパスワード",
                    "サーバーパスワード",
                    "管理者パスワード",
                    "観戦者パスワード",
                    "追加起動引数",
                    "ポート設定",
                    "パスワード",
                    "高度な設定"
                ];
                Assert.All(expectedLabels, expected => Assert.Contains(expected, texts));
                Button saveButton = Assert.Single(FindControls<Button>(basicSettings).Where(button => button.Text == "設定を保存"));
                Assert.InRange(saveButton.Width, 140, 180);
                Assert.InRange(saveButton.Height, 40, 45);
            }
            using (ModsView mods = new ModsView(modSettingsService, statusStore)) { }
            using (GameSettingsView gameSettings = new GameSettingsView(gameSettingsService, statusStore)) { }
            using (DiagnosticsView diagnostics = new DiagnosticsView(diagnosticsService, backupCoordinator, statusStore)) { }

            using MainForm form = new MainForm(orchestrator, basicSettingsService, modSettingsService, gameSettingsService, diagnosticsService, backupCoordinator, statusStore);
            Assert.Equal(5, form.Controls.OfType<TabControl>().Single().TabPages.Count);
            foreach (Size clientSize in new[] { new Size(1100, 700), new Size(1375, 875), new Size(1650, 1050) })
            {
                form.ClientSize = clientSize;
                form.CreateControl();
                form.PerformLayout();
                Assert.True(form.Controls.OfType<TabControl>().Single().TabPages.Count == 5);
            }
        });
    }

    private static GameSettingsService CreateGameSettingsService(IServerSettingsRepository settingsRepository)
    {
        IGameSettingCatalogRepository catalogRepository = new JsonGameSettingCatalogRepository(Path.Combine(AppContext.BaseDirectory, "definitions", "game-settings.json"));
        IniDocumentService iniDocumentService = new IniDocumentService();
        IniConfigurationSaveService saveService = new IniConfigurationSaveService(iniDocumentService, new IniBackupService(Path.Combine(Path.GetTempPath(), "asa-startup-smoke")));
        return new GameSettingsService(catalogRepository, settingsRepository, iniDocumentService, saveService);
    }

    private static void RunOnStaThread(Action action)
    {
        Exception? failure = null;
        Thread thread = new Thread(() =>
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

    private sealed class StartupSmokeLogFileService : ILogFileService
    {
        public string GetLogDirectory()
        {
            return Path.GetTempPath();
        }

        public Task<OperationResult<LogTailSnapshot>> ReadTailAsync(int maximumLines, CancellationToken cancellationToken)
        {
            return Task.FromResult(OperationResult<LogTailSnapshot>.Success(new LogTailSnapshot()));
        }
    }
}
