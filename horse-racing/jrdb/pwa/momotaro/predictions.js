"use strict";

const PREDICTION_CURRENT_BASE = "./data/newspaper/current/";
const predictionStatus = document.getElementById("prediction-status");
const predictionList = document.getElementById("prediction-list");
const predictionRefresh = document.getElementById("prediction-refresh");
const predictionNetworkBadge = document.getElementById("prediction-network-badge");
const predictionFilters = Array.from(document.querySelectorAll("[data-filter]"));

let predictionRows = [];
let activePredictionFilter = "all";

function predictionText(value, fallback) {
  if (value === null || value === undefined || value === "") return fallback || "";
  return String(value);
}

function predictionEscape(value) {
  return predictionText(value, "").replace(/[&<>"']/g, function (character) {
    return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[character];
  });
}

function predictionPublishedUrl(path) {
  return new URL(path, new URL(PREDICTION_CURRENT_BASE, window.location.href)).toString();
}

function extractIluka(addons) {
  const value = addons && addons.keibailuka ? addons.keibailuka : null;
  if (!value) return null;
  const label = predictionText(value.display_value || value.label || value.mark || value.value, "");
  const comment = predictionText(value.comment || value.memo || value.title, "");
  if (!label && !comment) return null;
  return { label: label || "対象", comment: comment };
}

function collectRows(bundle) {
  const race = bundle.race || {};
  const rows = [];
  (bundle.horses || []).forEach(function (horse) {
    const addons = horse.addons || {};
    const momotaro = addons.momotaro || {};
    const identity = horse.identity || {};
    const key = horse.key || {};
    const base = {
      race_key: predictionText(race.race_key, ""),
      venue: predictionText(race.venue, ""),
      race_no: predictionText(race.race_no, ""),
      race_name: predictionText(race.race_name, ""),
      horse_no: predictionText(key.horse_no, ""),
      horse_name: predictionText(identity.horse_name, "")
    };

    const ryota = momotaro.ryota || {};
    if (predictionText(ryota.confidence, "").toUpperCase() === "S") {
      rows.push(Object.assign({}, base, {
        type: "ryota-s",
        source: "りょーた",
        label: "自信度 S",
        mark: predictionText(ryota.mark, ""),
        comment: predictionText(ryota.comment, "")
      }));
    }

    const oji = momotaro.oji || {};
    if (oji.review_horse === true) {
      rows.push(Object.assign({}, base, {
        type: "oji-review",
        source: "おーじ",
        label: "回顧馬",
        mark: predictionText(oji.mark, ""),
        comment: predictionText(oji.comment, "")
      }));
    }

    const iluka = extractIluka(addons);
    if (iluka) {
      rows.push(Object.assign({}, base, {
        type: "keibailuka",
        source: "イルカ",
        label: iluka.label,
        mark: "",
        comment: iluka.comment
      }));
    }
  });
  return rows;
}

function renderPredictionRows() {
  const visible = activePredictionFilter === "all"
    ? predictionRows
    : predictionRows.filter(function (row) { return row.type === activePredictionFilter; });

  if (visible.length === 0) {
    predictionList.innerHTML = '<div class="empty-state">該当する予想データはありません。</div>';
    return;
  }

  predictionList.innerHTML = visible.map(function (row) {
    const raceTitle = predictionEscape(row.venue + " " + row.race_no + "R" + (row.race_name ? " " + row.race_name : ""));
    const horse = predictionEscape(row.horse_no + " " + row.horse_name);
    const mark = row.mark ? " / " + predictionEscape(row.mark) : "";
    return '<article class="momotaro-horse-card">' +
      '<div class="query-status">' + raceTitle + '</div>' +
      '<strong>' + predictionEscape(row.source) + " " + predictionEscape(row.label) + mark + '</strong>' +
      '<div>' + horse + '</div>' +
      (row.comment ? '<div class="momotaro-comment">' + predictionEscape(row.comment) + '</div>' : '') +
      '</article>';
  }).join("");
}

async function refreshPredictions() {
  if (!navigator.onLine) {
    predictionStatus.textContent = "オフラインです。";
    return;
  }

  predictionRefresh.disabled = true;
  predictionStatus.textContent = "最新データを確認中…";
  try {
    const manifestResponse = await fetch(predictionPublishedUrl("manifest.json") + "?t=" + Date.now(), {cache:"no-store"});
    if (!manifestResponse.ok) throw new Error("manifest HTTP " + manifestResponse.status);
    const manifest = await manifestResponse.json();
    if (!Array.isArray(manifest.races)) throw new Error("manifest.races がありません");

    const bundles = await Promise.all(manifest.races.map(async function (entry) {
      const response = await fetch(predictionPublishedUrl(entry.path) + "?t=" + Date.now(), {cache:"no-store"});
      if (!response.ok) throw new Error(entry.path + " HTTP " + response.status);
      return response.json();
    }));

    predictionRows = bundles.flatMap(collectRows);
    renderPredictionRows();
    predictionStatus.textContent = predictionText(manifest.date, "") + " / " + predictionRows.length + "件";
  } catch (error) {
    console.error(error);
    predictionStatus.textContent = "取得失敗: " + error.message;
  } finally {
    predictionRefresh.disabled = false;
  }
}

function updatePredictionNetwork() {
  const online = navigator.onLine;
  predictionNetworkBadge.textContent = online ? "オンライン" : "オフライン";
  predictionNetworkBadge.classList.toggle("online", online);
  predictionNetworkBadge.classList.toggle("offline", !online);
}

predictionFilters.forEach(function (button) {
  button.addEventListener("click", function () {
    activePredictionFilter = button.dataset.filter || "all";
    renderPredictionRows();
  });
});
predictionRefresh.addEventListener("click", refreshPredictions);
window.addEventListener("online", updatePredictionNetwork);
window.addEventListener("offline", updatePredictionNetwork);
updatePredictionNetwork();
refreshPredictions();
