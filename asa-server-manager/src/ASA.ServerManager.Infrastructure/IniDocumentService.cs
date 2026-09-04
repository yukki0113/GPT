using System.Text;
using ASA.ServerManager.Application;
using ASA.ServerManager.Domain;

namespace ASA.ServerManager.Infrastructure;

/// <summary>コメント、空行、未知行を保持してINIを読み書きします。</summary>
public sealed class IniDocumentService : IIniDocumentService
{
    /// <inheritdoc />
    public async Task<OperationResult<IniDocument>> LoadAsync(string path, IniFileKind fileKind, CancellationToken cancellationToken)
    {
        try
        {
            if (!File.Exists(path))
            {
                return OperationResult<IniDocument>.Failure($"INIファイルが見つかりません: {path}");
            }

            byte[] bytes = await File.ReadAllBytesAsync(path, cancellationToken);
            bool hasUtf8Bom = bytes.Length >= 3 && bytes[0] == 0xEF && bytes[1] == 0xBB && bytes[2] == 0xBF;
            int startIndex = 0;
            if (hasUtf8Bom)
            {
                startIndex = 3;
            }
            string text = new UTF8Encoding(false, true).GetString(bytes, startIndex, bytes.Length - startIndex);
            string newLine = "\n";
            if (text.Contains("\r\n", StringComparison.Ordinal))
            {
                newLine = "\r\n";
            }
            List<IniNode> nodes = Parse(text);
            return OperationResult<IniDocument>.Success(new IniDocument(fileKind, nodes, newLine, hasUtf8Bom));
        }
        catch (DecoderFallbackException exception)
        {
            string userMessage = "INIファイルをUTF-8として読み込めませんでした。" + Environment.NewLine
                + "安全のためファイルは変更していません。" + Environment.NewLine
                + "Game.ini / GameUserSettings.ini の文字コードを確認してください。";
            return OperationResult<IniDocument>.Failure(userMessage, errorCode: "INI_UNSUPPORTED_ENCODING", technicalMessage: exception.ToString());
        }
        catch (Exception exception)
        {
            return OperationResult<IniDocument>.Failure($"INIの読込に失敗しました: {exception.Message}");
        }
    }

    /// <inheritdoc />
    public async Task<OperationResult> SaveAsync(string path, IniDocument document, CancellationToken cancellationToken)
    {
        string? tempPath = null;
        try
        {
            string directory = Path.GetDirectoryName(path) ?? throw new InvalidOperationException("INIファイルの親ディレクトリが不明です。");
            Directory.CreateDirectory(directory);
            tempPath = Path.Combine(directory, $".{Path.GetFileName(path)}.{Guid.NewGuid():N}.tmp");

            // 置換前に一時ファイルを生成し、同じパーサーで読めることを確認します。
            string text = string.Join(document.NewLine, document.Nodes.Select(node => node.ToIniLine()));
            Encoding encoding = new UTF8Encoding(document.HasUtf8Bom);
            await File.WriteAllTextAsync(tempPath, text, encoding, cancellationToken);
            OperationResult<IniDocument> verification = await LoadAsync(tempPath, document.FileKind, cancellationToken);
            if (!verification.Succeeded)
            {
                return OperationResult.Failure($"INI一時ファイルの検証に失敗しました: {verification.ErrorMessage}");
            }

            File.Move(tempPath, path, true);
            tempPath = null;
            return OperationResult.Success();
        }
        catch (Exception exception)
        {
            return OperationResult.Failure($"INIの保存に失敗しました: {exception.Message}");
        }
        finally
        {
            if (tempPath is not null && File.Exists(tempPath))
            {
                File.Delete(tempPath);
            }
        }
    }

    private static List<IniNode> Parse(string text)
    {
        List<IniNode> nodes = [];
        string currentSection = string.Empty;
        string[] lines = text.Replace("\r\n", "\n", StringComparison.Ordinal).Split('\n');
        foreach (string line in lines)
        {
            if (line.Length == 0)
            {
                nodes.Add(new IniBlankLineNode());
                continue;
            }
            string trimmed = line.TrimStart();
            if (trimmed.StartsWith(';') || trimmed.StartsWith('#'))
            {
                nodes.Add(new IniCommentNode(line));
                continue;
            }
            if (line.StartsWith('[') && line.EndsWith(']') && line.Length > 2)
            {
                currentSection = line[1..^1];
                nodes.Add(new IniSectionNode(currentSection));
                continue;
            }
            int separatorIndex = line.IndexOf('=');
            if (separatorIndex > 0 && currentSection.Length > 0)
            {
                string key = line[..separatorIndex];
                string value = line[(separatorIndex + 1)..];
                nodes.Add(new IniKeyValueNode(currentSection, key, value));
                continue;
            }
            nodes.Add(new IniRawLineNode(line));
        }
        return nodes;
    }
}
