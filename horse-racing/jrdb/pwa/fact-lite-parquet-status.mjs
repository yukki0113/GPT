import { FactLiteDuckDb } from "./fact-lite-duckdb.js?v=2";

const stageMessages = Object.freeze({
  cache: "ローカルParquetを検証中…",
  manifest: "Parquet manifest確認中…",
  download: "Fact Lite Parquet取得・SHA-256検証中…",
  duckdb: "DuckDB初期化・schema/行数検証中…"
});

export function factLiteParquetStageMessage(stage, table) {
  if (stage === "download" && table) {
    return "Parquet取得・SHA-256検証中…（" + table + "）";
  }
  return stageMessages[stage] || "Parquet状態を確認中…";
}

export function factLiteParquetErrorMessage(error, cacheAvailable) {
  const detail = String(error && error.message ? error.message : error || "");
  let message = "Parquet初期化に失敗しました";
  if (/HTTP|fetch|network/i.test(detail)) message = "配布データを取得できませんでした";
  if (/SHA-256|size不一致/i.test(detail)) message = "Parquetの整合性検証に失敗しました";
  if (/schema|row count|必須列|manifest/i.test(detail)) message = "Parquet契約の検証に失敗しました";
  if (cacheAvailable) message += "。検証済みの既存cacheは利用可能です";
  return message + "。";
}

if (typeof document !== "undefined") {
  const cacheStatus = document.getElementById("fact-parquet-cache-status");
  const engineStatus = document.getElementById("fact-parquet-engine-status");
  const remoteStatus = document.getElementById("fact-parquet-remote-status");
  const progress = document.getElementById("fact-parquet-progress");
  const checkButton = document.getElementById("fact-btn-parquet-check");
  const syncButton = document.getElementById("fact-btn-parquet-sync");
  let cacheAvailable = false;

  function setProgress(message) {
    progress.textContent = message;
  }

  function updateButtons() {
    const online = navigator.onLine;
    checkButton.disabled = !online;
    syncButton.disabled = !online;
  }

  function reportStage(stage, table) {
    setProgress(factLiteParquetStageMessage(stage, table));
  }

  async function restore() {
    cacheStatus.textContent = "確認中…";
    engineStatus.textContent = "待機中";
    try {
      const restored = await FactLiteDuckDb.restoreCache(reportStage);
      if (!restored) {
        cacheStatus.textContent = "未取得";
        engineStatus.textContent = "未初期化";
        setProgress("検証済みParquet cacheはまだありません。");
        return null;
      }
      cacheAvailable = true;
      cacheStatus.textContent = "利用可能 / " + restored.cached.generationId;
      engineStatus.textContent = "DuckDB-Wasm検証済み";
      setProgress(navigator.onLine
        ? "ローカルcacheは検証済みです。配布版は未確認です。"
        : "オフラインで検証済みローカルcacheを利用できます。"
      );
      return restored;
    } catch (error) {
      console.error("Fact Lite Parquet cache restore failed", error);
      cacheStatus.textContent = "利用不可";
      engineStatus.textContent = "初期化失敗";
      setProgress(factLiteParquetErrorMessage(error, cacheAvailable));
      return null;
    }
  }

  async function check() {
    if (!navigator.onLine) {
      remoteStatus.textContent = "オフライン";
      setProgress(cacheAvailable
        ? "オフラインのため、検証済みローカルcacheを利用できます。"
        : "オフラインのため、配布版を確認できません。"
      );
      return null;
    }
    remoteStatus.textContent = "確認中…";
    setProgress("Parquet manifest確認中…");
    try {
      const remote = await FactLiteDuckDb.fetchCurrent();
      remoteStatus.textContent = "配布中 / " + remote.current.generation_id;
      setProgress(cacheAvailable
        ? "配布版manifestを確認しました。同期が必要な場合は「Parquetを同期」を実行してください。"
        : "配布版manifestを確認しました。初回は「Parquetを同期」を実行してください。"
      );
      return remote;
    } catch (error) {
      console.error("Fact Lite Parquet remote check failed", error);
      remoteStatus.textContent = "確認失敗";
      setProgress(factLiteParquetErrorMessage(error, cacheAvailable));
      return null;
    }
  }

  async function synchronize() {
    if (!navigator.onLine) return check();
    updateButtons();
    checkButton.disabled = true;
    syncButton.disabled = true;
    try {
      const result = await FactLiteDuckDb.synchronizeCache(fetch, reportStage);
      cacheAvailable = true;
      cacheStatus.textContent = "利用可能 / " + result.cached.generationId;
      remoteStatus.textContent = "配布中 / " + result.cached.generationId;
      engineStatus.textContent = "DuckDB-Wasm検証済み";
      setProgress(result.updated
        ? "Parquet同期・検証が完了しました。次回はオフラインでも復元できます。"
        : "配布版とローカルcacheは同一generationです。"
      );
    } catch (error) {
      console.error("Fact Lite Parquet sync failed", error);
      setProgress(factLiteParquetErrorMessage(error, cacheAvailable));
    } finally {
      updateButtons();
    }
  }

  async function initialize() {
    if (!navigator.storage || !navigator.storage.getDirectory) {
      cacheStatus.textContent = "OPFS非対応";
      engineStatus.textContent = "利用不可";
      remoteStatus.textContent = "未確認";
      setProgress("このブラウザではParquet cacheを利用できません。");
      return;
    }
    updateButtons();
    await restore();
    if (navigator.onLine) await check();
  }

  checkButton.addEventListener("click", function () { void check(); });
  syncButton.addEventListener("click", function () { void synchronize(); });
  window.addEventListener("online", function () { updateButtons(); void check(); });
  window.addEventListener("offline", function () { updateButtons(); void check(); });
  window.JRDBFactLiteParquetStatus = Object.freeze({ check, synchronize, restore });
  void initialize();
}
