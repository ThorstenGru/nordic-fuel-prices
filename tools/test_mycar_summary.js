// Tests for the answer-card state logic in web/index.html (between MC-PURE-BEGIN and MC-PURE-END).  node tools/test_mycar_summary.js
const fs = require('fs'), assert = require('assert');
const src = fs.readFileSync(__dirname + '/../web/index.html', 'utf8');
const m = src.match(/\/\/ MC-PURE-BEGIN[^\n]*\n([\s\S]*?)\/\/ MC-PURE-END/); assert(m, 'pure block not found');
const { mcState, mcNext } = new Function(m[1] + '; return { mcState, mcNext };')();
const eq = assert.strictEqual;
eq(mcState({}), 'nocar'); eq(mcNext({}), 1);
eq(mcState({ type: 'petrol' }), 'notphev'); eq(mcState({ type: 'diesel', cheaper: null }), 'notphev'); eq(mcNext({ type: 'petrol' }), 0);
eq(mcState({ type: 'phev', missCar: ['Batt'], missElec: true }), 'needcar'); eq(mcNext({ type: 'phev', missCar: ['Batt'], missElec: true }), 1);
eq(mcState({ type: 'phev', missCar: [], missElec: true }), 'needelec'); eq(mcNext({ type: 'phev', missCar: [], missElec: true }), 2);
eq(mcState({ type: 'phev', missCar: [], missElec: false }), 'needpet'); eq(mcNext({ type: 'phev', missCar: [], missElec: false }), 3);
for (const c of ['electric', 'petrol', 'same']) { eq(mcState({ type: 'phev', missCar: [], missElec: false, cheaper: c }), c); eq(mcNext({ type: 'phev', cheaper: c }), 0); }
console.log('mycar summary: all tests passed');
