"use strict";

/* Full-day package delivery: published current-day auto refresh + manual fallback import. */
const NEWSPAPER_DAY_OPFS_FILE = "current-day.json";
const NEWSPAPER_CURRENT_BASE = "./data/newspaper/current/";
const dayFileInput = document.getElementById("newspaper-day-file");
const dayImportButton = document.getElementById("newspaper-day-import");
const dayRefreshButton = document.getElementById("newspaper-day-refresh");
const dayClearButton = document.getElementById("newspaper-day-clear");
const dayStatus = document.getElementById("newspaper-day-status");
const dayRaceSelectWrap = document.getElementById("newspaper-day-race-wrap");
const dayRaceSelect = document.getElementById("newspaper-day-race-select");
let currentDayPackage = null;
let dayRefreshInFlight = false;

function validateDayPackage(value) {
  if (!value || typeof value !== "object") throw new Error("日次JSON objectではありません。");
  if (value.schema_version !== "0.1" || value.bundle_kind !== "jrdb_pwa_newspaper_day_package") {
    throw new Error("Newspaper day packageではありません。");
  }
  if (!value.manifest || value.manifest.manifest_kind !== "jrdb_pwa_newspaper_daily_manifest") {
    throw new Error("daily manifestがありません。");
  }
  if (!Array.isArray(value.races) || value.races.length === 0) throw new Error("racesがありません。");
  const seen = new Set();
  for (const bundle of value.races) {
    validateBundle(bundle);
    const raceKey = text(bundle.race && bundle.race.race_key, "");
    if (!raceKey || seen.has(raceKey)) throw new Error(`race_keyが不正または重複: ${raceKey}`);
    if (bundle.race.date !== value.manifest.date) throw new Error(`日付不一致: ${raceKey}`);
    seen.add(raceKey);
  }
  const expected = Number(value.manifest.completeness && value.manifest.completeness.expected_races);
  if (Number.isInteger(expected) && expected > 0 && expected !== value.races.length) {
    throw new Error(`レース数不一致: manifest=${expected} package=${value.races.length}`);
  }
  return value;
}

function validatePublishedManifest(value) {
  if (!value || typeof value !== "object") throw new Error("配信manifestがJSON objectではありません。");
  if (value.schema_version !== "0.1" || value.manifest_kind !== "jrdb_pwa_newspaper_daily_manifest") {
    throw new Error("Newspaper daily manifestではありません。");
  }
  if (!/^20\d{2}-\d{2}-\d{2}$/.test(text(value.date, ""))) throw new Error("manifestの日付が不正です。");
  if (!Array.isArray(value.races) || value.races.length === 0) throw new Error("manifestにracesがありません。");

  const expected = Number(value.completeness && value.completeness.expected_races);
  if (Number.isInteger(expected) && expected > 0 && expected !== value.races.length) {
    throw new Error(`manifestレース数不一致: expected=${expected} races=${value.races.length}`);
  }

  const raceKeys = new Set();
  const paths = new Set();
  for (const entry of value.races) {
    const raceKey = text(entry && entry.race_key, "");
    const path = text(entry && entry.path, "");
    const sha = text(entry && entry.sha256, "").toLowerCase();
    if (!raceKey || raceKeys.has(raceKey)) throw new Error(`manifest race_keyが不正または重複: ${raceKey}`);
    if (!/^races\/[^/]+\.json$/.test(path) || path.includes("..") || paths.has(path)) {
      throw new Error(`manifest race pathが不正または重複: ${path}`);
    }
    if (!/^[0-9a-f]{64}$/.test(sha)) throw new Error(`manifest SHA-256が不正: ${raceKey}`);
    raceKeys.add(raceKey);
    paths.add(path);
  }
  return value;
}

function dayRaceLabel(bundle) {
  const race = bundle.race;
  const title = text(race.race_name, "");
  return `${text(race.venue)} ${text(race.race_no)}R${title ? ` ${title}` : ""}`;
}

function dayPackageSummary(value) {
  if (!value || !value.manifest) return "新聞データなし";
  const sources = value.manifest.source_status || {};
  const evalState = sources.eval && sources.eval.state === "READY" ? "Eval○" : "Eval—";
  const rnState = sources.racenote_prediction && sources.racenote_prediction.state === "READY" ? "RN○" : "RN—";
  const ilukaState = sources.keibailuka && sources.keibailuka.state === "READY" ? "🐬○" : "🐬—";
  const count = Array.isArray(value.races) ? value.races.length : 0;
  return `${value.manifest.date} / ${count}R / ${evalState} / ${rnState} / ${ilukaState}`;
}

