#!/usr/bin/env node
// Publish only quality-passing, date-consistent Hepsiburada snapshots.
// The idempotency key is deterministic for profile/date/content.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const ENDPOINT = process.env.VERI_MIMARI_INGEST_URL;
const SECRET = process.env.VERI_MIMARI_INGEST_SECRET;
const PROFILES = ['elektronik', 'moda', 'supermarket', 'kozmetik', 'anne-bebek-oyuncak'];
const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Istanbul', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());

function readJson(file) {
  return fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : null;
}
function profileDir(profile) {
  return profile === 'elektronik' ? ROOT : path.join(ROOT, 'categories', profile);
}
function sourceCommit() {
  try { return execFileSync('git', ['rev-parse', 'HEAD'], { cwd: ROOT, encoding: 'utf8' }).trim(); }
  catch (_) { return ''; }
}
function idempotencyKey(payload) {
  return crypto.createHash('sha256').update(JSON.stringify(payload)).digest('hex');
}

async function send(payload) {
  const key = idempotencyKey(payload);
  const response = await fetch(ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${SECRET}`,
      'X-Ingest-Secret': SECRET,
      'Idempotency-Key': key,
    },
    body: JSON.stringify(payload),
  });
  const body = await response.text();
  if (!response.ok) throw new Error(`HTTP_${response.status}: ${body.slice(0, 160)}`);
  return { key, status: response.status, body: body.slice(0, 500) };
}

async function main() {
  if (!ENDPOINT || !SECRET) {
    console.log('PUBLISH_SKIP secrets yok (VERI_MIMARI_INGEST_URL/SECRET tanımlanana kadar atlanır)');
    return;
  }
  const commit = sourceCommit();
  const results = [];
  for (const profile of PROFILES) {
    const dir = profileDir(profile);
    const quality = readJson(path.join(dir, 'quality', 'latest.json'));
    const data = readJson(path.join(dir, 'data', 'latest.json'));
    if (!quality || !data || quality.status !== 'PASS' || data.date !== today) {
      results.push({ profile, status: 'SKIP', reason: !quality ? 'quality_missing' : quality.status !== 'PASS' ? 'quality_fail' : 'stale_date' });
      continue;
    }
    const payload = {
      marketplace: 'hepsiburada',
      profile: profile === 'elektronik' ? 'hepsiburada-elektronik' : `hepsiburada-${profile}`,
      quality,
      products: data.products || [],
      sourceCommit: commit,
      observedDate: data.date,
      publishedAt: new Date().toISOString(),
    };
    try {
      const sent = await send(payload);
      results.push({ profile, status: 'PUBLISHED', idempotencyKey: sent.key, httpStatus: sent.status });
    } catch (error) {
      results.push({ profile, status: 'FAILED', error: String(error.message || error) });
    }
  }
  const taxonomy = readJson(path.join(ROOT, 'taxonomy', 'catalog.json'));
  const taxonomyStatus = readJson(path.join(ROOT, 'taxonomy', 'status.json'));
  if (taxonomy && taxonomy.status === 'PASS' && taxonomy.date === today) {
    try {
      const sent = await send({ marketplace: 'hepsiburada', profile: 'hepsiburada-taxonomy', quality: taxonomyStatus || { status: 'PASS' }, taxonomy, sourceCommit: commit, observedDate: taxonomy.date, publishedAt: new Date().toISOString() });
      results.push({ profile: 'taxonomy', status: 'PUBLISHED', idempotencyKey: sent.key, httpStatus: sent.status });
    } catch (error) {
      results.push({ profile: 'taxonomy', status: 'FAILED', error: String(error.message || error) });
    }
  } else {
    results.push({ profile: 'taxonomy', status: 'SKIP', reason: 'taxonomy_not_pass' });
  }
  console.log(JSON.stringify({ marketplace: 'hepsiburada', sourceCommit: commit, results }, null, 2));
  if (results.some((r) => r.status === 'FAILED')) process.exitCode = 1;
}
main().catch((error) => { console.error(`PUBLISH_ERROR ${error.message || error}`); process.exitCode = 1; });
