"use strict";

/* Newspaper display v6: restore training column in the requested seven-column order. */

function newspaperV6ApplyMarkLayout() {
  if (!currentBundle || !tableWrap) return;
  const horses = [...currentBundle.horses].sort((a, b) => Number(a.key.horse_no) - Number(b.key.horse_no));
  const table = tableWrap.querySelector(".newspaper-table-v4");
  if (!table) return;

  const groupHead = table.querySelector(".newspaper-mark-group-head");
  if (groupHead) groupHead.colSpan = 7;

  const headRow = table.querySelector(".newspaper-mark-head-row");
  if (headRow) {
    let trainingHead = headRow.querySelector(".mark-training");
    if (!trainingHead) {
      trainingHead = document.createElement("th");
      trainingHead.className = "newspaper-mark-col mark-training";
    }
    trainingHead.textContent = "追切";

    const myHead = headRow.querySelector(".mark-my");
    if (myHead) myHead.textContent = "独自";

    const orderedHeads = [
      headRow.querySelector(".mark-ability"),
      myHead,
      headRow.querySelector(".mark-eval"),
      trainingHead,
      headRow.querySelector(".mark-jrdb"),
      headRow.querySelector(".mark-rn"),
      headRow.querySelector(".mark-iluka")
    ];
    for (const cell of orderedHeads) {
      if (cell) headRow.appendChild(cell);
    }
  }

  const bodyRows = table.querySelectorAll("tbody tr");
  bodyRows.forEach((row, index) => {
    const horse = horses[index];
    if (!horse) return;

    let trainingCell = row.querySelector(".mark-training");
    if (!trainingCell) {
      trainingCell = document.createElement("td");
      trainingCell.className = "newspaper-mark-col mark-training";
    }
    const training = newspaperV4TrainingValue(horse);
    trainingCell.textContent = training.display && training.display !== "—"
      ? training.display
      : newspaperV5IntrinsicValue(null, "jrdb_base");
    trainingCell.title = training.title || "JRDB追切";

    const orderedCells = [
      row.querySelector(".mark-ability"),
      row.querySelector(".mark-my"),
      row.querySelector(".mark-eval"),
      trainingCell,
      row.querySelector(".mark-jrdb"),
      row.querySelector(".mark-rn"),
      row.querySelector(".mark-iluka")
    ];
    const anchor = row.querySelector(".newspaper-history-cell") || row.querySelector(".newspaper-edge");
    for (const cell of orderedCells) {
      if (cell && anchor) row.insertBefore(cell, anchor);
    }
  });
}

const newspaperV6BaseRenderTable = renderTable;
renderTable = function () {
  newspaperV6BaseRenderTable();
  newspaperV6ApplyMarkLayout();
};

window.addEventListener("load", () => {
  if (currentBundle) newspaperV6ApplyMarkLayout();
});
