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
// Mirror the v4 output: seven mark heads, a separate two-row Edge head,
// and a separate Edge cell in every horse row. v6 removes mark-my later.
const v4Source = fs.readFileSync(path.join(__dirname, '../pwa/newspaper-v4.js'), 'utf8');
assert.match(v4Source, /class="newspaper-mark-group-head" colspan="7"/);
assert.match(v4Source, /<th class="newspaper-edge" rowspan="2">Edge<\/th>/);
assert.match(v4Source, /<td class="newspaper-edge">\$\{edgeHtml\(horse\)\}<\/td>/);
const v4Marks = ['ability', 'training', 'jrdb', 'eval', 'rn', 'iluka', 'my'];
function node(tag, className = '') {
  return {
    tag, className, children: [], parent: null,
    setAttribute(name, value) { this[name] = value; },
    addEventListener() {},
    get parentElement() { return this.parent; },
    appendChild(child) {
      if (child.parent) child.remove();
      this.children.push(child); child.parent = this;
    },
    insertBefore(child, anchor) {
      if (child.parent) child.remove();
      this.children.splice(this.children.indexOf(anchor), 0, child); child.parent = this;
    },
    remove() {
      if (this.parent) this.parent.children.splice(this.parent.children.indexOf(this), 1);
      this.parent = null;
    },
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; },
    querySelectorAll(selector) {
      if (selector === 'tbody tr') return this.querySelector('tbody').children;
      const selectors = selector.split(',').map(part => part.trim().split(' ').pop());
      const result = [];
      const visit = current => {
        for (const child of current.children) {
          if (selectors.some(part => {
            const [wantedTag, ...classes] = part.split('.');
            return (!wantedTag || child.tag === wantedTag) && classes.every(name => child.className.split(' ').includes(name));
          })) result.push(child);
          visit(child);
        }
      };
      visit(this);
      return result;
    }
  };
}
context.document.createElement = tag => node(tag);
function fixture(markNames) {
  const table = node('table', 'newspaper-table-v4');
  const thead = node('thead'); table.appendChild(thead);
  const firstHead = node('tr'); thead.appendChild(firstHead);
  for (let i = 0; i < 4; i++) firstHead.appendChild(node('th'));
  const groupHead = node('th', 'newspaper-mark-group-head');
  groupHead.colSpan = markNames.length; firstHead.appendChild(groupHead);
  firstHead.appendChild(node('th', 'newspaper-history-head'));
  firstHead.appendChild(node('th', 'newspaper-edge'));
  const markHead = node('tr', 'newspaper-mark-head-row'); thead.appendChild(markHead);
  markNames.forEach(name => markHead.appendChild(node('th', `newspaper-mark-col mark-${name}`)));
  const tbody = node('tbody'); table.appendChild(tbody);
  const rows = [0, 1, 2].map(() => {
    const row = node('tr'); tbody.appendChild(row);
    for (let i = 0; i < 4; i++) row.appendChild(node('td'));
    markNames.forEach(name => row.appendChild(node('td', `newspaper-mark-col mark-${name}`)));
    row.appendChild(node('td', 'newspaper-history-cell'));
    row.appendChild(node('td', 'newspaper-edge'));
    return row;
  });
  return { table, firstHead, groupHead, markHead, rows };
}
for (const markNames of [v4Marks, v4Marks.filter(name => name !== 'my')]) {
  const { table, firstHead, groupHead, markHead, rows } = fixture(markNames);
  assert.equal(table.querySelector('.newspaper-mark-head-row'), markHead);
  assert.notEqual(firstHead, markHead);
  context.tableWrap = { querySelector() { return table; } };
  vm.runInContext('newspaperV05ApplyColumn', context)();
  assert.equal(firstHead.querySelectorAll('.newspaper-edge').length, 0,
    JSON.stringify(firstHead.children.map(child => child.className)));
  assert.equal(table.querySelectorAll('.newspaper-edge').length, 0);
  assert.equal(groupHead.colSpan, markNames.length);
  assert.equal(markHead.querySelectorAll('th.mark-edge').length, 0);
  assert.equal(firstHead.querySelectorAll('th.mark-edge').length, 1);
  assert.equal(firstHead.querySelector('th.mark-edge').rowSpan, 2);
  assert.equal(markHead.querySelectorAll('th.newspaper-mark-col').length, groupHead.colSpan);
  assert.equal(firstHead.children.length - 1 + groupHead.colSpan, rows[0].children.length,
    `first head ${JSON.stringify(firstHead.children.map(child => child.className))}, mark span ${groupHead.colSpan}, body ${rows[0].children.length}`);
  rows.forEach(row => {
    assert.equal(row.children.length, rows[0].children.length);
    assert.equal(row.querySelectorAll('td.mark-edge').length, 1);
  });
  assert.equal(rows[0].querySelector('td.mark-edge').children.length, 0);
  assert.equal(rows[1].querySelector('td.mark-edge').children[0].textContent, '○');
  assert.equal(rows[2].querySelector('td.mark-edge').children[0].textContent, '○');
  vm.runInContext('newspaperV05ApplyColumn', context)();
  assert.equal(markHead.querySelectorAll('th.mark-edge').length, 0);
  assert.equal(firstHead.querySelectorAll('th.mark-edge').length, 1);
  rows.forEach(row => assert.equal(row.querySelectorAll('td.mark-edge').length, 1));
}
console.log('v0.5 preview UI contract: PASS');
