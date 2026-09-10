"use strict";

/* Newspaper display v8: expose EdgeDB merge readiness in the day summary. */

dayPackageSummary = function (value) {
  if (!value || !value.manifest) {
    return "新聞データなし";
  }

  const sources = value.manifest.source_status || {};
  const evalState = sources.eval && sources.eval.state === "READY" ? "Eval○" : "Eval—";
  const rnState = sources.racenote_prediction && sources.racenote_prediction.state === "READY" ? "RN○" : "RN—";
  const ilukaState = sources.keibailuka && sources.keibailuka.state === "READY" ? "🐬○" : "🐬—";
  const edgeState = sources.edge && sources.edge.state === "READY" ? "Edge○" : "Edge—";
  const count = Array.isArray(value.races) ? value.races.length : 0;

  return `${value.manifest.date} / ${count}R / ${evalState} / ${rnState} / ${ilukaState} / ${edgeState}`;
};
