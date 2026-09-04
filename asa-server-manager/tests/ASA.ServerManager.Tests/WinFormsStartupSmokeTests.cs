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

            using (ServerControlView serverControl = new ServerControlView(orchestrator, statusStore)) { }
            using (BasicSettingsView basicSettings = new BasicSettingsView(basicSettingsService, orchestrator, statusStore)) { }
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
