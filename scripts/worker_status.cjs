// Operational worker inventory shared by the dashboard and diagnostics.
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const RUNTIME = path.join(ROOT, '.runtime', 'runs');

function componentFor(command) {
  if (command.includes('hb_taxonomy_crawl.py')) return 'taxonomy-discovery';
  if (command.includes('hb_taxonomy_collect.py')) return 'taxonomy-products';
  if (command.includes('hb_collect_pw.py')) return 'listing-collector';
  if (command.includes('hb_detail_pw.py')) return 'detail-collector';
  if (command.includes('hb_taxonomy_merge.py')) return 'taxonomy-merge';
  if (command.includes('hepsiburada_discovery.sh')) return 'discovery-orchestrator';
  if (command.includes('hepsiburada_finalize.sh')) return 'finalize-orchestrator';
  return 'worker';
}

function readRuntimeRuns() {
  const files = [];
  if (!fs.existsSync(RUNTIME)) return files;
  for (const day of fs.readdirSync(RUNTIME)) {
    const dir = path.join(RUNTIME, day);
    if (!fs.statSync(dir).isDirectory()) continue;
    for (const file of fs.readdirSync(dir)) {
      if (file.endsWith('.json')) files.push(path.join(dir, file));
    }
  }
  return files.map((file) => {
    try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch (_) { return null; }
  }).filter(Boolean).sort((a, b) => String(b.updatedAt).localeCompare(String(a.updatedAt)));
}

function processInventory() {
  try {
    const output = execFileSync('ps', ['-axo', 'pid=,etime=,stat=,pcpu=,pmem=,command='], { encoding: 'utf8' });
    return output.split('\n').map((line) => {
      const match = line.match(/^\s*(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(.*)$/);
      if (!match) return null;
      const [, pid, elapsed, stat, cpu, memory, command] = match;
      if (!/hb_(taxonomy_crawl|taxonomy_collect|collect_pw|detail_pw)\.py|hepsiburada_(discovery|finalize)\.sh/.test(command)) return null;
      return { pid: Number(pid), elapsed, stat, cpu: Number(cpu), memory: Number(memory), command: command.trim(), component: componentFor(command) };
    }).filter(Boolean);
  } catch (_) { return []; }
}

function pidAlive(pid) {
  if (!pid) return false;
  try { process.kill(Number(pid), 0); return true; } catch (_) { return false; }
}

function workerStatus() {
  const runs = readRuntimeRuns();
  const ps = processInventory();
  const trackedPids = new Set(runs.filter((r) => r.status === 'RUNNING').map((r) => Number(r.pid)));
  const tracked = runs.slice(0, 50).map((run) => ({
    ...run,
    live: run.status === 'RUNNING' && pidAlive(run.pid),
    source: 'runtime-registry',
  }));
  const untracked = ps.filter((item) => !trackedPids.has(item.pid)).map((item) => ({
    ...item, status: 'RUNNING', live: true, source: 'process-list', tracked: false,
  }));
  const active = [
    ...tracked.filter((r) => r.status === 'RUNNING' && r.live),
    ...untracked,
  ];
  const stale = tracked.filter((r) => r.status === 'RUNNING' && !r.live).map((r) => ({ ...r, status: 'STALE', live: false }));
  return {
    observedAt: new Date().toISOString(),
    summary: { activeCount: active.length, staleCount: stale.length, trackedRunCount: runs.length, osProcessCount: ps.length },
    active,
    stale,
    recentRuns: runs.slice(0, 20),
  };
}

module.exports = { componentFor, processInventory, workerStatus };
