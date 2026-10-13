"""Freeze reviewed positive grammar regressions from a Test262 audit report.

Usage: python tools/freeze_grammar_corpus.py CHECKOUT AUDIT.json DESTINATION
The report must come from check_grammar_reference.py and the pinned revision.
Only cases independently accepted by Acorn are selected. No fixture is run.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REVISION = '2e0a56762801e275a9fdf96dc49d90ba0cddcf63'


def main():
    checkout, report_path, destination = (Path(value).resolve() for value in sys.argv[1:4])
    revision = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip()
    report = json.loads(report_path.read_text(encoding='utf-8'))
    if revision != REVISION or report['test262Revision'] != REVISION:
        raise SystemExit('Checkout/report differs from the pinned Test262 revision')
    cases = []
    for failure in report['failureCases']:
        if not failure['acorn']['accepted']:
            continue
        relative = failure['path']
        source = (checkout / relative).read_bytes()
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source)
        cases.append({'path': relative, 'sha256': hashlib.sha256(source).hexdigest(),
                      'mode': failure['mode'], 'features': failure['features'],
                      'parseNegative': False, 'originalFinding': failure['message']})
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'LICENSE').write_bytes((checkout / 'LICENSE').read_bytes())
    manifest = {'upstream': 'https://github.com/tc39/test262', 'revision': REVISION,
                'languageTarget': 'ECMAScript 2026',
                'scope': 'Reviewed positive grammar regressions; original programs are never executed.',
                'caseCount': len(cases), 'cases': cases}
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    print('Frozen %s positive grammar regressions' % len(cases))


if __name__ == '__main__':
    main()
