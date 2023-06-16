import random
from enum import Enum

from django.test import TestCase

from user.enums import EthnicityEnum, ReligionEnum, StateEnum


class EnumTests(TestCase):
    def test_state_enum(self):
        """test"""
        for enum_value in StateEnum:
            self.assertTrue(isinstance(enum_value, Enum))
            self.assertIn(enum_value.value, [choice.value for choice in StateEnum])

    def test_religion_enum(self):
        for enum_value in ReligionEnum:
            self.assertTrue(isinstance(enum_value, Enum))
            self.assertIn(enum_value.value, [choice.value for choice in ReligionEnum])

    def test_ethnicity_enum(self):
        for enum_value in EthnicityEnum:
            self.assertTrue(isinstance(enum_value, Enum))
            self.assertIn(enum_value.value, [choice.value for choice in EthnicityEnum])

    def test_random_enum_value(self):
        enum_class = random.choice([StateEnum, ReligionEnum, EthnicityEnum])
        enum_value = random.choice(list(enum_class))
        self.assertTrue(isinstance(enum_value, Enum))
        self.assertIn(enum_value.value, [choice.value for choice in enum_class])
