namespace ASA.ServerManager.WinForms;

/// <summary>後続工程の基本設定領域を示すプレースホルダーです。</summary>
public sealed class BasicSettingsView : UserControl { public BasicSettingsView() { Controls.Add(CreateMessage("基本設定は後続工程で実装します。")); } private static Label CreateMessage(string text) { Label label = new Label(); label.AutoSize = true; label.Location = new Point(24, 24); label.Text = text; return label; } }

/// <summary>後続工程のMOD領域を示すプレースホルダーです。</summary>
public sealed class ModsView : UserControl { public ModsView() { Controls.Add(CreateMessage("MOD管理は後続工程で実装します。")); } private static Label CreateMessage(string text) { Label label = new Label(); label.AutoSize = true; label.Location = new Point(24, 24); label.Text = text; return label; } }

/// <summary>後続工程の診断領域を示すプレースホルダーです。</summary>
public sealed class DiagnosticsView : UserControl { public DiagnosticsView() { Controls.Add(CreateMessage("ログ・診断は後続工程で実装します。")); } private static Label CreateMessage(string text) { Label label = new Label(); label.AutoSize = true; label.Location = new Point(24, 24); label.Text = text; return label; } }
