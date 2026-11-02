// Retained Pages gate: retired addons must never be read by newspaper renderers.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '../pwa');
for (const file of ['newspaper.js','newspaper-v2.js','newspaper-v4.js','newspaper-v5.js','newspaper-v6.js','newspaper-v7.js','newspaper-v8.js','newspaper-v10.js','newspaper-momotaro.js']) {
  const source = fs.readFileSync(path.join(root,file),'utf8');
  assert.doesNotMatch(source, /edge_matches|edge_v05|special_memos|my_index|training_edge_index|newspaper-edge|mark-my/);
  new vm.Script(source);
}
for (const file of ['newspaper.html','service-worker.js']) assert.doesNotMatch(fs.readFileSync(path.join(root,file),'utf8'), /newspaper-edge-v05/);
assert.ok(!fs.existsSync(path.join(root,'newspaper-edge-v05.js')));
const context = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(root,'newspaper-v10.js'),'utf8'),context);
for (const state of [undefined,'ERROR','PARTIAL','READY']) {
 const status = {eval:{state:'READY'},keibailuka:{state:'READY'}};
 for (const key of ['edge','edge_v05','my_index']) Object.defineProperty(status,key,{get(){throw Error('retired source read');}});
 assert.equal(context.dayPackageSummary({manifest:{date:'2026-11-02',source_status:status},races:[{}]}),'2026-11-02 / 1R / Eval○ / 🐬○');
}
console.log('retired newspaper UI regression: PASS');
