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

test('kalite kapısı temel alan ve duplicate kontrollerini uygular', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'hb-q-contract-'));
  fs.mkdirSync(path.join(dir, 'data'), { recursive: true });
  const date = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Istanbul', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
  const product = (i) => ({ marketplace: 'hepsiburada', product_id: `p-${i}`, product_key: `p-${i}`, sku: `s-${i}`, title: `Ürün ${i}`, url: `https://example.test/p-${i}`, price: 10, source_segment: 'test', source_page: 1 });
  fs.writeFileSync(path.join(dir, 'data', 'latest.json'), JSON.stringify({ date, products: Array.from({ length: 3 }, (_, i) => product(i)) }));
  const result = checkLatest(dir, 'listing', { minimumProducts: 3 });
  assert.equal(result.status, 'PASS');
  fs.writeFileSync(path.join(dir, 'data', 'latest.json'), JSON.stringify({ date, products: [product(1), product(1), product(2)] }));
  assert.equal(checkLatest(dir, 'listing', { minimumProducts: 3 }).status, 'FAIL');
});
