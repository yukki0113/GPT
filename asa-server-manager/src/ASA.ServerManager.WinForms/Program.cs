using ASA.ServerManager.Application;
using ASA.ServerManager.Domain;
using ASA.ServerManager.Infrastructure;
using System.Reflection;

namespace ASA.ServerManager.WinForms;

internal static class Program
{
    /// <summary>
    ///  The main entry point for the application.
    /// </summary>
    [STAThread]
    static async Task Main(string[] args)
    {
        if (IsFirewallHelperRequest(args))
        {
            await RunFirewallHelperAsync(args[2]);
            return;
        }
        // To customize application configuration such as set high DPI settings or default font,
        // see https://aka.ms/applicationconfiguration.
        ApplicationConfiguration.Initialize();
        ApplicationComposition composition = CreateComposition();
        System.Windows.Forms.Application.Run(new MainForm(
            composition.ServerOrchestrator,
            composition.BasicSettingsService,
            composition.ModSettingsService,
            composition.GameSettingsService,
            composition.DiagnosticsService,
            composition.BackupCoordinator,
            composition.StatusStore));
    }

    private static ApplicationComposition CreateComposition()
    {
        string baseDirectory = AppContext.BaseDirectory;
        string logDirectory = Path.Combine(baseDirectory, "logs");
        FileAppLogger logger = new FileAppLogger(logDirectory);
        JsonServerSettingsRepository settingsRepository = new JsonServerSettingsRepository(Path.Combine(baseDirectory, "config", "server-settings.json"));
        DpapiSecretRepository secretRepository = new DpapiSecretRepository(Path.Combine(baseDirectory, "secrets", "secrets.dat"));
        JsonGameSettingCatalogRepository catalogRepository = new JsonGameSettingCatalogRepository(Path.Combine(baseDirectory, "definitions", "game-settings.json"));
        JsonMapDefinitionRepository mapRepository = new JsonMapDefinitionRepository(Path.Combine(baseDirectory, "definitions", "maps.json"));
        string backupDirectory = Path.Combine(baseDirectory, "backups");
        IniBackupService iniBackupService = new IniBackupService(backupDirectory);
        IniDocumentService iniDocumentService = new IniDocumentService();
        IniConfigurationSaveService saveService = new IniConfigurationSaveService(iniDocumentService, iniBackupService);
        IniEnabledSettingsSaver saver = new IniEnabledSettingsSaver(catalogRepository, saveService);
        HttpClient httpClient = new HttpClient();
        WindowsFirewallService firewallService = new WindowsFirewallService(logger, Path.Combine(baseDirectory, "elevation"));
        FirewallElevationLauncher elevationLauncher = new FirewallElevationLauncher(System.Windows.Forms.Application.ExecutablePath, Path.Combine(baseDirectory, "elevation"), logger);
        NetworkInfoService networkInfoService = new NetworkInfoService(logger);
        RconClient rconClient = new RconClient();
        SystemOperationDelay delay = new SystemOperationDelay();
        ServerOrchestrator serverOrchestrator = new ServerOrchestrator(
            settingsRepository,
            secretRepository,
            new SteamCmdService(httpClient, logger),
            new AsaProcessService(logger),
            rconClient,
            saver,
            new ServerArgumentBuilder(),
            new ServerStateResolver(),
            delay,
            logger,
            firewallService,
            elevationLauncher,
            networkInfoService,
            new FirewallRequirementsBuilder());
        ApplicationStatusStore statusStore = new ApplicationStatusStore();
        SavedBackupService savedBackupService = new SavedBackupService(backupDirectory, logger);
        ManualBackupCoordinator backupCoordinator = new ManualBackupCoordinator(serverOrchestrator, settingsRepository, secretRepository, rconClient, savedBackupService, delay);
        FileLogService logFileService = new FileLogService(logDirectory);
        string appVersion = Assembly.GetExecutingAssembly().GetName().Version?.ToString() ?? "3.0.0";
        return new ApplicationComposition
        {
            ServerOrchestrator = serverOrchestrator,
            BasicSettingsService = new BasicSettingsService(settingsRepository, secretRepository, mapRepository),
            ModSettingsService = new ModSettingsService(settingsRepository),
            GameSettingsService = new GameSettingsService(catalogRepository, settingsRepository, iniDocumentService, saveService),
            DiagnosticsService = new DiagnosticsService(serverOrchestrator, settingsRepository, logFileService, statusStore, appVersion),
            BackupCoordinator = backupCoordinator,
            StatusStore = statusStore
        };
    }

    private static bool IsFirewallHelperRequest(IReadOnlyList<string> args)
    {
        return args.Count == 3 && string.Equals(args[0], "--elevated", StringComparison.Ordinal) && string.Equals(args[1], "firewall-ensure", StringComparison.Ordinal);
    }

    private static async Task RunFirewallHelperAsync(string requestPath)
    {
        string baseDirectory = AppContext.BaseDirectory;
        FileAppLogger logger = new FileAppLogger(Path.Combine(baseDirectory, "logs"));
        WindowsFirewallService firewallService = new WindowsFirewallService(logger, Path.Combine(baseDirectory, "elevation"));
        OperationResult result = await firewallService.EnsureFromElevatedRequestAsync(requestPath, CancellationToken.None);
        if (result.Succeeded)
        {
            Environment.ExitCode = 0;
            return;
        }
        Environment.ExitCode = 1;
    }

    private sealed class ApplicationComposition
    {
        public required ServerOrchestrator ServerOrchestrator { get; init; }
        public required BasicSettingsService BasicSettingsService { get; init; }
        public required ModSettingsService ModSettingsService { get; init; }
        public required GameSettingsService GameSettingsService { get; init; }
        public required DiagnosticsService DiagnosticsService { get; init; }
        public required ManualBackupCoordinator BackupCoordinator { get; init; }
        public required IApplicationStatusStore StatusStore { get; init; }
    }
}
