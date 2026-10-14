"""Freeze pinned Test262 syntax checks for the explicit import-phase extensions.

Usage: python tools/freeze_import_phase_corpus.py PATH_TO_PINNED_TEST262
The original programs are parsed only and are never executed. Runtime and
module-resolution assertions in positive sources are outside this syntax gate.
"""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.check_grammar_reference import REVISION, array

FEATURES = {'import-defer', 'source-phase-imports', 'source-phase-imports-module-source'}
SUBJECTS = ('expressions/dynamic-import', 'expressions/assignmenttargettype', 'import', 'module-code')


def main():
    checkout = Path(sys.argv[1]).resolve()
    revision = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != REVISION:
        raise SystemExit('Test262 checkout differs from the pinned revision')
    # Every occurrence of these features in the frozen revision is within
    # these subjects. Avoid scanning unrelated runtime built-in corpora.
    selected = set()
    for subject in SUBJECTS:
        selected.update((checkout / 'test/language' / subject).rglob('*.js'))
    cases = []
    for path in sorted(selected):
        source = path.read_text(encoding='utf-8')
        match = re.search(r'/\*---(.*?)---\*/', source, re.DOTALL)
        if not match:
            continue
        metadata = match.group(1)
        features, flags = array(metadata, 'features'), array(metadata, 'flags')
        if not set(features) & FEATURES or set(features) & {'export-defer', 'decorators'}:
            continue
        negative = bool(re.search(r'phase:\s*parse', metadata))
        if negative and not re.search(r'type:\s*SyntaxError\b', metadata):
            raise ValueError(f'Parse-negative phase fixture is not SyntaxError: {path}')
        modes = (['module'] if 'module' in flags else ['script'] if set(flags) & {'raw', 'noStrict'}
                 else ['strict'] if 'onlyStrict' in flags else ['script', 'strict'])
        for mode in modes:
            cases.append({'path': path.relative_to(checkout).as_posix(), 'mode': mode,
                          'flags': flags, 'features': features, 'parseNegative': negative,
                          'sha256': sha256(source.encode('utf-8')).hexdigest(), 'source': source})
    if len(cases) != 851 or len({case['path'] for case in cases}) != 495:
        raise ValueError('Import-phase inventory differs from the reviewed frozen revision')
    target = ROOT / 'tests/fixtures/import-phases'
    target.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({'cases': cases}, ensure_ascii=True, indent=2) + '\n'
    license_text = (checkout / 'LICENSE').read_text(encoding='utf-8')
    (target / 'cases.json').write_text(payload, encoding='utf-8', newline='\n')
    (target / 'LICENSE').write_text(license_text, encoding='utf-8', newline='\n')
    manifest = {'upstream': 'https://github.com/tc39/test262', 'revision': REVISION,
                'caseCount': len(cases), 'sourceFileCount': len({case['path'] for case in cases}),
                'scope': 'Import-phase proposal syntax and parse-phase SyntaxError checks; original programs never executed.',
                'options': {'ecmaVersion': 2026, 'deferredImportEvaluation': True, 'sourcePhaseImports': True},
                'selectionSubjects': list(SUBJECTS),
                'selectionFeatures': sorted(FEATURES), 'excludedFeatures': ['decorators', 'export-defer'],
                'modeCounts': dict(Counter(case['mode'] for case in cases)),
                'parseNegativeChecks': sum(case['parseNegative'] for case in cases),
                'sourceEncoding': 'UTF-8 decoded; line endings normalized to LF.',
                'files': {'cases.json': sha256(payload.encode('utf-8')).hexdigest(),
                          'LICENSE': sha256(license_text.encode('utf-8')).hexdigest()}}
    (target / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
