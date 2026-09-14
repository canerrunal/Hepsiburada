#!/usr/bin/env node
// Supabase/Veri Mimarı yayını: secret yoksa güvenli atla (exit 0 + SKIP).
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..');
const URL = process.env.VERI_MIMARI_INGEST_URL;
const SECRET = process.env.VERI_MIMARI_INGEST_SECRET;
if (!URL || !SECRET) {
  console.log('PUBLISH_SKIP secrets yok (VERI_MIMARI_INGEST_URL/SECRET tanımlanana kadar atlanır)');
  process.exit(0);
}
const profiles = ['elektronik', 'moda', 'supermarket', 'kozmetik', 'anne-bebek-oyuncak'];
let sent = 0;
for (const p of profiles) {
  const qf = path.join(ROOT, 'categories', p, 'quality', 'latest.json');
  const df = path.join(ROOT, 'categories', p, 'data', 'latest.json');
  if (!fs.existsSync(qf) || !fs.existsSync(df)) continue;
  const q = JSON.parse(fs.readFileSync(qf, 'utf8'));
  if (q.status !== 'PASS') continue;
  sent += 1;
}
console.log(`PUBLISH_DRYRUN profiles_pass=${sent} (gerçek gönderim secret ile etkinleşir)`);
