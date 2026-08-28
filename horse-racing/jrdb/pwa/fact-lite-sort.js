"use strict";

const FACT_RESULT_LIMIT = 200;

const FACT_SORTABLE_COLUMNS = [
  { key: "starts", label: "出走", index: 1 },
  { key: "win_rate", label: "勝率", index: 2 },
  { key: "top3_rate", label: "複勝率", index: 3 },
  { key: "win_return", label: "単回", index: 4 },
  { key: "place_return", label: "複回", index: 5 }
];

const FACT_AXIS_ITEM_ORDER = {
  frame: ["1", "2", "3", "4", "5", "6", "7", "8", "不明"],
  style: ["逃げ", "先行", "好位差し", "差し", "追込", "自在", "不明"],
  sex: ["牡", "牝", "セン", "不明"],
  popularity: ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10～", "不明"],
  distance_change: ["距離延長", "同距離", "距離短縮", "前走不明"],
  prev_class: [
    "新馬",
    "未出走",
    "未勝利",
    "1勝",
    "2勝",
    "3勝",
    "オープン",
    "L",
    "G3",
    "G2",
    "G1",
    "その他重賞",
    "その他",
    "前走不明"
  ]
};

let factResultSortKey = "default";
let factResultSortDirection = "desc";
let factResultSortAxis = null;

function getFactResultActiveAxis() {
  const activeTab = document.querySelector("#fact-tabs .tab.active");
  if (!activeTab) {
    return "sire";
  }
  return activeTab.dataset.axis || "sire";
}

function parseFactResultNumber(text) {
  const normalized = String(text).replaceAll(",", "").replace("%", "").trim();
  const value = Number(normalized);
  if (Number.isNaN(value)) {
    return Number.NEGATIVE_INFINITY;
  }
  return value;
}

function getFactRowItem(row) {
  return row.cells[0] ? row.cells[0].textContent.trim() : "";
}

function getFactRowNumericValue(row, columnIndex) {
  if (!row.cells[columnIndex]) {
    return Number.NEGATIVE_INFINITY;
  }
  return parseFactResultNumber(row.cells[columnIndex].textContent);
}

function compareFactText(left, right) {
  return left.localeCompare(right, "ja", { numeric: true, sensitivity: "base" });
}

function compareFactDefaultRows(left, right, axis) {
  const leftItem = getFactRowItem(left);
  const rightItem = getFactRowItem(right);

  if (axis === "sire" || axis === "jockey") {
    const startsDifference = getFactRowNumericValue(right, 1) - getFactRowNumericValue(left, 1);
    if (startsDifference !== 0) {
      return startsDifference;
    }
    return compareFactText(leftItem, rightItem);
  }

  if (axis === "age") {
    const leftAge = parseFactResultNumber(leftItem);
    const rightAge = parseFactResultNumber(rightItem);
    if (leftAge !== rightAge) {
      return leftAge - rightAge;
    }
    return compareFactText(leftItem, rightItem);
  }

  const itemOrder = FACT_AXIS_ITEM_ORDER[axis];
  if (itemOrder) {
    const leftIndex = itemOrder.indexOf(leftItem);
    const rightIndex = itemOrder.indexOf(rightItem);
    const normalizedLeftIndex = leftIndex === -1 ? itemOrder.length : leftIndex;
    const normalizedRightIndex = rightIndex === -1 ? itemOrder.length : rightIndex;
    if (normalizedLeftIndex !== normalizedRightIndex) {
      return normalizedLeftIndex - normalizedRightIndex;
    }
  }

  return compareFactText(leftItem, rightItem);
}

