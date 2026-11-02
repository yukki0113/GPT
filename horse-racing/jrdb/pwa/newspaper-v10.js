"use strict";

/* Personal newspaper delivery summary. */

dayPackageSummary = function (value) {
  if (!value || !value.manifest) return "新聞データなし";

  const sources = value.manifest.source_status || {};
  const evalState = sources.eval && sources.eval.state === "READY" ? "Eval○" : "Eval—";
  const ilukaState = sources.keibailuka && sources.keibailuka.state === "READY" ? "🐬○" : "🐬—";
  const count = Array.isArray(value.races) ? value.races.length : 0;

  return `${value.manifest.date} / ${count}R / ${evalState} / ${ilukaState}`;
};
