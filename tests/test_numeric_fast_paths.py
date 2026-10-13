"""Numeric scanning preserves exact lexical boundaries and host settings."""
import sys
import unittest
import esprima


class NumericFastPathTests(unittest.TestCase):
    def test_digit_runs_and_separator_errors(self):
        for source, value in [('12345', 12345), ('0xabcdef', 0xabcdef), ('0b101001', 41), ('0o7654', 4012),
                              ('123_456', 123456), ('0xabc_def', 0xabcdef), ('1.25e2', 125), ('.125', .125)]:
            with self.subTest(source=source):
                tree = esprima.parseScript(source+';', range=True)
                self.assertEqual(tree.body[0].expression.value, value)
                self.assertEqual(tree.body[0].expression.range, [0, len(source)])
        for source in ('1__2', '1_', '0x_1', '0x1_', '0b102', '0o78', '12abc', '1e_2', '1._2'):
            with self.subTest(source=source), self.assertRaises(esprima.Error):
                esprima.parseScript(source)

    def test_large_decimal_bigint_and_caller_digit_limit(self):
        before = sys.get_int_max_str_digits()
        digits = '1234567890' * 1000
        node = esprima.parseScript(digits+'n;').body[0].expression
        self.assertEqual(node.bigint, digits)
        self.assertIsNone(node.value)
        self.assertEqual(sys.get_int_max_str_digits(), before)
        for source, expected in [('0n', '0'), ('0x000ffn', '255'), ('0o00077n', '63'), ('0b00011n', '3')]:
            self.assertEqual(esprima.parseScript(source).body[0].expression.bigint, expected)
        with self.assertRaises(esprima.Error):
            esprima.parseScript('00n')


if __name__ == '__main__':
    unittest.main()
