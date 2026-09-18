const arrow = window.Arrow;

if (!arrow || !arrow.RecordBatchReader || !arrow.Table || !arrow.tableToIPC) {
  throw new Error("Fact Lite Arrow runtimeが読み込めません");
}

export const RecordBatchReader = arrow.RecordBatchReader;
export const Table = arrow.Table;
export const tableToIPC = arrow.tableToIPC;
