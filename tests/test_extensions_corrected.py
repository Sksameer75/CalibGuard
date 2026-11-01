import unittest
from datetime import datetime, timedelta
from backend.generator import generate_dataset
from backend.production import evaluate_use

FMT = '%Y-%m-%d %H:%M:%S'

class CorrectedExtensionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = generate_dataset(40, 100, 20261022, 1000)

    def test_conditional_allow_is_generated(self):
        self.assertGreater(sum(u['decision'] == 'CONDITIONAL_ALLOW' for u in self.data['production_uses']), 0)

    def test_failed_calibration_never_overridden(self):
        d = self.data
        asset = d['assets'][0]
        plan = next(p for p in d['calibration_plans'] if p['asset_id'] == asset['asset_id'])
        when = datetime(2026, 4, 1)
        fail = dict(calibration_id='CAL-TEST', asset_id=asset['asset_id'], performed_at='2026-03-31 00:00:00', result='FAIL', calculated_due_at='')
        extension = dict(approval_state='APPROVED', approved_from='2026-03-30 00:00:00', approved_until='2026-04-10 00:00:00')
        decision, reason = evaluate_use(asset, when, [fail], {}, [extension], plan)
        self.assertEqual((decision, reason), ('BLOCK', 'FAILED_CALIBRATION'))

    def test_generated_conditional_cases_are_in_approved_window(self):
        d = self.data
        extensions = d['emergency_extensions']
        for use in d['production_uses']:
            if use['decision'] != 'CONDITIONAL_ALLOW':
                continue
            self.assertTrue(any(e['asset_id'] == use['asset_id'] and e['approval_state'] == 'APPROVED'
                                and e['approved_from'] <= use['used_at'] <= e['approved_until'] for e in extensions))
