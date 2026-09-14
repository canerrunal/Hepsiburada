#!/usr/bin/env node
// Pilot profil toplayıcı: liste -> latest.json/snapshot/lists/reports/quality iskeleti.
// Anti-bot engelde sahte ürün ÜRETMEZ; quality FAIL + boş rapor yazar.
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
const CONFIG_FILE = PROFILE === 'elektronik' && fs.existsSync(path.join(ROOT, 'config.json')) && !fs.existsSync(path.join(ROOT, 'profiles', 'elektronik.json'))
  ? path.join(ROOT, 'config.json')
  : path.join(ROOT, 'profiles', `${PROFILE}.json`);
if (!fs.existsSync(CONFIG_FILE)) throw new Error(`Profil ayarı bulunamadı: ${CONFIG_FILE}`);
const config = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf8'));
const OUT = PROFILE === 'elektronik' && config.profile === 'elektronik' && path.basename(CONFIG_FILE) === 'config.json' ? ROOT : path.join(ROOT, 'categories', PROFILE);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const todayIstanbul = () => {
  const p = new Intl.DateTimeFormat('en-CA', { timeZone: config.timezone || 'Europe/Istanbul', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date()).reduce((a, x) => ({ ...a, [x.type]: x.value }), {});
  return `${p.year}-${p.month}-${p.day}`;
};
const stampIstanbul = () => {
  const p = new Intl.DateTimeFormat('en-CA', { timeZone: config.timezone || 'Europe/Istanbul', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).formatToParts(new Date()).reduce((a, x) => ({ ...a, [x.type]: x.value }), {});
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}:${p.second}+03:00`;
};
const mkdir = (d) => fs.mkdirSync(d, { recursive: true });

async function fetchListing(url) {
  const res = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36', Accept: 'text/html,*/*;q=0.8' } });
  if (!res.ok) throw new Error(`HTTP_${res.status}`);
  const html = await res.text();
  // Hepsiburada gömülü JSON yapısı keşif aşamasında sabitlenecek; şimdilik ürün kartı linklerini çıkar.
  const links = [...html.matchAll(/href="(\/[a-z0-9- PastelQGp\-p\/]*-p-[A-Za-z0-9]+)"/g)].map((m) => `https://www.hepsiburada.com${m[1]}`).filter((u, i, a) => a.indexOf(u) === i);
  return links.map((url, i) => ({ rank: i + 1, url, title: '', price: null, source_url: url }));
}

async function main() {
  const date = todayIstanbul();
  const collectedAt = stampIstanbul();
  const dataDir = path.join(OUT, 'data');
  const snapDir = path.join(OUT, 'snapshots', date);
  const listsDir = path.join(OUT, 'lists', date);
  const reportsDir = path.join(OUT, 'reports');
  const qualityDir = path.join(OUT, 'quality');
  [dataDir, snapDir, listsDir, reportsDir, qualityDir].forEach(mkdir);
  let products = [];
  let blockError = null;
  for (const seg of config.searchSegments || []) {
    try {
      const items = await fetchListing(seg.url);
      items.forEach((it) => { it.source_segment = seg.name; });
      products.push(...items);
    } catch (e) { blockError = blockError || e.message; }
    await sleep(config.requestDelayMs || 1500);
    if (products.length >= (config.maxProducts || 300)) break;
  }
  // Tekilleştir
  const seen = new Set();
  products = products.filter((p) => (seen.has(p.url) ? false : (seen.add(p.url), true))).slice(0, config.maxProducts || 300);
  const pass = products.length >= (config.minimumProducts || 200);
  const latest = { profile: PROFILE, date, collectedAt, source: config.sourceLabel, count: products.length, products };
  fs.writeFileSync(path.join(dataDir, 'latest.json'), JSON.stringify(latest, null, 2));
  fs.writeFileSync(path.join(snapDir, 'products.json'), JSON.stringify(latest, null, 2));
  const header = 'rank,title,price,url,source_segment\n';
  const csv = header + products.map((p, i) => [i + 1, `"${String(p.title).replace(/"/g, '""')}"`, p.price ?? '', p.url, p.source_segment || ''].join(',')).join('\n');
  fs.writeFileSync(path.join(dataDir, 'latest.csv'), csv);
  fs.writeFileSync(path.join(listsDir, 'trending.csv'), csv);
  const md = `# ${config.reportTitle} — ${date}\n\n> Kaynak: ${config.sourceLabel}\n> Toplama: ${collectedAt}\n> Havuz: ${products.length} ürün | Kalite: **${pass ? 'PASS' : 'FAIL'}**${blockError ? `\n> Not: listeleme engeli (${blockError}), sahte ürün üretilmedi.` : ''}\n`;
  fs.writeFileSync(path.join(reportsDir, `${date}.md`), md);
  fs.writeFileSync(path.join(reportsDir, 'latest.md'), md);
  fs.writeFileSync(path.join(reportsDir, 'telegram-latest.txt'), `${config.telegramTitle} ${date}: ${products.length} ürün, kalite ${pass ? 'PASS' : 'FAIL'}.`);
  const quality = { status: pass ? 'PASS' : 'FAIL', productCount: products.length, minimumProducts: config.minimumProducts, date, generatedAt: collectedAt, blockError };
  fs.writeFileSync(path.join(qualityDir, 'latest.json'), JSON.stringify(quality, null, 2));
  console.log(`COLLECT_${pass ? 'OK' : 'FAIL'} profile=${PROFILE} count=${products.length}${blockError ? ` block=${blockError}` : ''}`);
  if (!pass) process.exitCode = 2;
}

if (require.main === module) main().catch((e) => { console.error(`COLLECT_ERROR ${e.message}`); process.exit(1); });