function activateDayRace(raceKey) {
  if (!currentDayPackage) return;
  const bundle = currentDayPackage.races.find(item => String(item.race.race_key) === String(raceKey));
  if (!bundle) return;
  currentBundle = bundle;
  dayRaceSelect.value = String(bundle.race.race_key);
  renderBundle();
  saveBundle(bundle).catch(error => console.error(error));
}

function renderDayPackage(value, restore = false, sourceLabel = "") {
  currentDayPackage = value;
  const ordered = [...value.races].sort((a, b) => {
    const venueDiff = Number(a.race.venue_code) - Number(b.race.venue_code);
    return venueDiff || Number(a.race.race_no) - Number(b.race.race_no);
  });
  currentDayPackage.races = ordered;
  dayRaceSelect.innerHTML = ordered.map(bundle =>
    `<option value="${escapeHtml(text(bundle.race.race_key, ""))}">${escapeHtml(dayRaceLabel(bundle))}</option>`
  ).join("");
  dayRaceSelectWrap.hidden = false;
  dayClearButton.disabled = false;
  const preferredRaceKey = currentBundle && currentBundle.race ? String(currentBundle.race.race_key || "") : "";
  const initialBundle = ordered.find(bundle => String(bundle.race.race_key) === preferredRaceKey) || ordered[0];
  activateDayRace(initialBundle.race.race_key);
  const prefix = sourceLabel || (restore ? "端末保存から復元" : "日次読込完了");
  dayStatus.textContent = `${prefix}: ${dayPackageSummary(value)}`;
}

async function saveDayPackage(value) {
  if (!opfsAvailable) return false;
  const directory = await getNewspaperDirectory(true);
  const handle = await directory.getFileHandle(NEWSPAPER_DAY_OPFS_FILE, { create: true });
  const writable = await handle.createWritable();
  await writable.write(JSON.stringify(value));
  await writable.close();
  return true;
}

async function restoreDayPackage() {
  if (!opfsAvailable) return false;
  try {
    const directory = await getNewspaperDirectory(false);
    const handle = await directory.getFileHandle(NEWSPAPER_DAY_OPFS_FILE);
    const file = await handle.getFile();
    renderDayPackage(validateDayPackage(JSON.parse(await file.text())), true);
    return true;
  } catch (error) {
    if (error && error.name !== "NotFoundError") console.error(error);
    return false;
  }
}

function publishedUrl(relativePath) {
  return new URL(`${NEWSPAPER_CURRENT_BASE}${relativePath}`, window.location.href);
}

function manifestSignature(manifest) {
  const entries = [...(manifest.races || [])]
    .map(entry => `${text(entry.race_key, "")}:${text(entry.sha256, "").toLowerCase()}`)
    .sort();
  return `${text(manifest.date, "")}|${Number(manifest.revision) || 0}|${entries.join("|")}`;
}

async function sha256Hex(buffer) {
  if (!window.crypto || !window.crypto.subtle) throw new Error("この端末ではSHA-256検証を利用できません。");
  const digest = await window.crypto.subtle.digest("SHA-256", buffer);
  return [...new Uint8Array(digest)].map(value => value.toString(16).padStart(2, "0")).join("");
}

async function fetchPublishedRace(entry, manifest) {
  const response = await fetch(publishedUrl(entry.path), { cache: "no-store" });
  if (!response.ok) throw new Error(`${entry.path} の取得に失敗しました (${response.status})`);
  const buffer = await response.arrayBuffer();
  const digest = await sha256Hex(buffer);
  if (digest !== String(entry.sha256).toLowerCase()) {
    throw new Error(`${entry.path} のSHA-256がmanifestと一致しません。`);
  }
  const bundle = JSON.parse(new TextDecoder("utf-8").decode(buffer));
  validateBundle(bundle);
  const race = bundle.race || {};
  if (String(race.race_key) !== String(entry.race_key)
      || String(race.date) !== String(manifest.date)
      || String(race.venue_code).padStart(2, "0") !== String(entry.venue_code).padStart(2, "0")
      || Number(race.race_no) !== Number(entry.race_no)) {
    throw new Error(`${entry.path} のレースidentityがmanifestと一致しません。`);
  }
  return bundle;
}

