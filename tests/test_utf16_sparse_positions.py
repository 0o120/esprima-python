"""Compare sparse position conversion to actual UTF-16 encoding."""
import random
import unittest
from esprima.error_handler import ErrorHandler
from esprima.scanner import Scanner


def units(source):
    return len(source.encode('utf-16-le', errors='surrogatepass')) // 2


class SparsePositionTests(unittest.TestCase):
    def test_mixed_scalars_surrogates_boundaries_and_columns(self):
        random_source = random.Random(9147)
        alphabet = 'a\u03b1\u200c\n\r\U0001f600\U0001d49c\ud83d\ude00'
        for _ in range(80):
            source = ''.join(random_source.choice(alphabet) for _ in range(random_source.randrange(1, 70)))
            scanner = Scanner(source, ErrorHandler())
            for index in range(-2, len(source) + 3):
                clamped = min(max(index, 0), len(source))
                self.assertEqual(scanner.utf16Offset(index), units(source[:clamped]))
                start = min(max(index // 2, 0), len(source))
                self.assertEqual(scanner.utf16Column(index, start), units(source[:clamped]) - units(source[:start]))

    def test_large_bmp_source_with_one_supplementary_scalar(self):
        source = '\u03b1' * 25000 + '\U0001f600' + 'z' * 25000
        scanner = Scanner(source, ErrorHandler())
        for index in (0, 1, 24999, 25000, 25001, len(source), len(source) + 1):
            self.assertEqual(scanner.utf16Offset(index), units(source[:min(index, len(source))]))


if __name__ == '__main__':
    unittest.main()
