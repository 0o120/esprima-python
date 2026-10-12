"""Freeze the published-standard Test262 lexical syntax selection.

Usage: python tools/freeze_lexical_corpus.py PATH_TO_TEST262
The exact revision and file digests are recorded. Runtime assertions are never
executed; the selected sources are used only for parser acceptance/rejection.
All parse-phase negative RegExp fixtures in built-ins/RegExp are included.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REVISION = '2e0a56762801e275a9fdf96dc49d90ba0cddcf63'
DIRECTORIES = (
    'test/language/literals/regexp',
    'test/annexB/language/literals/regexp',
    'test/language/literals/numeric',
    'test/language/literals/bigint',
    'test/language/literals/string',
    'test/language/expressions/template-literal',
    'test/language/comments/hashbang',
)


def metadata(source, name):
    match = re.search(r'^' + name + r':\s*\[([^\]]*)\]', source, re.MULTILINE)
    return [value.strip() for value in match.group(1).split(',') if value.strip()] if match else []


def main():
    checkout = Path(sys.argv[1]).resolve()
    actual = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != REVISION:
        raise SystemExit('Test262 checkout revision differs from the pinned selection')
    paths = set()
    for directory in DIRECTORIES:
        paths.update((checkout / directory).rglob('*.js'))
    for path in (checkout / 'test' / 'built-ins' / 'RegExp').rglob('*.js'):
        if re.search(r'phase:\s*parse', path.read_text(encoding='utf-8')):
            paths.add(path)
    destination = ROOT / 'tests' / 'fixtures' / 'test262-lexical'
    destination.mkdir(parents=True, exist_ok=True)
    cases = []
    for path in sorted(paths):
        data = path.read_bytes()
        source = data.decode('utf-8')
        relative = path.relative_to(checkout).as_posix()
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        cases.append({
            'path': relative, 'sha256': hashlib.sha256(data).hexdigest(),
            'parseNegative': bool(re.search(r'phase:\s*parse', source)),
            'flags': metadata(source, 'flags'), 'features': metadata(source, 'features'),
        })
    (destination / 'LICENSE').write_bytes((checkout / 'LICENSE').read_bytes())
    manifest = {
        'upstream': 'https://github.com/tc39/test262', 'revision': REVISION,
        'languageTarget': 'ECMAScript 2026',
        'selection': list(DIRECTORIES) + ['test/built-ins/RegExp: all parse-phase negatives'],
        'scope': 'Grammar acceptance only; runtime tests and assertions are never executed.',
        'caseCount': len(cases), 'cases': cases,
    }
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    print('Frozen %s lexical syntax files at %s' % (len(cases), REVISION))


if __name__ == '__main__':
    main()
