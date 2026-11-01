import unittest
from datetime import datetime
from backend.generator import generate_dataset
from backend.production import evaluate_use, generate_production_uses

class ProductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = generate_dataset(40, 100, 20261022, 1000)

    def test_counts_and_references(self):
        uses = self.tables['production_uses']
        self.assertEqual(len(uses), 1000)
        self.assertEqual(len({r['use_id'] for r in uses}), 1000)
        self.assertTrue({r['asset_id'] for r in uses} <= {a['asset_id'] for a in self.tables['assets']})
        self.assertTrue({r['decision'] for r in uses} <= {'ALLOW','BLOCK','CONDITIONAL_ALLOW'})

    def test_determinism(self):
        a, _ = generate_production_uses(self.tables, 100, 20261022)
        b, _ = generate_production_uses(self.tables, 100, 20261022)
        self.assertEqual(a, b)

    def test_no_calibration_blocks(self):
        asset = self.tables['assets'][0]
        plan = next(p for p in self.tables['calibration_plans'] if p['asset_id'] == asset['asset_id'])
        decision, reason = evaluate_use(asset, datetime(2025, 10, 30), [], {}, [], plan)
        self.assertEqual((decision, reason), ('BLOCK', 'NO_CALIBRATION'))

    def test_blocked_execution_distinct(self):
        for row in self.tables['production_uses']:
            if row['decision'] != 'BLOCK':
                self.assertEqual(row['was_executed'], 1)
