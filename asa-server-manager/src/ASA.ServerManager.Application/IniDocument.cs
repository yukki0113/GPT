using ASA.ServerManager.Domain;

namespace ASA.ServerManager.Application;

/// <summary>INI内の行を順序どおり保持する編集用ドキュメントです。</summary>
public sealed class IniDocument
{
    /// <summary>ドキュメントを初期化します。</summary>
    public IniDocument(IniFileKind fileKind, IEnumerable<IniNode> nodes, string newLine, bool hasUtf8Bom)
    {
        FileKind = fileKind;
        Nodes = nodes.ToList();
        NewLine = newLine;
        HasUtf8Bom = hasUtf8Bom;
    }
    public IniFileKind FileKind { get; }
    public List<IniNode> Nodes { get; }
    public string NewLine { get; }
    public bool HasUtf8Bom { get; }

    /// <summary>指定SectionとKeyに一致する既存ノードを返します。</summary>
    public IReadOnlyList<IniKeyValueNode> FindKeys(string section, string key)
    {
        return Nodes.OfType<IniKeyValueNode>().Where(node => string.Equals(node.Section, section, StringComparison.OrdinalIgnoreCase) && string.Equals(node.Key, key, StringComparison.OrdinalIgnoreCase)).ToList();
    }

    /// <summary>既存値を更新し、未存在ならSectionの末尾へ追加します。</summary>
    public void SetValue(string section, string key, string value)
    {
        IReadOnlyList<IniKeyValueNode> matches = FindKeys(section, key);
        if (matches.Count == 1)
        {
            matches[0].Value = value;
            return;
        }
        int sectionIndex = FindSectionIndex(section);
        if (sectionIndex < 0)
        {
            if (Nodes.Count > 0 && Nodes[^1] is not IniBlankLineNode)
            {
                Nodes.Add(new IniBlankLineNode());
            }
            Nodes.Add(new IniSectionNode(section));
            Nodes.Add(new IniKeyValueNode(section, key, value));
            return;
        }
        int insertIndex = sectionIndex + 1;
        while (insertIndex < Nodes.Count && Nodes[insertIndex] is not IniSectionNode)
        {
            insertIndex++;
        }
        Nodes.Insert(insertIndex, new IniKeyValueNode(section, key, value));
    }

    private int FindSectionIndex(string section)
    {
        for (int index = 0; index < Nodes.Count; index++)
        {
            if (Nodes[index] is IniSectionNode sectionNode && string.Equals(sectionNode.Name, section, StringComparison.OrdinalIgnoreCase))
            {
                return index;
            }
        }
        return -1;
    }
}

/// <summary>INIの一行を表します。</summary>
public abstract class IniNode { public abstract string ToIniLine(); }
public sealed class IniBlankLineNode : IniNode { public override string ToIniLine() { return string.Empty; } }
public sealed class IniCommentNode(string text) : IniNode { public string Text { get; } = text; public override string ToIniLine() { return Text; } }
public sealed class IniRawLineNode(string text) : IniNode { public string Text { get; } = text; public override string ToIniLine() { return Text; } }
public sealed class IniSectionNode(string name) : IniNode { public string Name { get; } = name; public override string ToIniLine() { return $"[{Name}]"; } }
public sealed class IniKeyValueNode(string section, string key, string value) : IniNode { public string Section { get; } = section; public string Key { get; } = key; public string Value { get; set; } = value; public override string ToIniLine() { return $"{Key}={Value}"; } }
