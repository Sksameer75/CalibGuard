import unittest
from backend.generator import generate_master_data


class MasterDataTests(unittest.TestCase):
    def test_counts_and_joins(self):
        data = generate_master_data(40, 20261022)
        self.assertEqual(len(data["assets"]), 40)
        self.assertEqual(len(data["calibration_plans"]), 40)
        types = {r["instrument_type_id"] for r in data["instrument_types"]}
        suppliers = {r["supplier_id"] for r in data["suppliers"]}
        assets = {r["asset_id"] for r in data["assets"]}
        self.assertEqual(len(assets), 40)
        for asset in data["assets"]:
            self.assertIn(asset["instrument_type_id"], types)
            self.assertIn(asset["supplier_id"], suppliers)
        for plan in data["calibration_plans"]:
            self.assertIn(plan["asset_id"], assets)

    def test_determinism(self):
        self.assertEqual(generate_master_data(40, 20261022),
                         generate_master_data(40, 20261022))


if __name__ == "__main__":
    unittest.main()
