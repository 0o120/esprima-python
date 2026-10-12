"""Repeated regexp checks retain exceptions, editions and caller isolation."""
import unittest
from esprima.regexp_validator import validate_regexp, regexp_features, RegExpSyntaxError


class RegExpCacheContractTests(unittest.TestCase):
    def test_returned_features_are_independent_and_edition_checks_remain(self):
        first = regexp_features('(?<name>x)', 'u')
        self.assertIn('RegExp named capture groups', first)
        first.clear()
        self.assertTrue(regexp_features('(?<name>x)', 'u'))
        validate_regexp('(?<name>x)', 'u', 2026)
        for edition in (5, 2015, 2016, 2017):
            with self.subTest(edition=edition), self.assertRaises(RegExpSyntaxError):
                validate_regexp('(?<name>x)', 'u', edition)

    def test_failure_instances_and_long_patterns_are_not_shared(self):
        errors = []
        for _ in range(2):
            try:
                validate_regexp('(', 'u')
            except RegExpSyntaxError as error:
                errors.append(error)
        self.assertEqual(len(errors), 2)
        self.assertIsNot(errors[0], errors[1])
        self.assertEqual(str(errors[0]), str(errors[1]))
        validate_regexp('x' * 513, 'u')
        with self.assertRaises(RegExpSyntaxError):
            validate_regexp('x' * 513 + '(', 'u')


if __name__ == '__main__':
    unittest.main()
