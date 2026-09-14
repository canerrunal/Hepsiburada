#!/usr/bin/env node
// Hepsiburada quality gate. Listing phase validates the candidate; final phase
// also validates detail coverage before a snapshot can be published.
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const arg = (n, f = null) => {
  const i = process.argv.indexOf(`--${n}`);
  const inline = process.argv.find((a) => a.startsWith(`--${n}=`));
  if (inline) return inline.slice(n.length + 3);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const PROFILE = arg('profile', 'elektronik');
const PHASE = arg('phase', 'listing');
const base = PROFILE === 'elektronik' && fs.existsSync(path.join(ROOT, 'config.json')) ? ROOT : path.join(ROOT, 'categories', PROFILE);
const nowDate = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Istanbul', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
const present = (v) => v !== null && v !== undefined && v !== '' && !(Array.isArray(v) && v.length === 0);

const CORE_FIELDS = ['marketplace', 'product_id', 'sku', 'title', 'url', 'price', 'source_segment', 'source_page'];
const DETAIL_FIELDS = ['merchant_name', 'seller_count', 'rating', 'review_count', 'question_count', 'stock_status'];

function readJson(file) {
  return fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : null;
}

function checkLatest(dir, phase = 'listing', configOverride = null) {
  const cfg = configOverride || readJson(path.join(dir, 'config.json')) || readJson(path.join(ROOT, 'profiles', `${PROFILE}.json`)) || {};
  const dataName = phase === 'listing' && fs.existsSync(path.join(dir, 'data', 'latest.candidate.json'))
    ? 'latest.candidate.json' : 'latest.json';
  const latest = readJson(path.join(dir, 'data', dataName));
  if (!latest) return { status: 'FAIL', reason: 'latest.json yok', phase };
  const products = Array.isArray(latest.products) ? latest.products : [];
  const minimumProducts = Number(latest.minimumProducts || cfg.minimumProducts || 1000);
  const fieldCoverage = {};
  for (const field of CORE_FIELDS) {
    fieldCoverage[field] = Number((100 * products.filter((p) => present(p[field])).length / Math.max(products.length, 1)).toFixed(1));
  }
  const identityKeys = products.map((p) => {
    const key = p.product_key || p.product_id || p.canonical_url || p.url || p.sku;
    return key ? `${key}::${p.variant_id || ''}` : null;
  }).filter(Boolean);
  const duplicates = identityKeys.length - new Set(identityKeys).size;
  const checks = {
    productTarget: products.length >= minimumProducts,
    coreFieldCoverage: CORE_FIELDS.every((f) => fieldCoverage[f] >= 95),
    noDuplicateProducts: duplicates === 0,
    dateMatches: latest.date === nowDate(),
  };
  let detail = null;
  if (phase === 'final') {
    const detailedName = fs.existsSync(path.join(dir, 'data', 'latest.detailed.candidate.json'))
      ? 'latest.detailed.candidate.json' : 'latest.detailed.json';
    const detailed = readJson(path.join(dir, 'data', detailedName));
    const detailedProducts = detailed && Array.isArray(detailed.products) ? detailed.products : [];
    const attempted = detailedProducts.filter((p) => p.detail_attempted || p.detail_ok).length;
    const refreshed = detailedProducts.filter((p) => p.detail_ok).length;
    const stockCovered = detailedProducts.filter((p) => present(p.stock_status) || present(p.stock_quantity)).length;
    const planned = Number(cfg.dailyFullDetailTopN || Math.min(300, products.length));
    detail = {
      attempted,
      refreshed,
      planned,
      successRate: Number((100 * refreshed / Math.max(attempted, 1)).toFixed(1)),
      stockCoverage: Number((100 * stockCovered / Math.max(refreshed, 1)).toFixed(1)),
      coverage: Object.fromEntries(DETAIL_FIELDS.map((f) => [f, Number((100 * detailedProducts.filter((p) => present(p[f]) || present((p.detail || {})[f])).length / Math.max(refreshed, 1)).toFixed(1))])),
    };
    checks.detailFileExists = Boolean(detailed);
    checks.detailSnapshotAligned = Boolean(detailed && detailed.date === latest.date && detailedProducts.length === products.length);
    checks.detailPlanReached = attempted >= Math.min(planned, products.length);
    checks.detailSuccessRate = detail.successRate >= 80;
    checks.stockCoverage = detail.stockCoverage >= 90;
  }
  const passed = Object.values(checks).every(Boolean);
  return {
    status: !checks.dateMatches ? 'STALE' : passed ? 'PASS' : 'FAIL',
    phase,
    date: latest.date,
    generatedAt: new Date().toISOString(),
    productCount: products.length,
    minimumProducts,
    duplicateProducts: duplicates,
    fieldCoverage,
    checks,
    ...(detail ? { detail } : {}),
  };
}

function main() {
  const result = checkLatest(base, PHASE);
  fs.mkdirSync(path.join(base, 'quality'), { recursive: true });
  fs.writeFileSync(path.join(base, 'quality', 'latest.json'), JSON.stringify(result, null, 2));
  fs.writeFileSync(path.join(base, 'quality', `${result.date || nowDate()}.json`), JSON.stringify(result, null, 2));
  console.log(`QUALITY_${result.status} profile=${PROFILE} phase=${PHASE} count=${result.productCount ?? 0}`);
  if (result.status !== 'PASS') process.exitCode = 2;
}
if (require.main === module) main();
module.exports = { checkLatest };
