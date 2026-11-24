"use strict";
/* Actual JS source smoke regression; never touches published Newspaper data. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const base = path.resolve(__dirname, "../../jrdb/pwa");
const trigger = {handler: null, addEventListener(event, fn) {
  if (event === "click") this.handler = fn;
}};
const title = {textContent: ""};
const body = {innerHTML: ""};
const dialog = {opened: 0, showModal() {this.opened++;}, setAttribute() {this.opened++;}};
const element = {
  "newspaper-blood-dialog": dialog,
  "newspaper-blood-title": title,
  "newspaper-blood-body": body,
  "newspaper-table-wrap": trigger
};
const escapeHtml = x => String(x).replace(/&/g,"&amp;").replace(/</g,"&lt;")
  .replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#039;");
const first = {
  key: {horse_no: 3, horse_id: "12345678"},
  basic: {horse_name: "<b>架空馬</b>", sire_name: "父A",
    dam_name: "母B", broodmare_sire_name: "母父C"},
  addons: {racenote_prediction: {mark:"◎"}}
};
const scope = {
  console,
  window: {addEventListener() {}, JRDB_PWA_CONFIG: {}},
  document: {getElementById: k => element[k] || null},
  renderTable: () => {},
  renderBundle: () => {},
  currentBundle: {race: {race_key:"05265412"}, horses:[first]},
  escapeHtml,
  text: (x, fallback="—") => x === null || x === undefined || x === "" ? fallback : String(x),
  number: x => String(x),
  tableWrap: trigger,
  historyCount:3
};
vm.createContext(scope);
for(const name of ["newspaper-v4.js","newspaper-blood.js"]){
  vm.runInContext(fs.readFileSync(path.join(base,name),"utf8"),scope,{filename:name});
}
const html = vm.runInContext("newspaperV4HorseNameHtml(currentBundle.horses[0])",scope);
assert.match(html,/newspaper-blood-name-wrap/);
assert.match(html,/data-horse-no="3"/);
assert.match(html,/data-horse-id="12345678"/);
assert.match(html,/<button[^>]+>血統<\/button>/);
assert.match(html,/&lt;b&gt;架空馬&lt;\/b&gt;/);
assert.equal(typeof trigger.handler,"function");

function click(n=3,id="12345678"){
  trigger.handler({target:{closest(cls){
    return cls === ".newspaper-blood-trigger" ?
      {dataset:{horseNo:String(n),horseId:id}} : null;
  }}});
}
click();
assert.equal(dialog.opened,1);
assert.match(body.innerHTML,/父A/);
assert.match(body.innerHTML,/母B/);
assert.match(body.innerHTML,/母父C/);
assert.match(body.innerHTML,/クロス/);
assert.match(body.innerHTML,/今回の条件と血統実績/);
assert.match(body.innerHTML,/馬券検討Tips/);
assert.match(body.innerHTML,/未接続/);
assert.doesNotMatch(body.innerHTML,/父が得意|必ず買う|100%適性/);
assert.equal(scope.currentBundle.horses[0].addons.racenote_prediction.mark,"◎");

click(3,"87654321");
assert.equal(dialog.opened,1,"wrong horse ID may not open dialog");

first.addons.brdb_pedigree_display = {
  contract_version:"brdb-newspaper-pedigree-display-v0.1-candidate",
  release_status:"RESEARCH_PREVIEW_ONLY",
  research_only:true, prediction_safe:false, production_authorized:false,
  as_of_status:"AS_OF_UNVERIFIED",
  race_key:"05265412",horse_id:"12345678",horse_no:3,
  score:null,rank:null,probability:null,source_sha256:"a".repeat(64),
  crosses:[{ancestor:"Northern Dancer",pattern:"4×5"}],
  condition_records:[{label:"東京芝2000m / 父産駒",starts:40,wins:4,top3:12,
    status:"AVAILABLE",source_label:"JRDB研究集計"}],
  reviews:[{category:"父産駒",text:"観測実績のみ。",status:"AS_OF_UNVERIFIED",
    evidence_label:"SIRE_VENUE_DISTANCE"}],
  relatives:[{name:"近親A",relationship:"母方半兄",note:"研究確認中"}],
  tips:[{kind:"CHECK",text:"該当条件の母数40走を確認",evidence_label:"SIRE_VENUE_DISTANCE"}]
};
click();
assert.equal(dialog.opened,2);
assert.match(body.innerHTML,/Northern Dancer/);
assert.match(body.innerHTML,/40走・4勝・3着以内12回/);
assert.match(body.innerHTML,/30.0%/);
assert.match(body.innerHTML,/研究確認中/);
assert.match(body.innerHTML,/観測実績のみ/);
assert.match(body.innerHTML,/取得時点は未検証/);

first.addons.brdb_pedigree_display.horse_id = "99999999";
click();
assert.match(body.innerHTML,/未接続/);
assert.doesNotMatch(body.innerHTML,/Northern Dancer/);
first.addons.brdb_pedigree_display.horse_id = "12345678";

first.addons.brdb_pedigree_display.prediction_safe=true;
click();
assert.match(body.innerHTML,/未接続/);
first.addons.brdb_pedigree_display.prediction_safe=false;

first.addons.brdb_pedigree_display.reviews[0].text="<script>alert(1)</script>";
click();
assert.doesNotMatch(body.innerHTML,/<script>/);
assert.match(body.innerHTML,/&lt;script&gt;/);

const pages=[
  ["newspaper.html","./"],
  ["momotaro/newspaper.html","../"]
];
for (const [page,prefix] of pages) {
  const content=fs.readFileSync(path.join(base,page),"utf8");
  assert.match(content,/id="newspaper-blood-dialog"/);
  assert.match(content,/id="newspaper-blood-title"/);
  assert.match(content,/id="newspaper-blood-body"/);
  assert.ok(content.includes(prefix+"newspaper-blood.css?v=1"));
  assert.ok(content.includes(prefix+"newspaper-blood.js?v=1"));
}
for(const [worker,prefix] of [
  ["service-worker.js","./"],
  ["momotaro/service-worker.js","../"]
]){
  const content=fs.readFileSync(path.join(base,worker),"utf8");
  assert.ok(content.includes(prefix+"newspaper-blood.css?v=1"));
  assert.ok(content.includes(prefix+"newspaper-blood.js?v=1"));
}
console.log("PASS: blood modal, basic facts, guarded optional review, escaping, canonical ID, 2 surfaces and offline shell");
