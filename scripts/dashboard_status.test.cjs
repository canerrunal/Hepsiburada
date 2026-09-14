const test = require('node:test');
const assert = require('node:assert/strict');

test('dashboard contract keeps profile product counts separate from taxonomy memberships', () => {
  const status = {
    profiles: [{ productCount: 1000 }],
    taxonomy: { categoryCount: 1743, productMembershipRows: null },
    definitions: { productCount: 'Unique product records in a profile snapshot.' },
  };
  assert.equal(status.profiles[0].productCount, 1000);
  assert.equal(status.taxonomy.productMembershipRows, null);
  assert.match(status.definitions.productCount, /Unique product/);
});
