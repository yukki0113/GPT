const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '../pwa');
const source = fs.readFileSync(path.join(root, 'newspaper-confidence.js'), 'utf8');
const context = vm.createContext({ escapeHtml: value => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;') });
vm.runInContext(source, context);
const confidence = vm.runInContext('newspaperRaceConfidence', context);
const horse = (rn, ryota, oji) => ({ addons: { racenote_prediction: rn ? { confidence: rn } : {},
  momotaro: { ryota: ryota ? { confidence: ryota } : {}, oji: oji ? { confidence: oji } : {} } } });
const bundle = (horses, notes = {}) => ({ horses, race_notes: notes });
for (const grade of ['A', 'B', 'C']) {
  assert.equal(confidence(bundle([horse(grade, '')]), 'kenshow', false), grade);
  assert.equal(confidence(bundle([horse('', '')], { momotaro_race_confidence: { kenshow: grade } }), 'kenshow', true), grade);
}
for (const grade of ['A−', 'B', 'PASS']) {
  assert.equal(confidence(bundle([horse('', grade), horse('', '')]), 'ryota', false), grade);
  assert.equal(confidence(bundle([horse('', grade)]), 'ryota', true), grade);
}
assert.equal(confidence(bundle([horse('A', 'A−'), horse('B', 'B')]), 'kenshow', false), '–');
assert.equal(confidence(bundle([horse('', 'A−'), horse('', 'PASS')]), 'ryota', false), '–');
assert.equal(confidence(bundle([horse('', '', '★')]), 'oji', false), '–');
assert.equal(confidence(bundle([horse('', '', '★')]), 'oji', true), '–');
assert.equal(confidence(bundle([horse('', '')]), 'kenshow', false), '–');
assert.equal(confidence(bundle([horse('', '')]), 'ryota', true), '–');
const html = fs.readFileSync(path.join(root, 'newspaper.html'), 'utf8');
const publicHtml = fs.readFileSync(path.join(root, 'momotaro/newspaper.html'), 'utf8');
assert.ok(html.indexOf('newspaper-confidence.js') < html.indexOf('newspaper-momotaro.js'));
assert.ok(publicHtml.indexOf('newspaper-confidence.js') < publicHtml.indexOf('momotaro.js'));
for (const value of [html, publicHtml]) {
  assert.match(value, /newspaper-confidence\.css\?v=2/);
  assert.match(value, /newspaper-confidence\.js\?v=1/);
}
console.log('race confidence contract: PASS');
