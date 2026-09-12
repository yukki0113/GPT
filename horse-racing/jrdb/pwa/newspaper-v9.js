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

function newspaperV9EvalCodes(analysis) {
  if (!analysis) return [];
  if (Array.isArray(analysis.codes)) {
    return analysis.codes
      .map(value => text(value, "").trim())
      .filter(Boolean);
  }
  const fallback = text(analysis.codes, "").trim();
  return fallback ? [fallback] : [];
}

function newspaperV9ShowEvalDetail(horse) {
  const addon = newspaperV9EvalAddon(horse);
  const analysis = newspaperV9EvalAnalysis(horse);
  if (!addon || !analysis) return;

  const horseName = text(horse && horse.basic && horse.basic.horse_name, "");
  const evalValue = newspaperV9EvalValue(horse);
  const title = text(analysis.title, "").trim();
  const comment = text(analysis.comment, "").trim();
  const codes = newspaperV9EvalCodes(analysis);
  const status = text(analysis.status, "").trim();
  const version = text(analysis.version, "").trim();
  const asof = text(analysis.asof, "").trim();

  const detailRows = [
    ["条件コード", codes.length ? codes.join(" / ") : "—"],
    ["status", status],
    ["version", version],
    ["as-of", asof]
  ].filter(([, value]) => value !== null && value !== undefined && value !== "");

  dialogTitle.textContent = `${horseName} / Eval ${evalValue}`;
  dialogBody.innerHTML = `
    <div class="newspaper-eval-analysis">
      ${title ? `<h3 class="newspaper-eval-analysis-title">${escapeHtml(title)}</h3>` : ""}
      <p class="newspaper-addon-comment newspaper-eval-analysis-comment">${escapeHtml(comment)}</p>
      <dl class="newspaper-detail-list newspaper-eval-analysis-meta">${
        detailRows.map(([label, value]) =>
          `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(text(value))}</dd></div>`
        ).join("")
      }</dl>
    </div>`;

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
