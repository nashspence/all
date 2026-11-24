import unittest

from policy import loads


class StrictJsonTests(unittest.TestCase):
    def test_valid_json_preserves_domain_values(self):
        self.assertEqual({"a": [True, None, 1, 1.5]}, loads('{"a":[true,null,1,1.5]}'))
        self.assertEqual([1], loads('[1]'))

    def test_duplicate_keys_are_rejected_at_every_depth(self):
        for text in ('{"a":1,"a":2}', '{"x":[{"a":1,"a":2}]}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                loads(text)

    def test_nonfinite_and_overflow_numbers_are_rejected(self):
        for value in ('NaN', 'Infinity', '-Infinity', '1e9999', '-1e9999'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                loads('{"value":' + value + '}')

    def test_root_shape_is_owned_by_the_consumer(self):
        self.assertEqual({}, loads('{}', object_root=True))
        for text in ('[]', 'null', 'true', '1', '"value"'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                loads(text, object_root=True)

    def test_invalid_or_trailing_json_is_not_silently_repaired(self):
        for text in ('{"a":1,}', '{} {}', ''):
            with self.subTest(text=text), self.assertRaises(ValueError):
                loads(text)


if __name__ == '__main__':
    unittest.main()
