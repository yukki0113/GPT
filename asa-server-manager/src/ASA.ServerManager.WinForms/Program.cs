using ASA.ServerManager.Application;
using ASA.ServerManager.Domain;
using ASA.ServerManager.Infrastructure;

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
        System.Windows.Forms.Application.Run(new MainForm(CreateServerOrchestrator()));
    }

    private static ServerOrchestrator CreateServerOrchestrator()
    {
        string baseDirectory = AppContext.BaseDirectory;
        FileAppLogger logger = new FileAppLogger(Path.Combine(baseDirectory, "logs"));
        JsonServerSettingsRepository settingsRepository = new JsonServerSettingsRepository(Path.Combine(baseDirectory, "config", "server-settings.json"));
        DpapiSecretRepository secretRepository = new DpapiSecretRepository(Path.Combine(baseDirectory, "secrets", "secrets.dat"));
        JsonGameSettingCatalogRepository catalogRepository = new JsonGameSettingCatalogRepository(Path.Combine(baseDirectory, "definitions", "game-settings.json"));
        IniBackupService backupService = new IniBackupService(Path.Combine(baseDirectory, "backups"));
        IniDocumentService iniDocumentService = new IniDocumentService();
        IniConfigurationSaveService saveService = new IniConfigurationSaveService(iniDocumentService, backupService);
        IniEnabledSettingsSaver saver = new IniEnabledSettingsSaver(catalogRepository, saveService);
        HttpClient httpClient = new HttpClient();
        WindowsFirewallService firewallService = new WindowsFirewallService(logger, Path.Combine(baseDirectory, "elevation"));
        FirewallElevationLauncher elevationLauncher = new FirewallElevationLauncher(System.Windows.Forms.Application.ExecutablePath, Path.Combine(baseDirectory, "elevation"), logger);
        NetworkInfoService networkInfoService = new NetworkInfoService(logger);
        return new ServerOrchestrator(
            settingsRepository,
            secretRepository,
            new SteamCmdService(httpClient, logger),
            new AsaProcessService(logger),
            new RconClient(),
            saver,
            new ServerArgumentBuilder(),
            new ServerStateResolver(),
            new SystemOperationDelay(),
            logger,
            firewallService,
            elevationLauncher,
            networkInfoService,
            new FirewallRequirementsBuilder());
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
}
