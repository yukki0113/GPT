"use strict";

/* Manual full-day package import for Newspaper acceptance testing. */
const NEWSPAPER_DAY_OPFS_FILE = "current-day.json";
const dayFileInput = document.getElementById("newspaper-day-file");
const dayImportButton = document.getElementById("newspaper-day-import");
const dayClearButton = document.getElementById("newspaper-day-clear");
const dayStatus = document.getElementById("newspaper-day-status");
const dayRaceSelectWrap = document.getElementById("newspaper-day-race-wrap");
const dayRaceSelect = document.getElementById("newspaper-day-race-select");
let currentDayPackage = null;

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

function dayRaceLabel(bundle) {
  const race = bundle.race;
  const title = text(race.race_name, "");
  return `${text(race.venue)} ${text(race.race_no)}R${title ? ` ${title}` : ""}`;
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

function renderDayPackage(value, restore = false) {
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
  activateDayRace(ordered[0].race.race_key);
  const sources = value.manifest.source_status || {};
  const evalState = sources.eval && sources.eval.state === "READY" ? "Eval○" : "Eval—";
  const ilukaState = sources.keibailuka && sources.keibailuka.state === "READY" ? "🐬○" : "🐬—";
  dayStatus.textContent = `${restore ? "端末保存から復元" : "日次読込完了"}: ${value.manifest.date} / ${ordered.length}R / ${evalState} / ${ilukaState}`;
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
dayClearButton.addEventListener("click", () => clearDayPackage().catch(error => {
  console.error(error);
  dayStatus.textContent = `日次削除失敗: ${error.message}`;
}));
dayRaceSelect.addEventListener("change", () => activateDayRace(dayRaceSelect.value));
window.addEventListener("load", () => restoreDayPackage().catch(error => console.error(error)));
