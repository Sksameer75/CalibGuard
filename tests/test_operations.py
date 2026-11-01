import unittest
from collections import Counter
from backend.generator import generate_dataset


class OperationsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = generate_dataset(40, 100, 20261022)

    def test_work_orders_linked_and_downtime(self):
        d = self.data
        event_ids = {x['calibration_id'] for x in d['calibration_events']}
        asset_ids = {x['asset_id'] for x in d['assets']}
        wo_ids = {x['work_order_id'] for x in d['work_orders']}
        self.assertEqual(len(d['work_orders']), 100)
        self.assertTrue(all(x['calibration_id'] in event_ids and x['downtime_minutes'] > 0 for x in d['work_orders']))
        self.assertTrue(all(x['work_order_id'] in wo_ids and x['asset_id'] in asset_ids for x in d['work_order_assets']))

    def test_failed_calibrations_have_impact_assessment(self):
        failures = {e['calibration_id'] for e in self.data['calibration_events'] if e['result'] == 'FAIL'}
        assessed = {x['calibration_id'] for x in self.data['impact_assessments']}
        self.assertEqual(failures, assessed)

    def test_lifecycle_history_and_determinism(self):
        d = self.data
        self.assertEqual(len(d['work_orders']) * 3 + len(d['impact_assessments']) + len(d['emergency_extensions']) * 2, len(d['lifecycle_events']))
        self.assertEqual(d['lifecycle_events'], generate_dataset(40, 100, 20261022)['lifecycle_events'])


if __name__ == '__main__':
    unittest.main()
