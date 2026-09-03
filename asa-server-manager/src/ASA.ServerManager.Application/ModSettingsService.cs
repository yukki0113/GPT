using ASA.ServerManager.Domain;

namespace ASA.ServerManager.Application;

/// <summary>MOD一覧の検証、並び替え、永続化をViewから分離します。</summary>
public sealed class ModSettingsService
{
    private readonly IServerSettingsRepository _settingsRepository;

    /// <summary>設定Repositoryを指定します。</summary>
    public ModSettingsService(IServerSettingsRepository settingsRepository)
    {
        _settingsRepository = settingsRepository;
    }

    /// <summary>保存済みMODを順序どおり読み込みます。</summary>
    public async Task<OperationResult<IReadOnlyList<ModDefinition>>> LoadAsync(CancellationToken cancellationToken)
    {
        OperationResult<ServerSettings> result = await _settingsRepository.LoadAsync(cancellationToken);
        if (!result.Succeeded || result.Value is null)
        {
            return OperationResult<IReadOnlyList<ModDefinition>>.Failure(result.ErrorMessage ?? "MOD設定を読み込めません。", errorCode: "MOD_LOAD_FAILED");
        }
        return OperationResult<IReadOnlyList<ModDefinition>>.Success(SortAndNormalize(result.Value.Mods));
    }

    /// <summary>MODを末尾へ追加します。</summary>
    public OperationResult<IReadOnlyList<ModDefinition>> Add(IReadOnlyList<ModDefinition> mods, string projectId, string name)
    {
        string normalizedId = projectId.Trim();
        if (normalizedId.Length == 0 || !normalizedId.All(char.IsDigit))
        {
            return OperationResult<IReadOnlyList<ModDefinition>>.Failure("Project IDは数字で入力してください。", errorCode: "MOD_PROJECT_ID_INVALID");
        }
        if (mods.Any(mod => string.Equals(mod.ProjectId, normalizedId, StringComparison.OrdinalIgnoreCase)))
        {
            return OperationResult<IReadOnlyList<ModDefinition>>.Failure("同じProject IDは追加できません。", errorCode: "MOD_PROJECT_ID_DUPLICATE");
        }
        List<ModDefinition> updated = mods.ToList();
        updated.Add(new ModDefinition { ProjectId = normalizedId, Name = name.Trim(), Enabled = true, Order = updated.Count });
        return OperationResult<IReadOnlyList<ModDefinition>>.Success(NormalizeInOrder(updated));
    }

    /// <summary>指定位置のMODを削除します。</summary>
    public OperationResult<IReadOnlyList<ModDefinition>> Remove(IReadOnlyList<ModDefinition> mods, int index)
    {
        if (index < 0 || index >= mods.Count)
        {
            return OperationResult<IReadOnlyList<ModDefinition>>.Failure("削除するMODを選択してください。", errorCode: "MOD_SELECTION_REQUIRED");
        }
        List<ModDefinition> updated = mods.ToList();
        updated.RemoveAt(index);
        return OperationResult<IReadOnlyList<ModDefinition>>.Success(NormalizeInOrder(updated));
    }

    /// <summary>指定位置のMODを一つ上へ移動します。</summary>
    public OperationResult<IReadOnlyList<ModDefinition>> MoveUp(IReadOnlyList<ModDefinition> mods, int index)
    {
        return Move(mods, index, index - 1);
    }

    /// <summary>指定位置のMODを一つ下へ移動します。</summary>
    public OperationResult<IReadOnlyList<ModDefinition>> MoveDown(IReadOnlyList<ModDefinition> mods, int index)
    {
        return Move(mods, index, index + 1);
    }

    /// <summary>MOD一覧を検証してserver-settings.jsonへ保存し、再読込します。</summary>
    public async Task<OperationResult<IReadOnlyList<ModDefinition>>> SaveAsync(IReadOnlyList<ModDefinition> mods, CancellationToken cancellationToken)
    {
        OperationResult validation = Validate(mods);
        if (!validation.Succeeded)
        {
            return OperationResult<IReadOnlyList<ModDefinition>>.Failure(validation.ErrorMessage ?? "MOD設定を確認してください。", errorCode: validation.ErrorCode);
        }
        OperationResult<ServerSettings> settingsResult = await _settingsRepository.LoadAsync(cancellationToken);
        if (!settingsResult.Succeeded || settingsResult.Value is null)
        {
            return OperationResult<IReadOnlyList<ModDefinition>>.Failure(settingsResult.ErrorMessage ?? "基本設定を読み込めません。", errorCode: "SETTINGS_LOAD_FAILED");
        }
        settingsResult.Value.Mods = NormalizeInOrder(mods).ToList();
        OperationResult saveResult = await _settingsRepository.SaveAsync(settingsResult.Value, cancellationToken);
        if (!saveResult.Succeeded)
        {
            return OperationResult<IReadOnlyList<ModDefinition>>.Failure(saveResult.ErrorMessage ?? "MOD設定を保存できません。", errorCode: "MOD_SAVE_FAILED");
        }
        return await LoadAsync(cancellationToken);
    }

    /// <summary>Project IDと重複を検証します。</summary>
    public static OperationResult Validate(IReadOnlyList<ModDefinition> mods)
    {
        if (mods.Any(mod => string.IsNullOrWhiteSpace(mod.ProjectId) || !mod.ProjectId.All(char.IsDigit)))
        {
            return OperationResult.Failure("Project IDは空にせず数字で入力してください。", errorCode: "MOD_PROJECT_ID_INVALID");
        }
        if (mods.Select(mod => mod.ProjectId).Distinct(StringComparer.OrdinalIgnoreCase).Count() != mods.Count)
        {
            return OperationResult.Failure("Project IDが重複しています。", errorCode: "MOD_PROJECT_ID_DUPLICATE");
        }
        return OperationResult.Success();
    }

    private static OperationResult<IReadOnlyList<ModDefinition>> Move(IReadOnlyList<ModDefinition> mods, int sourceIndex, int destinationIndex)
    {
        if (sourceIndex < 0 || sourceIndex >= mods.Count || destinationIndex < 0 || destinationIndex >= mods.Count)
        {
            return OperationResult<IReadOnlyList<ModDefinition>>.Failure("これ以上移動できません。", errorCode: "MOD_MOVE_INVALID");
        }
        List<ModDefinition> updated = mods.ToList();
        ModDefinition selected = updated[sourceIndex];
        updated.RemoveAt(sourceIndex);
        updated.Insert(destinationIndex, selected);
        return OperationResult<IReadOnlyList<ModDefinition>>.Success(NormalizeInOrder(updated));
    }

    private static IReadOnlyList<ModDefinition> SortAndNormalize(IEnumerable<ModDefinition> mods)
    {
        return NormalizeInOrder(mods.OrderBy(mod => mod.Order));
    }

    private static IReadOnlyList<ModDefinition> NormalizeInOrder(IEnumerable<ModDefinition> mods)
    {
        List<ModDefinition> result = [];
        int order = 0;
        foreach (ModDefinition mod in mods)
        {
            result.Add(new ModDefinition { ProjectId = mod.ProjectId.Trim(), Name = mod.Name.Trim(), Enabled = mod.Enabled, Order = order });
            order++;
        }
        return result;
    }
}
