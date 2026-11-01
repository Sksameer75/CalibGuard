import unittest
from backend.generator import generate_dataset
from backend.phase3 import inject, detect, validate_integrity, KINDS

class Phase3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=generate_dataset(40,100,20261022,1000)
        cls.data,cls.labels=inject(cls.base,20261022,2)
    def test_all_four_anomalies_labelled(self):
        self.assertEqual({x['anomaly_type'] for x in self.labels},set(KINDS))
        self.assertEqual(len(self.labels),8)
    def test_detection(self):
        actual=set(detect(self.data))
        expected={(x['anomaly_type'],x['table_name'],x['record_id'],x['field_name']) for x in self.labels}
        self.assertTrue(expected<=actual)
    def test_integrity(self):
        self.assertEqual(validate_integrity(self.data),[])
    def test_deterministic_and_no_original_mutation(self):
        second,labels=inject(self.base,20261022,2)
        self.assertEqual((self.data,self.labels),(second,labels))
        self.assertNotEqual(self.base['calibration_events'],self.data['calibration_events'])
if __name__=='__main__':unittest.main()
