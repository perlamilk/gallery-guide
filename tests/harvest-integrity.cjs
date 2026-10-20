const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('tools/harvest-mfa.js', 'utf8');
let calls, statuses, sleeps, runningState;
function harness(responses) {
  calls = 0; sleeps = [];
  const element = { style: {}, appendChild() {}, remove() {}, querySelector() { return {style:{}}; } };
  const context = { console, Blob, URL, Map, Set, Date, Math, Number, String,
    document: { getElementById() { return null; }, createElement() { return element; }, body: element },
    window: {}, setTimeout(fn, ms) { sleeps.push(ms); fn(); },
    fetch: async () => { calls++; return responses.shift(); },
  };
  vm.createContext(context);
  const cutoff = source.indexOf('  open().then(async d =>');
  vm.runInContext(source.slice(0, cutoff) + `
  window.test = { politeFetch, record, start: () => { running = true; }, stop: () => { running = false; } };
})();`, context);
  context.window.test.start();
  return context.window.test;
}
(async () => {
  for (const code of [202, 401, 403, 429]) {
    const h = harness([{status:code, ok:false}]);
    await assert.rejects(h.politeFetch('/objects/8'), new RegExp('HTTP '+code));
    assert.equal(calls, 1, 'access refusals must not be retried');
  }
  let h = harness([{status:500, ok:false},{status:200,ok:true,text:async()=>'<div class="detailField">ok</div>'}]);
  await h.politeFetch('/objects/8');
  assert.deepEqual(sleeps, [15000,60000,30000], 'server errors must lengthen request delay');
  h = harness([{status:200,ok:true,text:async()=>'<html>captcha</html>'}]);
  await assert.rejects(h.politeFetch('/objects/8'), /verification page/);
  assert.equal(calls, 1);
  h = harness([]); h.stop();
  await assert.rejects(h.politeFetch('/objects/8'), /paused/);
  assert.equal(calls, 0);
  console.log('7 integrity checks passed (4 refusal statuses, backoff, challenge, pause).');
})().catch(e=>{ console.error(e); process.exitCode=1; });
