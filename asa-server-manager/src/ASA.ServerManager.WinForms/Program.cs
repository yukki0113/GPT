using ASA.ServerManager.Application;
using ASA.ServerManager.Infrastructure;

namespace ASA.ServerManager.WinForms;

static class Program
{
    /// <summary>
    ///  The main entry point for the application.
    /// </summary>
    [STAThread]
    static void Main()
    {
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
            logger);
    }
}
