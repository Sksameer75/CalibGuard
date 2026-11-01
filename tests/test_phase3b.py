import unittest
from backend.generator import generate_dataset
from backend.phase3 import inject
from backend.phase3b import inspect, sql_literal

class Phase3BTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=generate_dataset(40,100,20261022,1000)
        cls.data,cls.labels=inject(cls.base,20261022)
        cls.data={name:[{k:str(v) for k,v in row.items()} for row in rows] for name,rows in cls.data.items()}

    def test_labelled_anomalies_are_allowed_only_when_detected(self):
        report=inspect(self.data,self.labels)
        self.assertTrue(report['pass'],report['error_examples'][:5])
        self.assertEqual(report['labels_detected'],12)

    def test_corrupted_arithmetic_is_rejected(self):
        import copy
        data=copy.deepcopy(self.data)
        data['calibration_events'][0]['absolute_error']='9999.0000'
        report=inspect(data,self.labels)
        self.assertFalse(report['pass'])
        self.assertIn('ERROR_ARITHMETIC',report['rule_counts'])

    def test_bad_enum_is_rejected(self):
        import copy
        data=copy.deepcopy(self.data)
        data['production_uses'][0]['decision']='UNKNOWN'
        report=inspect(data,self.labels)
        self.assertFalse(report['pass'])
        self.assertIn('ENUM',report['rule_counts'])

    def test_sql_escapes_quotes(self):
        self.assertEqual(sql_literal("O'Reilly",None),"'O''Reilly'")
        self.assertEqual(sql_literal('',None),'NULL')

if __name__=='__main__': unittest.main()
