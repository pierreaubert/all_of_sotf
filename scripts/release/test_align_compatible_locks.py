"""Small identity-guard regressions for the lock-alignment proposal lane."""

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from align_compatible_locks import CRATES_IO, companion_observations, global_identity_guard


def lock(path: Path, packages: list[tuple[str, str]]) -> Path:
    lines = ['version = 4']
    for name, version in packages:
        lines.extend(['', '[[package]]', f'name = "{name}"',
                      f'version = "{version}"', f'source = "{CRATES_IO}"'])
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return path


class AlignmentIdentityGuards(unittest.TestCase):
    def test_new_singleton_companion_does_not_expand_duplicate_group(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before = lock(root / 'before.lock', [('base', '1.0.0')])
            after = lock(root / 'after.lock', [('base', '1.0.0'), ('child', '0.1.0')])
            guard = global_identity_guard({'test': before}, {'test': after})
            self.assertEqual(guard['new_duplicate_names'], [])
            self.assertEqual(guard['expanded_identity_names'], [])

    def test_second_identity_creates_rejected_duplicate_group(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before = lock(root / 'before.lock', [('base', '1.0.0')])
            after = lock(root / 'after.lock', [('base', '1.0.0'), ('base', '2.0.0')])
            guard = global_identity_guard({'test': before}, {'test': after})
            self.assertEqual(guard['new_duplicate_names'], ['base'])
            self.assertEqual(guard['expanded_identity_names'], ['base'])

    def test_companion_accepts_normalized_parent_edge_spelling(self) -> None:
        parent = {'name': 'flate2', 'version': '1.1.10', 'source': CRATES_IO,
                  'dependencies': ['miniz_oxide 0.9.1']}
        child = {'name': 'miniz_oxide', 'version': '0.9.1', 'source': CRATES_IO}
        approved = {'test': [{'name': 'miniz_oxide', 'version': '0.9.1', 'source': CRATES_IO,
                              'required_parent': {'name': 'flate2', 'version': '1.1.10',
                                                  'source': CRATES_IO,
                                                  'dependency_entry': 'miniz_oxide'}}]}
        observed = companion_observations('test', {('miniz_oxide', '0.9.1', CRATES_IO)},
                                          [parent, child], approved)
        self.assertEqual(observed[0]['dependency_entry'], 'miniz_oxide 0.9.1')

    def test_unreviewed_companion_source_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, 'unreviewed'):
            companion_observations('test', {('miniz_oxide', '0.9.1', 'git+example')}, [], {})


if __name__ == '__main__':
    unittest.main()