async function refreshPublishedDay({ automatic = false } = {}) {
  if (dayRefreshInFlight) return false;
  dayRefreshInFlight = true;
  if (dayRefreshButton) dayRefreshButton.disabled = true;

  if (!navigator.onLine) {
    dayStatus.textContent = currentDayPackage
      ? `${dayPackageSummary(currentDayPackage)} / オフラインのため保存済みを表示`
      : "オフラインです。端末保存データもありません。";
    dayRefreshInFlight = false;
    if (dayRefreshButton) dayRefreshButton.disabled = false;
    return false;
  }

  dayStatus.textContent = currentDayPackage && automatic
    ? `${dayPackageSummary(currentDayPackage)} / 最新データを確認中…`
    : "最新の新聞データを確認しています…";

  try {
    const response = await fetch(publishedUrl("manifest.json"), { cache: "no-store" });
    if (response.status === 404) {
      dayStatus.textContent = currentDayPackage
        ? `${dayPackageSummary(currentDayPackage)} / 配信データ未公開のため保存済みを継続`
        : "配信データはまだ公開されていません。手動JSON取込は利用できます。";
      return false;
    }
    if (!response.ok) throw new Error(`manifest取得失敗 (${response.status})`);

    const manifest = validatePublishedManifest(await response.json());
    if (currentDayPackage && manifestSignature(currentDayPackage.manifest) === manifestSignature(manifest)) {
      dayStatus.textContent = `${dayPackageSummary(currentDayPackage)} / 最新`;
      return false;
    }
    if (currentDayPackage && String(manifest.date) < String(currentDayPackage.manifest.date)) {
      dayStatus.textContent = `${dayPackageSummary(currentDayPackage)} / 配信データが端末保存より古いため更新せず`;
      return false;
    }

    dayStatus.textContent = `${manifest.date} の新聞データを取得・検証しています…`;
    const races = await Promise.all(manifest.races.map(entry => fetchPublishedRace(entry, manifest)));
    const packageValue = validateDayPackage({
      schema_version: "0.1",
      bundle_kind: "jrdb_pwa_newspaper_day_package",
      manifest,
      races
    });

    const saved = await saveDayPackage(packageValue);
    renderDayPackage(packageValue, false, "配信データ更新");
    dayStatus.textContent += saved ? " / 端末保存済み" : " / OPFS保存不可";
    return true;
  } catch (error) {
    console.error(error);
    dayStatus.textContent = currentDayPackage
      ? `${dayPackageSummary(currentDayPackage)} / 更新確認失敗のため保存済みを継続`
      : `配信データ取得失敗: ${error.message}`;
    return false;
  } finally {
    dayRefreshInFlight = false;
    if (dayRefreshButton) dayRefreshButton.disabled = false;
  }
}

async function importDayPackage() {
  const file = dayFileInput.files && dayFileInput.files[0];
  if (!file) return;
  dayImportButton.disabled = true;
  dayStatus.textContent = "1日分JSONを検証しています…";
  try {
    const value = validateDayPackage(JSON.parse(await file.text()));
    renderDayPackage(value, false);
    const saved = await saveDayPackage(value);
    dayStatus.textContent += saved ? " / 端末保存済み" : " / OPFS保存不可";
  } catch (error) {
    console.error(error);
    dayStatus.textContent = `日次読込失敗: ${error.message}`;
  } finally {
    dayImportButton.disabled = !(dayFileInput.files && dayFileInput.files.length);
  }
}

async function clearDayPackage() {
  if (opfsAvailable) {
    try {
      const directory = await getNewspaperDirectory(false);
      await directory.removeEntry(NEWSPAPER_DAY_OPFS_FILE);
    } catch (error) {
      if (error && error.name !== "NotFoundError") throw error;
    }
  }
  currentDayPackage = null;
  dayRaceSelectWrap.hidden = true;
  dayRaceSelect.innerHTML = "";
  dayClearButton.disabled = true;
  dayStatus.textContent = "1日分の端末保存を削除しました。";
}

dayFileInput.addEventListener("change", () => {
  dayImportButton.disabled = !(dayFileInput.files && dayFileInput.files.length);
});
dayImportButton.addEventListener("click", importDayPackage);
if (dayRefreshButton) {
  dayRefreshButton.addEventListener("click", () => refreshPublishedDay({ automatic: false }));
}
dayClearButton.addEventListener("click", () => clearDayPackage().catch(error => {
  console.error(error);
  dayStatus.textContent = `日次削除失敗: ${error.message}`;
}));
dayRaceSelect.addEventListener("change", () => activateDayRace(dayRaceSelect.value));
window.addEventListener("load", () => {
  checkOpfs()
    .then(() => restoreBundle())
    .then(() => restoreDayPackage())
    .then(() => refreshPublishedDay({ automatic: true }))
    .catch(error => console.error(error));
});
