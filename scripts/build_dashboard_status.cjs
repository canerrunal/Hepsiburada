#!/usr/bin/env node
// Build a marketplace-specific dashboard contract. A UI can consume this file
// without confusing profile products with taxonomy membership rows.
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const { workerStatus } = require('./worker_status.cjs');

const ROOT = path.resolve(__dirname, '..');
const PROFILES = ['elektronik', 'moda', 'supermarket', 'kozmetik', 'anne-bebek-oyuncak'];
const date = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Istanbul', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
const read = (f) => {
  try { return fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, 'utf8')) : null; } catch (_) { return null; }
};
const dir = (p) => p === 'elektronik' ? ROOT : path.join(ROOT, 'categories', p);
const commit = (() => { try { return execFileSync('git', ['rev-parse', 'HEAD'], { cwd: ROOT, encoding: 'utf8' }).trim(); } catch (_) { return null; } })();
const workers = workerStatus();

function hermesSchedules() {
  try {
    const home = process.env.HOME || '/Users/canerunal';
    const jobsFile = path.join(home, '.hermes', 'cron', 'jobs.json');
    if (!fs.existsSync(jobsFile)) return [];
    const jobs = JSON.parse(fs.readFileSync(jobsFile, 'utf8')).jobs || [];
    return jobs
      .filter((j) => j && j.enabled !== false && /^hepsiburada/.test(j.name || ''))
      .map((j) => ({
        name: j.name,
        schedule: j.schedule_display || j.schedule?.display || '?',
        nextRun: j.next_run_at || null,
        lastRun: j.last_run_at || null,
        lastStatus: j.last_status || null,
        mode: j.no_agent ? 'no-agent' : 'agent',
      }))
      .sort((a, b) => String(a.nextRun || '').localeCompare(String(b.nextRun || '')));
  } catch (_) { return []; }
}

function taxonomyFileStats(file) {
  const data = read(file) || {};
  const rows = Array.isArray(data.categories) ? data.categories : [];
  const roots = rows.filter((row) => Number(row.level) === 1);
  const byRoot = {};
  const byLevel = {};
  let maxDepth = 0;
  for (const row of rows) {
    const root = row.root_name || (row.full_path || row.path || row.name || '').split('>')[0].trim() || 'unknown';
    byRoot[root] = (byRoot[root] || 0) + 1;
    const level = Number(row.level) || 0;
    byLevel[level] = (byLevel[level] || 0) + 1;
    maxDepth = Math.max(maxDepth, level);
  }
  return {
    file: path.relative(ROOT, file),
    status: data.status || 'UNKNOWN',
    date: data.date || null,
    categoryCount: Number(data.count || rows.length),
    rootCount: roots.length,
    maxDepth,
    emptyIdCount: rows.filter((row) => !row.id).length,
    byRoot,
    byLevel,
  };
}

function taxonomyTreeStats() {
  const taxonomyDir = path.join(ROOT, 'taxonomy');
  const primary = taxonomyFileStats(path.join(taxonomyDir, 'catalog.json'));
  const shardFiles = fs.existsSync(taxonomyDir)
    ? fs.readdirSync(taxonomyDir).filter((name) => /^catalog-.+\.json$/.test(name)).sort().map((name) => taxonomyFileStats(path.join(taxonomyDir, name)))
    : [];
  const uniqueIds = new Set();
  for (const shard of shardFiles) {
    const data = read(path.join(ROOT, shard.file)) || {};
    for (const row of (data.categories || [])) if (row.id) uniqueIds.add(row.id);
  }
  return {
    primary,
    shards: shardFiles,
    shardCategoryRows: shardFiles.reduce((sum, shard) => sum + shard.categoryCount, 0),
    shardUniqueCategoryIds: uniqueIds.size,
  };
}

function atomicWriteJson(file, value) {
  const temporary = `${file}.${process.pid}.tmp`;
  fs.writeFileSync(temporary, JSON.stringify(value, null, 2));
  fs.renameSync(temporary, file);
}

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
    productCount: Number(data.count || (Array.isArray(data.products) ? data.products.length : 0) || quality.productCount || 0),
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
const tree = taxonomyTreeStats();
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
    tree,
  },
  profiles,
  workers,
  activeHermesJobs: workers.active,
  schedules: hermesSchedules(),
  scanPlan: [
    ...PROFILES.map((p) => {
      const cfg = read(p === 'elektronik' ? path.join(ROOT, 'config.json') : path.join(ROOT, 'profiles', `${p}.json`)) || {};
      return { task: `Profil: ${p}`, time: cfg.dailyRunTime || '—', workers: '1 (vitrin) + 1 (detay), global kilitle sıralı', target: `${cfg.minimumProducts || 1000} ürün + detay` };
    }),
    { task: 'Taksonomi keşif (4 shard)', time: '15:00', workers: '4 paralel (shard-0..3)', target: 'kategori ağacı + merge' },
    { task: 'Taksonomi ürün tarama (4 shard)', time: 'keşif sonrası', workers: '4 paralel (shard-0..3)', target: 'kategori-ürün üyelikleri' },
    { task: 'Finalize + Telegram özeti', time: '04:30', workers: '1', target: 'yayın + Telegram' },
    { task: 'Dashboard durum üretici', time: '5 dakikada bir', workers: '1', target: 'status.json' },
  ],
  publication: { status: process.env.VERI_MIMARI_INGEST_URL && process.env.VERI_MIMARI_INGEST_SECRET ? 'configured' : 'not_configured' },
  definitions: {
    productCount: 'Unique product records in a profile snapshot.',
    productMembershipRows: 'Category-product ranking memberships; not added to profile product count.',
    stale: 'Snapshot date does not match observedDate or its quality status is not PASS.',
  },
};
fs.mkdirSync(path.join(ROOT, 'dashboard'), { recursive: true });
atomicWriteJson(path.join(ROOT, 'dashboard', 'status.json'), output);
console.log(`DASHBOARD_STATUS_OK profiles=${profiles.length} taxonomy=${output.taxonomy.status}`);
