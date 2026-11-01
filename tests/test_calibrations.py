import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from backend.generator import generate_dataset


class CalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = generate_dataset(40, 100, 20261022)

    def test_counts_and_references(self):
        d = self.data
        self.assertEqual(len(d['calibration_events']), 100)
        asset_ids = {r['asset_id'] for r in d['assets']}
        plans = {r['plan_id']: r for r in d['calibration_plans']}
        event_ids = {r['calibration_id'] for r in d['calibration_events']}
        for event in d['calibration_events']:
            self.assertIn(event['asset_id'], asset_ids)
            self.assertEqual(plans[event['plan_id']]['asset_id'], event['asset_id'])
        for cert in d['certificates']:
            self.assertIn(cert['calibration_id'], event_ids)
            self.assertEqual(cert['certificate_id'], 'CERT-' + cert['calibration_id'])

    def test_measurements_and_due_dates(self):
        plans = {r['plan_id']: r for r in self.data['calibration_plans']}
        for e in self.data['calibration_events']:
            error = abs(Decimal(e['measured_value']) - Decimal(e['reference_value']))
            self.assertEqual(error, Decimal(e['absolute_error']))
            expected = 'PASS' if error <= Decimal(e['tolerance_at_test']) else 'FAIL'
            self.assertEqual(e['result'], expected)
            if expected == 'PASS':
                due = datetime.fromisoformat(e['performed_at']) + timedelta(days=int(plans[e['plan_id']]['interval_days']))
                self.assertEqual(e['calculated_due_at'], due.strftime('%Y-%m-%d %H:%M:%S'))
            else:
                self.assertEqual(e['calculated_due_at'], '')

    def test_repeatable(self):
        self.assertEqual(self.data, generate_dataset(40, 100, 20261022))

if __name__ == '__main__':
    unittest.main()
