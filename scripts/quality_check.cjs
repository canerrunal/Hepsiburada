#!/usr/bin/env node
// Kalite kapısı: latest.json ürün sayısı + minimum eşik.
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..');
const arg = (n, f = null) => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const PROFILE = arg('profile', 'elektronik');
const base = PROFILE === 'elektronik' && fs.existsSync(path.join(ROOT, 'config.json')) ? ROOT : path.join(ROOT, 'categories', PROFILE);
function checkLatest(dir) {
  const f = path.join(dir, 'data', 'latest.json');
  if (!fs.existsSync(f)) return { status: 'FAIL', reason: 'latest.json yok' };
  const j = JSON.parse(fs.readFileSync(f, 'utf8'));
  const min = j.minimumProducts || 200;
  return { status: (j.products || []).length >= min ? 'PASS' : 'FAIL', productCount: (j.products || []).length, minimumProducts: min };
}
function main() {
  const r = checkLatest(base);
  console.log(`QUALITY_${r.status} profile=${PROFILE} count=${r.productCount ?? 0}`);
  if (r.status !== 'PASS') process.exitCode = 2;
}
if (require.main === module) main();
module.exports = { checkLatest };
