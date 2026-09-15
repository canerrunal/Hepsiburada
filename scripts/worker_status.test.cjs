const test = require('node:test');
const assert = require('node:assert/strict');
const { componentFor, workerStatus } = require('./worker_status.cjs');

test('worker commands map to stable operational components', () => {
  assert.equal(componentFor('python3 scripts/hb_taxonomy_crawl.py --tag shard-0'), 'taxonomy-discovery');
  assert.equal(componentFor('python3 scripts/hb_taxonomy_collect.py --shard 2'), 'taxonomy-products');
  assert.equal(componentFor('python3 scripts/hb_detail_pw.py --profile moda'), 'detail-collector');
});

test('worker status exposes a dashboard-safe shape', () => {
  const status = workerStatus();
  assert.ok(status && status.summary);
  assert.ok(Array.isArray(status.active));
  assert.ok(Array.isArray(status.stale));
  assert.ok(Array.isArray(status.recentRuns));
});
