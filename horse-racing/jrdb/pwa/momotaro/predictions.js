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
  const comment = predictionText(value.comment || value.memo || value.title, "");
  if (!comment) return null;
  return { comment: comment };
}

function collectRows(bundle) {
  const race = bundle.race || {};
  const rows = [];
  (bundle.horses || []).forEach(function (horse) {
    const addons = horse.addons || {};
    const momotaro = addons.momotaro || {};
    const basic = horse.basic || {};
    const key = horse.key || {};
    const base = {
      race_key: predictionText(race.race_key, ""),
      venue: predictionText(race.venue, ""),
      race_no: Number(race.race_no || 0),
      race_name: predictionText(race.race_name, ""),
      horse_no: Number(key.horse_no || 0),
      horse_name: predictionText(basic.horse_name, "")
    };

    const ryota = momotaro.ryota || {};
    if (predictionText(ryota.confidence, "").toUpperCase() === "S") {
      rows.push(Object.assign({}, base, {
        type: "ryota-s",
        source: "りょーた",
        source_order: 2,
        signal: "次走注目S",
        mark: predictionText(ryota.mark, ""),
        comment: predictionText(ryota.comment, "")
      }));
    }

    const oji = momotaro.oji || {};
    if (oji.review_horse === true) {
      rows.push(Object.assign({}, base, {
        type: "oji-review",
        source: "王子",
        source_order: 3,
        signal: "回顧馬",
        mark: predictionText(oji.mark, ""),
        comment: predictionText(oji.comment, "")
      }));
    }

    const iluka = extractIluka(addons);
    if (iluka) {
      rows.push(Object.assign({}, base, {
        type: "keibailuka",
        source: "🐬",
        source_order: 1,
        signal: "",
        mark: "",
        comment: iluka.comment
      }));
    }
  });
  return rows;
}

function groupVisibleRows() {
  const visible = activePredictionFilter === "all"
    ? predictionRows
    : predictionRows.filter(function (row) { return row.type === activePredictionFilter; });

  const races = new Map();
  visible.forEach(function (row) {
    const raceKey = row.race_key || row.venue + "-" + row.race_no;
    if (!races.has(raceKey)) {
      races.set(raceKey, {
        race_key: raceKey,
        venue: row.venue,
        race_no: row.race_no,
        race_name: row.race_name,
        rows: []
      });
    }
    races.get(raceKey).rows.push(row);
  });

  return Array.from(races.values()).sort(function (left, right) {
    if (left.venue !== right.venue) return left.venue.localeCompare(right.venue, "ja");
    return Number(left.race_no) - Number(right.race_no);
  });
}

function renderSourceGroup(rows) {
  const sorted = [...rows].sort(function (left, right) {
    if (left.source_order !== right.source_order) return left.source_order - right.source_order;
    return Number(left.horse_no) - Number(right.horse_no);
  });

  const sourceBuckets = new Map();
  sorted.forEach(function (row) {
    if (!sourceBuckets.has(row.source)) sourceBuckets.set(row.source, []);
    sourceBuckets.get(row.source).push(row);
  });

  return Array.from(sourceBuckets.entries()).map(function (entry) {
    const source = entry[0];
    const items = entry[1];
    const itemHtml = items.map(function (row) {
      const horseLine =
        predictionEscape(row.horse_no + "番 " + row.horse_name) +
        (row.signal ? '<span class="momotaro-signal">：' + predictionEscape(row.signal) + '</span>' : "");
      const mark = row.mark ? '<span class="momotaro-list-mark">' + predictionEscape(row.mark) + '</span>' : "";
      const comment = row.comment
        ? '<div class="momotaro-prediction-comment">' + predictionEscape(row.comment) + '</div>'
        : "";

      return '<div class="momotaro-prediction-item">' +
        '<div class="momotaro-prediction-horse">' + mark + horseLine + '</div>' +
        comment +
        '</div>';
    }).join("");

    return '<section class="momotaro-source-group">' +
      '<div class="momotaro-source-label">' + predictionEscape(source) + '</div>' +
      itemHtml +
      '</section>';
  }).join("");
}

function renderPredictionRows() {
  const races = groupVisibleRows();

  if (races.length === 0) {
    predictionList.innerHTML = '<div class="empty-state">該当する予想データはありません。</div>';
    return;
  }

  predictionList.innerHTML = races.map(function (race) {
    const raceTitle = predictionEscape(race.venue + " " + race.race_no + "R");
    const raceName = race.race_name
      ? '<div class="momotaro-race-name">' + predictionEscape(race.race_name) + '</div>'
      : "";

    return '<article class="momotaro-race-card">' +
      '<header class="momotaro-race-header">' +
        '<strong>' + raceTitle + '</strong>' +
        raceName +
      '</header>' +
      renderSourceGroup(race.rows) +
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
    predictionFilters.forEach(function (target) {
      target.classList.toggle("active", target === button);
    });
    renderPredictionRows();
  });
});
predictionRefresh.addEventListener("click", refreshPredictions);
window.addEventListener("online", updatePredictionNetwork);
window.addEventListener("offline", updatePredictionNetwork);
updatePredictionNetwork();
refreshPredictions();
