import unittest

from saleha.skills.unit_converter_skill import UnitConverterSkill


class UnitConverterSkillTests(unittest.TestCase):
    def setUp(self):
        self.skill = UnitConverterSkill()

    def test_temperature_conversion(self):
        self.assertTrue(self.skill.can_handle("Convert 100 celsius to fahrenheit"))
        result = self.skill.execute("Convert 100 celsius to fahrenheit")
        self.assertTrue(result.success)
        self.assertIn("212 fahrenheit", result.output)

    def test_distance_conversion(self):
        self.assertTrue(self.skill.can_handle("50 km to miles"))
        result = self.skill.execute("50 km to miles")
        self.assertTrue(result.success)
        self.assertIn("31.0686 miles", result.output)

    def test_mass_conversion(self):
        self.assertTrue(self.skill.can_handle("10 kg to lbs"))
        result = self.skill.execute("10 kg to lbs")
        self.assertTrue(result.success)
        self.assertIn("22.0462 lbs", result.output)

    def test_storage_conversion(self):
        self.assertTrue(self.skill.can_handle("2048 MB to GB"))
        result = self.skill.execute("2048 MB to GB")
        self.assertTrue(result.success)
        self.assertIn("2 gb", result.output)

    def test_rejects_coding_requests(self):
        self.assertFalse(self.skill.can_handle("Write a Python function to convert km to miles"))

    def test_rejects_unsupported_units(self):
        self.assertFalse(self.skill.can_handle("Convert 10 apples to oranges"))


if __name__ == "__main__":
    unittest.main()

