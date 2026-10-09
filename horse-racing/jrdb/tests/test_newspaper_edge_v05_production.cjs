const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '../pwa');
const source = fs.readFileSync(path.join(root, 'newspaper-edge-v05.js'), 'utf8');
const html = fs.readFileSync(path.join(root, 'newspaper.html'), 'utf8');
assert.ok(html.indexOf('newspaper-momotaro.js') < html.indexOf('newspaper-edge-v05.js'));
assert.doesNotMatch(html, /newspaper-v05-preview\.(js|css)/);

function node(tag, className = '') {
  return {
    tag, className, children: [], parentElement: null, listeners: {},
    appendChild(child) { if (child.parentElement) child.remove(); this.children.push(child); child.parentElement = this; },
    insertBefore(child, anchor) { if (child.parentElement) child.remove(); this.children.splice(this.children.indexOf(anchor), 0, child); child.parentElement = this; },
    remove() { if (this.parentElement) this.parentElement.children.splice(this.parentElement.children.indexOf(this), 1); this.parentElement = null; },
    setAttribute(name, value) { this[name] = value; },
    addEventListener(name, listener) { this.listeners[name] = listener; },
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; },
    querySelectorAll(selector) {
      if (selector === 'tbody tr') return this.querySelector('tbody').children;
      const parts = selector.split(',').map(part => part.trim().split(' ').pop());
      const found = [];
      const visit = parent => parent.children.forEach(child => {
        if (parts.some(part => {
          const [tagName, ...classes] = part.split('.');
          return (!tagName || tagName === child.tag) && classes.every(name => child.className.split(' ').includes(name));
        })) found.push(child);
        visit(child);
      });
      visit(this);
      return found;
    }
  };
}
function fixture() {
  const table = node('table', 'newspaper-table-v4');
  const thead = node('thead'); table.appendChild(thead);
  const top = node('tr'); thead.appendChild(top);
  for (let i = 0; i < 4; i++) top.appendChild(node('th'));
  const group = node('th', 'newspaper-mark-group-head'); group.colSpan = 8; top.appendChild(group);
  for (let i = 0; i < 3; i++) top.appendChild(node('th', 'newspaper-history-head'));
  top.appendChild(node('th', 'newspaper-edge'));
  const markRow = node('tr', 'newspaper-mark-head-row'); thead.appendChild(markRow);
  const marks = ['ability', 'eval', 'training', 'jrdb', 'rn', 'ryota', 'oji', 'iluka'];
  marks.forEach(mark => markRow.appendChild(node('th', `newspaper-mark-col mark-${mark}`)));
  const tbody = node('tbody'); table.appendChild(tbody);
  const rows = [0, 1, 2].map(() => {
    const row = node('tr'); tbody.appendChild(row);
    for (let i = 0; i < 4; i++) row.appendChild(node('td'));
    marks.forEach(mark => row.appendChild(node('td', `newspaper-mark-col mark-${mark}`)));
    for (let i = 0; i < 3; i++) row.appendChild(node('td', 'newspaper-history-cell'));
    row.appendChild(node('td', 'newspaper-edge'));
    return row;
  });
  return { table, top, group, markRow, marks, rows };
}
const { table, top, group, markRow, marks, rows } = fixture();
const context = vm.createContext({
  currentBundle: {
    metadata: { source_status: { edge_v05: { state: 'PARTIAL' } } },
    edge_v05_candidates: Object.fromEntries(['a', 'b', 'c'].map((id, i) => [id, {
      candidate_id: id, family: `T${i + 1}`, condition_text: `条件${id}`, oos_tier: 'CONFIRMED',
      discovery: { n: 10, place_rate: 0.3, place_roi: 120 }, oos_2026: { n: 5, place_rate: 0.4, place_roi: 130 }
    }])),
    horses: [[], ['a'], ['a', 'b', 'c']].map((ids, index) => ({ key: { horse_no: index + 1 }, basic: { horse_name: `馬${index + 1}` }, addons: { edge_v05: { candidate_ids: ids } }, special_memos: [{ edge_id: 'v02' }] }))
  },
  tableWrap: { querySelector() { return table; } },
  dialogTitle: { textContent: '' }, dialogBody: { innerHTML: '' },
  detailDialog: { showModal() { this.opened = true; } },
  document: { createElement: tag => node(tag) },
  renderTable() {}, text: (value, fallback = '—') => value == null || value === '' ? fallback : String(value),
  escapeHtml: value => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;')
});
vm.runInContext(source, context);
context.renderTable();
assert.equal(table.querySelectorAll('.newspaper-edge').length, 0);
assert.equal(top.querySelectorAll('th.newspaper-edge-v05').length, 1);
assert.equal(top.querySelector('th.newspaper-edge-v05').rowSpan, 2);
assert.equal(top.querySelector('th.newspaper-edge-v05').textContent, 'Edge');
assert.equal(group.colSpan, 8);
assert.deepEqual(markRow.children.map(cell => cell.className.split('mark-').at(-1)), marks);
assert.equal(top.children.indexOf(top.querySelector('th.newspaper-edge-v05')) + 1,
  top.children.indexOf(top.querySelector('th.newspaper-history-head')));
assert.equal(top.children.length - 1 + group.colSpan, rows[0].children.length);
rows.forEach((row, i) => {
  const edge = row.querySelector('td.newspaper-edge-v05');
  assert.equal(row.querySelectorAll('td.newspaper-edge-v05').length, 1);
  assert.equal(row.children.indexOf(edge) + 1, row.children.indexOf(row.querySelector('td.newspaper-history-cell')));
  assert.equal(row.children.length, rows[0].children.length);
  assert.equal(edge.children.length, i ? 1 : 0);
});
assert.equal(rows[1].querySelector('td.newspaper-edge-v05').children[0].textContent, '○');
rows[2].querySelector('td.newspaper-edge-v05').children[0].listeners.click();
assert.equal(context.detailDialog.opened, true);
assert.match(context.dialogBody.innerHTML, /その他のEdge（1件）/);
assert.match(context.dialogBody.innerHTML, /2026診断は過去評価の説明/);
context.renderTable();
assert.equal(top.querySelectorAll('th.newspaper-edge-v05').length, 1);
rows.forEach(row => assert.equal(row.querySelectorAll('td.newspaper-edge-v05').length, 1));
context.currentBundle.metadata.source_status.edge_v05.state = 'ERROR';
assert.equal(vm.runInContext('newspaperV05Ids', context)(context.currentBundle.horses[1]).length, 0);
console.log('production v0.5 Edge DOM contract: PASS');
