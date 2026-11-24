import unittest

from policy import finite_number, integer


class NumericBoundaryTests(unittest.TestCase):
    def test_booleans_and_strings_do_not_become_numbers(self):
        for function in (finite_number, integer):
            for value in (True, False, '1', None):
                with self.subTest(function=function.__name__, value=value):
                    with self.assertRaises(ValueError):
                        function(value)

    def test_nonfinite_values_cannot_enter_numeric_policy(self):
        for value in (float('inf'), float('-inf'), float('nan'), 10 ** 999):
            with self.subTest(value=str(value)[:30]), self.assertRaises(ValueError):
                finite_number(value)

    def test_bounds_come_from_the_owning_contract(self):
        self.assertEqual(0, integer(0, minimum=0, maximum=2))
        self.assertEqual(2, integer(2, minimum=0, maximum=2))
        self.assertEqual(0.5, finite_number(0.5, minimum=0, maximum=1))
        for function, value in ((integer, -1), (integer, 3), (finite_number, -0.1)):
            with self.subTest(value=value), self.assertRaises(ValueError):
                function(value, minimum=0, maximum=2)

    def test_json_schema_integer_semantics_are_explicit_not_silently_tightened(self):
        self.assertEqual(1, integer(1.0, allow_integral_float=True))
        with self.assertRaises(ValueError):
            integer(1.0)
        for value in (True, 1.1, float('nan'), float('inf')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                integer(value, allow_integral_float=True)

    def test_exact_integer_validation_does_not_add_a_machine_size_limit(self):
        self.assertEqual(10 ** 999, integer(10 ** 999, minimum=0))


if __name__ == '__main__':
    unittest.main()
