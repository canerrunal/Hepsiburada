const test = require('node:test');
const assert = require('node:assert');
const { extractCategoryUrls, toCsv } = require('./discover_hepsiburada_taxonomy.cjs');

test('kategori URL çıkarımı -c- desenini yakalar', () => {
  const html = '<a href="https://www.hepsiburada.com/telefonlar-c-60003479">x</a> bla https://www.hepsiburada.com/bilgisayarlar-c-60003480?q=1';
  const out = extractCategoryUrls(html);
  assert.strictEqual(out.length, 2);
  assert.ok(out[0].includes('-c-'));
});

test('csv başlığı ve kaçış', () => {
  const csv = toCsv([{ id: '1', parent_id: '', name: 'a"b', url: 'u', level: 1, path: 'a' }]);
  assert.ok(csv.startsWith('id,parent_id,name,url,level,path'));
  assert.ok(csv.includes('a""b'));
});