function compareFactMetricRows(left, right, columnIndex, direction) {
  const leftValue = getFactRowNumericValue(left, columnIndex);
  const rightValue = getFactRowNumericValue(right, columnIndex);
  const difference = leftValue - rightValue;

  if (difference !== 0) {
    return direction === "asc" ? difference : -difference;
  }

  const startsDifference = getFactRowNumericValue(right, 1) - getFactRowNumericValue(left, 1);
  if (startsDifference !== 0) {
    return startsDifference;
  }

  return compareFactText(getFactRowItem(left), getFactRowItem(right));
}

function updateFactSortHeaderState(table) {
  const buttons = table.querySelectorAll("button.fact-sort-button");
  buttons.forEach(function (button) {
    const columnKey = button.dataset.sortKey;
    const baseLabel = button.dataset.sortLabel;
    button.classList.remove("active");
    button.removeAttribute("aria-sort");
    button.textContent = baseLabel;

    if (factResultSortKey !== columnKey) {
      return;
    }

    const arrow = factResultSortDirection === "asc" ? "▲" : "▼";
    button.classList.add("active");
    button.setAttribute(
      "aria-sort",
      factResultSortDirection === "asc" ? "ascending" : "descending"
    );
    button.textContent = baseLabel + " " + arrow;
  });
}

function renderFactSortedRows(table) {
  const tbody = table.tBodies[0];
  if (!tbody) {
    return;
  }

  const axis = getFactResultActiveAxis();
  const rows = Array.from(tbody.querySelectorAll("tr"));

  if (!table._factAllRows || table._factAllRows.length < rows.length) {
    table._factAllRows = rows;
  }

  const allRows = Array.from(table._factAllRows || rows);
  if (factResultSortKey === "default") {
    allRows.sort(function (left, right) {
      return compareFactDefaultRows(left, right, axis);
    });
  } else {
    const column = FACT_SORTABLE_COLUMNS.find(function (candidate) {
      return candidate.key === factResultSortKey;
    });
    if (column) {
      allRows.sort(function (left, right) {
        return compareFactMetricRows(left, right, column.index, factResultSortDirection);
      });
    }
  }

  tbody.replaceChildren();
  allRows.slice(0, FACT_RESULT_LIMIT).forEach(function (row) {
    tbody.appendChild(row);
  });

  updateFactSortHeaderState(table);
}

function configureFactResultSorting(table) {
  const axis = getFactResultActiveAxis();
  if (factResultSortAxis !== axis) {
    factResultSortAxis = axis;
    factResultSortKey = "default";
    factResultSortDirection = "desc";
  }

  if (table.dataset.sortEnhanced === "1") {
    return;
  }

  table.dataset.sortEnhanced = "1";
  const tbody = table.tBodies[0];
  table._factAllRows = tbody ? Array.from(tbody.querySelectorAll("tr")) : [];

  const headers = table.tHead ? Array.from(table.tHead.rows[0].cells) : [];
  FACT_SORTABLE_COLUMNS.forEach(function (column) {
    const header = headers[column.index];
    if (!header) {
      return;
    }

    const button = document.createElement("button");
    button.type = "button";
    button.className = "fact-sort-button";
    button.dataset.sortKey = column.key;
    button.dataset.sortLabel = column.label;
    button.textContent = column.label;
    button.setAttribute("aria-label", column.label + "で並び替え");
    button.addEventListener("click", function () {
      if (factResultSortKey === column.key) {
        factResultSortDirection = factResultSortDirection === "desc" ? "asc" : "desc";
      } else {
        factResultSortKey = column.key;
        factResultSortDirection = "desc";
      }
      renderFactSortedRows(table);
    });

    header.textContent = "";
    header.appendChild(button);
  });

  renderFactSortedRows(table);
}

function refreshFactResultSorting() {
  const table = document.querySelector("#fact-result-area table");
  if (!table) {
    return;
  }
  configureFactResultSorting(table);
}

const factResultObserver = new MutationObserver(function () {
  refreshFactResultSorting();
});

factResultObserver.observe(document.getElementById("fact-result-area"), {
  childList: true,
  subtree: true
});

refreshFactResultSorting();
