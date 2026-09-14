#!/usr/bin/env node
// Hepsiburada kategori keşfi: sitemap + tohum liste -> taxonomy/catalog.json/csv
// Engelde sahte kategori ÜRETMEZ; status=BLOCKED yazar.
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const TAXONOMY_DIR = path.join(ROOT, 'taxonomy');
const SEED = require('./taxonomy_seed.json');

function todayIstanbul() {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Istanbul', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date()).reduce((a, p) => ({ ...a, [p.type]: p.value }), {});
  return `${parts.year}-${parts.month}-${parts.day}`;
}

function toCsv(rows) {
  const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
  return ['id,parent_id,name,url,level,path', ...rows.map((r) => [r.id, r.parent_id, r.name, r.url, r.level, r.path].map(esc).join(','))].join('\n') + '\n';
}

async function fetchText(url) {
  const res = await fetch(url, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
      Accept: 'text/html,application/xml;q=0.9,*/*;q=0.8',
    },
  });
  if (!res.ok) throw new Error(`HTTP_${res.status}`);
  return res.text();
}

function extractCategoryUrls(xmlOrHtml) {
  const urls = new Set();
  const re = /https:\/\/www\.hepsiburada\.com\/[a-z0-9-]+\-c\-\d+/gi;
  let m;
  while ((m = re.exec(xmlOrHtml)) !== null) urls.add(m[0].toLowerCase());
  return [...urls].slice(0, 5000);
}

async function main() {
  const date = todayIstanbul();
  const snapDir = path.join(TAXONOMY_DIR, 'snapshots', date);
  fs.mkdirSync(snapDir, { recursive: true });
  let found = [];
  let status = 'SEED';
  try {
    const index = await fetchText('https://www.hepsiburada.com/sitemap.xml');
    const locs = [...index.matchAll(/<loc>([^<]+)<\/loc>/g)].map((x) => x[1]).filter((u) => /sitemap/i.test(u)).slice(0, 10);
    for (const loc of locs) {
      try {
        const body = await fetchText(loc);
        found.push(...extractCategoryUrls(body));
      } catch { /* tek sitemap hatası keşfi durdurmaz */ }
    }
    if (found.length > 0) status = 'LIVE';
  } catch (e) {
    status = `BLOCKED_${e.message}`;
  }
  found = [...new Set(found)];
  const rows = found.length > 0
    ? found.map((url, i) => {
      const idMatch = url.match(/-c-(\d+)/);
      const slug = url.split('/').pop().replace(/-c-\d+/, '');
      return { id: idMatch ? idMatch[1] : `hb-${i}`, parent_id: '', name: slug.replace(/-/g, ' '), url, level: 1, path: slug };
    })
    : SEED.map((s) => ({ id: s.id ?? '', parent_id: s.parent_id ?? '', name: s.name, url: s.url, level: s.level ?? 1, path: s.path ?? s.name }));
  fs.writeFileSync(path.join(TAXONOMY_DIR, 'catalog.json'), JSON.stringify({ date, status, count: rows.length, categories: rows }, null, 2));
  fs.writeFileSync(path.join(TAXONOMY_DIR, 'catalog.csv'), toCsv(rows));
  fs.writeFileSync(path.join(snapDir, 'summary.json'), JSON.stringify({ date, status, categoryCount: rows.length, source: found.length > 0 ? 'sitemap' : 'seed' }, null, 2));
  console.log(`DISCOVERY_OK status=${status} categories=${rows.length}`);
}

if (require.main === module) main().catch((e) => { console.error(`DISCOVERY_FAIL ${e.message}`); process.exit(1); });
module.exports = { extractCategoryUrls, toCsv };
