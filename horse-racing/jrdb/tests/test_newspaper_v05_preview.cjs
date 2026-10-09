const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../pwa/newspaper-v05-preview.js'), 'utf8');
let opened = 0;
const created = [];
const context = vm.createContext({
  currentBundle: null,
  tableWrap: null,
  dialogTitle: { textContent: '' },
  dialogBody: { innerHTML: '' },
  detailDialog: { showModal() { opened += 1; } },
  renderTable() {},
  dayPackageSummary() { return 'day'; },
  refreshPublishedDay() {},
  currentDayPackage: null,
  dayStatus: { textContent: '' },
  document: { createElement(tag) {
    const element = { tag, children: [], appendChild(child) { this.children.push(child); },
      setAttribute(name, value) { this[name] = value; }, addEventListener() {} };
    created.push(element);
    return element;
  } },
  text(value, fallback = '—') { return value === null || value === undefined || value === '' ? fallback : String(value); },
  escapeHtml(value) { return String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;'); }
});
vm.runInContext(source, context);
const detail = (id, family) => ({ candidate_id: id, family, condition_text: `${id}の条件`, oos_tier: 'CONFIRMED',
  discovery: { n: 10, place_rate: 0.3, place_roi: 120 }, oos_2026: { n: 5, place_rate: 0.4, place_roi: 130 } });
context.currentBundle = { metadata: { source_status: { edge_v05: { state: 'PARTIAL' } } },
  edge_v05_candidates: { a: detail('a', 'T1'), b: detail('b', 'T2'), c: detail('c', 'T3') } };
const horse = ids => ({ basic: { horse_name: 'テスト馬' }, special_memos: [{ edge_id: 'v02' }],
  addons: { edge_v05: { candidate_ids: ids } } });
assert.equal(vm.runInContext('newspaperV05Ids', context)(horse([])).length, 0);
assert.equal(vm.runInContext('newspaperV05Ids', context)(horse(['a'])).length, 1);
assert.equal(vm.runInContext('newspaperV05Ids', context)(horse(['a', 'b', 'c'])).length, 3);
vm.runInContext('newspaperV05ShowDetail', context)(horse(['a', 'b', 'c']));
assert.equal(opened, 1);
assert.equal(context.dialogTitle.textContent, 'テスト馬 / Edge 3件');
assert.match(context.dialogBody.innerHTML, /その他のEdge（1件）/);
assert.equal((context.dialogBody.innerHTML.match(/class="newspaper-v05-detail"/g) || []).length, 3);
assert.ok(context.dialogBody.innerHTML.indexOf('cの条件') > context.dialogBody.innerHTML.indexOf('その他のEdge'));
context.currentBundle.metadata.source_status.edge_v05.state = 'ERROR';
assert.equal(vm.runInContext('newspaperV05Ids', context)(horse(['a'])).length, 0);
context.currentBundle.metadata.source_status.edge_v05.state = 'READY';
assert.equal(vm.runInContext('newspaperV05Ids', context)(horse(['a'])).length, 1);
assert.equal(vm.runInContext('newspaperV05Metric', context)(0, null, 'rate'), '未観測');
assert.equal(vm.runInContext('newspaperV05Metric', context)(5, null, 'roi'), '算出不可');
context.currentBundle.metadata.source_status.edge_v05.state = 'PARTIAL';
context.currentBundle.horses = [horse([]), horse(['a']), horse(['a', 'b', 'c'])]
  .map((item, i) => ({ ...item, key: { horse_no: i + 1 } }));
let removed = 0;
const groupHead = { colSpan: 6 };
const headRow = { querySelector() { return null; }, appendChild() {} };
const rows = [0, 1, 2].map(() => ({ inserted: [], querySelector() { return {}; },
  insertBefore(cell) { this.inserted.push(cell); }, appendChild(cell) { this.inserted.push(cell); } }));
const table = { querySelector(selector) { return selector === '.newspaper-mark-group-head' ? groupHead : headRow; },
  querySelectorAll(selector) { return selector === '.newspaper-edge' ? [{ remove() { removed++; } }] : rows; } };
context.tableWrap = { querySelector() { return table; } };
vm.runInContext('newspaperV05ApplyColumn', context)();
assert.equal(removed, 1);
assert.equal(groupHead.colSpan, 7);
assert.equal(rows[0].inserted[0].children.length, 0);
assert.equal(rows[1].inserted[0].children[0].textContent, '○');
assert.equal(rows[2].inserted[0].children[0].textContent, '○');
console.log('v0.5 preview UI contract: PASS');
