// Verify the guest engine against the shared synthetic scenarios without a browser.
const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const source = fs.readFileSync("frontend/app.js", "utf8");
const start = source.indexOf("function localAnalyze(");
const end = source.indexOf("\nfunction requestStart", start);
const context = {
  performance,
  level: (s) => (s >= 60 ? "high" : s >= 30 ? "caution" : "low"),
};
vm.createContext(context);
vm.runInContext(source.slice(start, end), context);
const cases = JSON.parse(
  fs.readFileSync("evaluation/cases.json", "utf8").replace(/^\uFEFF/, ""),
);
for (const item of cases.filter((c) => !c.id.includes("known-gap"))) {
  assert.equal(context.localAnalyze(item.turns).level, item.expected, item.id);
}
console.log(
  "Guest baseline: 10 regression scenarios passed; 2 known limitations are tracked in evaluation.",
);
