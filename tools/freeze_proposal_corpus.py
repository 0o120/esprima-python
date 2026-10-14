"""Freeze complete pinned Test262 resource/decorator syntax feature inventories.

Usage: python tools/freeze_proposal_corpus.py PATH_TO_PINNED_TEST262
Sources retain copyright notices. Every source is data for parsing only;
runtime assertions, host behavior and module resolution are never executed.
"""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.check_grammar_reference import REVISION, array

FEATURES = {'explicit-resource-management', 'decorators'}
PHASE_FEATURES = {'import-defer', 'source-phase-imports', 'source-phase-imports-module-source'}
OPTIONS = {'ecmaVersion': 2026, 'explicitResourceManagement': True, 'decorators': True,
           'deferredImportEvaluation': True, 'sourcePhaseImports': True}
# A whole-test-tree feature census reviewed every feature-tagged source in
# this immutable revision. Every occurrence falls within these subjects.
SUBJECTS = (
    'test/language/expressions/class', 'test/language/statements/class',
    'test/language/statements/using', 'test/language/statements/await-using',
    'test/language/statements/for-of', 'test/language/statements/for-await-of',
    'test/built-ins/AsyncDisposableStack', 'test/built-ins/DisposableStack',
    'test/built-ins/SuppressedError', 'test/built-ins/Symbol/asyncDispose',
    'test/built-ins/Symbol/dispose',
    'test/built-ins/AsyncIteratorPrototype/Symbol.asyncDispose',
    'test/built-ins/Iterator/prototype/Symbol.dispose',
    'test/staging/decorators', 'test/staging/explicit-resource-management',
)


def main():
    checkout = Path(sys.argv[1]).resolve()
    revision = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != REVISION:
        raise SystemExit('Test262 checkout differs from the pinned revision')
    proposed_section = (checkout / 'features.txt').read_text(encoding='utf-8').split('## Standard language features')[0]
    proposed = {line.split('#', 1)[0].strip() for line in proposed_section.splitlines() if line.split('#', 1)[0].strip()}
    excluded = proposed - FEATURES - PHASE_FEATURES
    if shutil.which('rg'):
        # A whole-tree inventory remains fast on Windows with thousands of
        # unrelated class fixtures. The fallback needs no extra dependency.
        paths = subprocess.check_output(['rg', '-l', 'explicit-resource-management|decorators',
            str(checkout / 'test'), '-g', '*.js'], text=True).splitlines()
        selected = set(map(Path, paths))
    else:
        selected = set()
        for subject in SUBJECTS:
            selected.update((checkout / subject).rglob('*.js'))
    cases, omitted = [], []
    for path in sorted(selected):
        source = path.read_text(encoding='utf-8')
        match = re.search(r'/\*---(.*?)---\*/', source, re.DOTALL)
        if not match:
            continue
        metadata = match.group(1)
        features, flags = array(metadata, 'features'), array(metadata, 'flags')
        if not set(features) & FEATURES:
            continue
        adjacent = set(features) & excluded
        covered = set(features) & PHASE_FEATURES
        relative = path.relative_to(checkout).as_posix()
        if adjacent or covered:
            omitted.append({'path': relative, 'features': features,
                            'reason': 'unsupported adjacent proposal' if adjacent else 'already covered in import-phases',
                            'excludedFeatures': sorted(adjacent or covered)})
            continue
        negative = bool(re.search(r'phase:\s*parse', metadata))
        if negative and not re.search(r'type:\s*SyntaxError\b', metadata):
            raise ValueError(f'Parse-negative proposal fixture is not SyntaxError: {path}')
        modes = (['module'] if 'module' in flags else ['script'] if set(flags) & {'raw', 'noStrict'}
                 else ['strict'] if 'onlyStrict' in flags else ['script', 'strict'])
        for mode in modes:
            cases.append({'path': relative, 'mode': mode, 'flags': flags, 'features': features,
                          'parseNegative': negative, 'sha256': sha256(source.encode('utf-8')).hexdigest(),
                          'source': source})
    if len(cases) != 995 or len({case['path'] for case in cases}) != 510 or omitted:
        raise ValueError('Proposal inventory differs from the reviewed frozen revision')
    target = ROOT / 'tests/fixtures/proposals'
    target.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({'cases': cases}, ensure_ascii=True, indent=2) + '\n'
    license_text = (checkout / 'LICENSE').read_text(encoding='utf-8')
    (target / 'cases.json').write_text(payload, encoding='utf-8', newline='\n')
    (target / 'LICENSE').write_text(license_text, encoding='utf-8', newline='\n')
    manifest = {'upstream': 'https://github.com/tc39/test262', 'revision': REVISION,
                'caseCount': len(cases), 'sourceFileCount': len({case['path'] for case in cases}),
                'scope': 'Resource-management and decorator syntax/parse-negative checks; no runtime, host or resolution execution.',
                'options': OPTIONS, 'selectionSubjects': list(SUBJECTS),
                'selectionFeatures': sorted(FEATURES), 'excludedFeatures': sorted(excluded),
                'phaseCorpusFeatures': sorted(PHASE_FEATURES), 'omitted': omitted,
                'modeCounts': dict(Counter(case['mode'] for case in cases)),
                'featureModeCounts': {feature: sum(feature in case['features'] for case in cases) for feature in sorted(FEATURES)},
                'parseNegativeChecks': sum(case['parseNegative'] for case in cases),
                'sourceEncoding': 'UTF-8 decoded; line endings normalized to LF.',
                'resourceLimits': 'Resource-limit Error and incidental Python exceptions cannot count as SyntaxError rejection.',
                'files': {'cases.json': sha256(payload.encode('utf-8')).hexdigest(),
                          'LICENSE': sha256(license_text.encode('utf-8')).hexdigest()}}
    (target / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
