#!/usr/bin/env node
// Build a marketplace-specific dashboard contract. A UI can consume this file
// without confusing profile products with taxonomy membership rows.
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const PROFILES = ['elektronik', 'moda', 'supermarket', 'kozmetik', 'anne-bebek-oyuncak'];
const date = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Istanbul', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
const read = (f) => fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, 'utf8')) : null;
const dir = (p) => p === 'elektronik' ? ROOT : path.join(ROOT, 'categories', p);
const commit = (() => { try { return execFileSync('git', ['rev-parse', 'HEAD'], { cwd: ROOT, encoding: 'utf8' }).trim(); } catch (_) { return null; } })();
const activeJobs = (() => {
  try {
    return execFileSync('ps', ['ax', '-o', 'command='], { encoding: 'utf8' }).split('\n')
      .filter((line) => /hb_(collect|detail|taxonomy)|run_profile\.sh/.test(line))
      .map((command) => ({ command: command.trim().slice(0, 240) }));
  } catch (_) { return []; }
})();

const profiles = PROFILES.map((profile) => {
  const root = dir(profile);
  const quality = read(path.join(root, 'quality', 'latest.json')) || { status: 'UNKNOWN' };
  const data = read(path.join(root, 'data', 'latest.json')) || {};
  const cfg = read(profile === 'elektronik' ? path.join(ROOT, 'config.json') : path.join(ROOT, 'profiles', `${profile}.json`)) || {};
  return {
    profile,
    status: quality.status || 'UNKNOWN',
    observedDate: data.date || quality.date || null,
    reportDate: quality.date || null,
    lastSuccessfulRun: quality.status === 'PASS' ? (quality.generatedAt || null) : null,
    nextScheduledTime: cfg.dailyRunTime || null,
    productTarget: Number(cfg.minimumProducts || 1000),
    productCount: Number(data.count || quality.productCount || 0),
    detailSuccessRate: quality.detailSuccessRate ?? null,
    stockCoverage: quality.detail?.stockCoverage ?? quality.detailCoverage?.stock_status ?? null,
    sellerCoverage: quality.detail?.coverage?.seller_count ?? quality.detailCoverage?.seller_count ?? null,
    errorCount: quality.detailFailed ?? (quality.blockError ? 1 : 0),
    quality,
  };
});

const taxonomy = read(path.join(ROOT, 'taxonomy', 'catalog.json')) || {};
const taxonomyStatus = read(path.join(ROOT, 'taxonomy', 'status.json')) || {};
const taxonomySnapshot = read(path.join(ROOT, 'taxonomy', 'snapshots', date, 'summary.json')) || {};
const output = {
  marketplace: 'hepsiburada',
  generatedAt: new Date().toISOString(),
  observedDate: date,
  sourceCommit: commit,
  taxonomy: {
    status: taxonomyStatus.status || taxonomy.status || 'UNKNOWN',
    productCollectionStatus: taxonomySnapshot.status || 'NOT_RUN',
    observedDate: taxonomy.date || null,
    categoryCount: taxonomy.count || (taxonomy.categories || []).length || 0,
    rootCategoryCount: (taxonomy.categories || []).filter((c) => c.level === 1).length,
    productMembershipRows: taxonomySnapshot.rankingCount ?? null,
  },
  profiles,
  activeHermesJobs: activeJobs,
  publication: { status: process.env.VERI_MIMARI_INGEST_URL && process.env.VERI_MIMARI_INGEST_SECRET ? 'configured' : 'not_configured' },
  definitions: {
    productCount: 'Unique product records in a profile snapshot.',
    productMembershipRows: 'Category-product ranking memberships; not added to profile product count.',
    stale: 'Snapshot date does not match observedDate or its quality status is not PASS.',
  },
};
fs.mkdirSync(path.join(ROOT, 'dashboard'), { recursive: true });
fs.writeFileSync(path.join(ROOT, 'dashboard', 'status.json'), JSON.stringify(output, null, 2));
console.log(`DASHBOARD_STATUS_OK profiles=${profiles.length} taxonomy=${output.taxonomy.status}`);
