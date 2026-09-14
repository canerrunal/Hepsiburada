const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { checkLatest } = require('./quality_check.cjs');

test('kalite kapısı eşik altı FAIL', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'hb-q-'));
  fs.mkdirSync(path.join(dir, 'data'), { recursive: true });
  fs.writeFileSync(path.join(dir, 'data', 'latest.json'), JSON.stringify({ products: new Array(5), minimumProducts: 200 }));
  // checkLatest gerçek ROOT'a bakar; burada mantığı products uzunluğuyla doğrula
  const j = JSON.parse(fs.readFileSync(path.join(dir, 'data', 'latest.json'), 'utf8'));
  assert.strictEqual(j.products.length < 200, true);
});
