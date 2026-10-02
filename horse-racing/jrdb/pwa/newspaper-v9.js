"use strict";

/* Newspaper display v9: expose Eval analysis only when the supplied comment is non-empty. */

function newspaperV9EvalAddon(horse) {
  if (!horse || !horse.addons || !horse.addons.eval || typeof horse.addons.eval !== "object") {
    return null;
  }
  return horse.addons.eval;
}

function newspaperV9EvalAnalysis(horse) {
  const addon = newspaperV9EvalAddon(horse);
  if (!addon || !addon.analysis || typeof addon.analysis !== "object") {
    return null;
  }
  const comment = text(addon.analysis.comment, "").trim();
  if (!comment) {
    return null;
  }
  return addon.analysis;
}

function newspaperV9EvalValue(horse) {
  const addon = newspaperV9EvalAddon(horse);
  return newspaperV2AddonDisplay(addon, ["eval", "score", "index", "value"]);
}

function newspaperV9ShowEvalDetail(horse) {
  const addon = newspaperV9EvalAddon(horse);
  const analysis = newspaperV9EvalAnalysis(horse);
  if (!addon || !analysis) return;

  const horseName = text(horse && horse.basic && horse.basic.horse_name, "");
  const evalValue = newspaperV9EvalValue(horse);
  const comment = text(analysis.comment, "").trim();

  dialogTitle.textContent = `${horseName} / Eval ${evalValue}`;
  dialogBody.innerHTML =
    '<p class="newspaper-addon-comment newspaper-eval-analysis-comment">' +
    escapeHtml(comment) +
    '</p>';

  if (typeof detailDialog.showModal === "function") {
    detailDialog.showModal();
  } else {
    detailDialog.setAttribute("open", "");
  }
}

function newspaperV9ApplyEvalLinks() {
  if (!currentBundle || !Array.isArray(currentBundle.horses) || !tableWrap) return;

  const horses = [...currentBundle.horses].sort(
    (a, b) => Number(a && a.key && a.key.horse_no) - Number(b && b.key && b.key.horse_no)
  );
  const rows = tableWrap.querySelectorAll("tbody tr");

  rows.forEach((row, index) => {
    const horse = horses[index];
    const cell = row.querySelector(".mark-eval");
    if (!horse || !cell) return;

    const analysis = newspaperV9EvalAnalysis(horse);
    if (!analysis) return;

    const evalValue = newspaperV9EvalValue(horse);
    const horseName = text(horse && horse.basic && horse.basic.horse_name, "");
    cell.innerHTML = `<button type="button" class="newspaper-addon-link newspaper-eval-analysis-link" data-horse-index="${index}" aria-label="${escapeHtml(horseName)}のEval分析を開く">${escapeHtml(evalValue)}</button>`;
  });

  tableWrap.querySelectorAll(".newspaper-eval-analysis-link").forEach(button => {
    if (button.dataset.evalAnalysisBound === "1") return;
    button.dataset.evalAnalysisBound = "1";
    button.addEventListener("click", () => {
      const horse = horses[Number(button.dataset.horseIndex)];
      if (horse) newspaperV9ShowEvalDetail(horse);
    });
  });
}

const newspaperV9RenderTableBase = renderTable;
renderTable = function () {
  newspaperV9RenderTableBase();
  newspaperV9ApplyEvalLinks();
};

window.addEventListener("load", () => {
  if (currentBundle) newspaperV9ApplyEvalLinks();
});
