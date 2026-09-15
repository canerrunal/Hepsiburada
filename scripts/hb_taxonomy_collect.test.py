#!/usr/bin/env python3
import json
import unittest
from pathlib import Path

from hb_taxonomy_collect import load_categories, target_for_subcategory_count


class TaxonomyCollectionPolicyTest(unittest.TestCase):
    def test_root_target_policy(self):
        self.assertEqual(target_for_subcategory_count(1001), 4000)
        self.assertEqual(target_for_subcategory_count(999), 2500)
        self.assertEqual(target_for_subcategory_count(500), 2500)
        self.assertEqual(target_for_subcategory_count(499), 2000)
        self.assertEqual(target_for_subcategory_count(12, 123), 123)

    def test_current_catalog_normalizes_all_roots(self):
        data, rows = load_categories()
        roots = [row for row in rows if int(row.get("level", 0)) == 1]
        self.assertEqual(data.get("status"), "PASS")
        self.assertEqual(len(roots), 9)
        self.assertTrue(all(row.get("root_id") for row in rows))
        self.assertTrue(all(row.get("canonical_path") for row in rows))


if __name__ == "__main__":
    unittest.main()
