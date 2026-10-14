import pathlib
import unittest

import test as legacy


class FixtureInventoryTests(unittest.TestCase):
    def test_every_fixture_is_collected_once(self):
        suite = unittest.defaultTestLoader.loadTestsFromModule(legacy)
        def cases(group):
            for item in group:
                if isinstance(item, unittest.TestSuite):
                    yield from cases(item)
                else:
                    yield item
        ids = [case.id() for case in cases(suite)]
        fixtures = list((pathlib.Path(legacy.BASE_DIR) / 'fixtures').rglob('*.js'))
        self.assertEqual(len(fixtures), 1604)
        self.assertEqual(len(ids), len(fixtures) + 2)
        self.assertEqual(len(ids), len(set(ids)))

    def test_factory_uses_its_argument(self):
        fixture = pathlib.Path(legacy.BASE_DIR) / 'fixtures' / 'whitespace'
        expected = len(list(fixture.rglob('*.js')))
        self.assertEqual(len(list(legacy.test_factory(str(fixture)))), expected)

    def test_schema_and_diagnostic_migrations_are_explicit(self):
        self.assertEqual(len(legacy.FIXTURE_MIGRATIONS), 35)
        for source, migration in legacy.FIXTURE_MIGRATIONS.items():
            self.assertTrue((pathlib.Path(legacy.BASE_DIR) / source).is_file())
            self.assertTrue((pathlib.Path(legacy.BASE_DIR) / migration['snapshot']).is_file())
            self.assertTrue(migration['reason'])
            self.assertIn(migration['kind'], ('.tree', '.failure'))
