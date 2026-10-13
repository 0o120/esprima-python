"""Read-only Test262 positive grammar audit against the published 2026 scope.

Usage: python tools/check_grammar_reference.py PATH_TO_TEST262 OUTPUT.json
No fixture program is executed. Parser failures are checked with pinned Acorn
as a second syntax oracle. Draft proposals and explicit resource management
are excluded, following the dated ECMAScript 2026 project contract.
The seven Annex B.3.9 browser-optional call-target cases are reported explicitly
under optional_policy_exclusions, with the chosen policy and dated clause URL.
"""
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import esprima

REVISION = '2e0a56762801e275a9fdf96dc49d90ba0cddcf63'
REFERENCE_ACORN_VERSION = '8.19.0'
OPTIONAL_POLICY_CLAUSE = 'https://tc39.es/ecma262/2026/#sec-runtime-errors-for-function-call-assignment-targets'
OPTIONAL_POLICY_REASON = ('Intentional omission of normative-optional Annex B.3.9 browser compatibility: '
                          'function-call assignment/update/iteration targets are rejected in all modes, '
                          'preserving the prior port.')
OPTIONAL_POLICY_PATHS = frozenset(
    'test/annexB/language/expressions/assignmenttargettype/' + name + '.js'
    for name in (
        'callexpression-as-for-in-lhs', 'callexpression-as-for-of-lhs',
        'callexpression-in-compound-assignment', 'callexpression-in-postfix-update',
        'callexpression-in-prefix-update', 'callexpression',
        'cover-callexpression-and-asyncarrowhead',
    )
)


def array(metadata, name):
    match = re.search(r'^' + name + r':\s*\[([^\]]*)\]', metadata, re.MULTILINE)
    if match:
        return [value.strip().strip('"\'') for value in match.group(1).split(',') if value.strip()]
    match = re.search(r'^' + name + r':\s*\n((?:[ \t]+-[^\n]*\n?)+)', metadata, re.MULTILINE)
    return re.findall(r'^\s*-\s*(\S+)', match.group(1), re.MULTILINE) if match else []


def strict_source(source):
    if source.startswith('#!'):
        end = next((i + 1 for i, ch in enumerate(source) if ch in '\r\n\u2028\u2029'), len(source))
        if source[end - 1:end] == '\r' and source[end:end + 1] == '\n':
            end += 1
        return source[:end] + '\n"use strict";\n' + source[end:]
    return '"use strict";\n' + source


def main():
    checkout = Path(sys.argv[1]).resolve()
    output = Path(sys.argv[2]).resolve()
    revision = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != REVISION:
        raise SystemExit('Test262 checkout differs from the pinned revision')
    proposed_section = (checkout / 'features.txt').read_text(encoding='utf-8').split('## Standard language features')[0]
    excluded = {line.split('#', 1)[0].strip() for line in proposed_section.splitlines() if line.split('#', 1)[0].strip()}
    excluded.add('explicit-resource-management')
    omitted = Counter()
    failures = []
    oracle_sources = []
    accepted = 0
    source_count = 0
    mode_counts = Counter()
    optional_policy_exclusions = []
    started = time.monotonic()
    selected_paths = sorted(set((checkout / 'test' / 'language').rglob('*.js')) |
                            set((checkout / 'test' / 'annexB' / 'language').rglob('*.js')))
    for path in selected_paths:
        source = path.read_text(encoding='utf-8')
        metadata_match = re.search(r'/\*---(.*?)---\*/', source, re.DOTALL)
        if not metadata_match:
            omitted['non-test helper fixtures'] += 1
            continue
        metadata = metadata_match.group(1)
        features = array(metadata, 'features')
        out_of_scope = set(features) & excluded
        if out_of_scope:
            omitted.update(sorted(out_of_scope))
            continue
        if re.search(r'phase:\s*parse', metadata):
            omitted['parse-phase negative (positive audit)'] += 1
            continue
        flags = array(metadata, 'flags')
        source_count += 1
        relative = path.relative_to(checkout).as_posix()
        optional_policy = relative in OPTIONAL_POLICY_PATHS
        if 'module' in flags:
            modes = ['module']
        elif 'raw' in flags or 'noStrict' in flags:
            modes = ['script']
        elif 'onlyStrict' in flags:
            modes = ['strict']
        else:
            modes = ['script', 'strict']
        for mode in modes:
            mode_counts[mode] += 1
            text = strict_source(source) if mode == 'strict' else source
            parse = esprima.parseModule if mode == 'module' else esprima.parseScript
            try:
                parse(text)
                if optional_policy:
                    raise AssertionError('Parser accepted call target disabled by the compatibility policy')
                accepted += 1
            except Exception as error:
                if optional_policy and isinstance(error, esprima.Error) and 'Invalid left-hand side' in str(error):
                    optional_policy_exclusions.append({'path': relative, 'mode': mode,
                                                       'reason': OPTIONAL_POLICY_REASON,
                                                       'clause': OPTIONAL_POLICY_CLAUSE,
                                                       'parserRejected': True})
                else:
                    failures.append({'path': relative, 'mode': mode, 'features': features,
                                     'exception': type(error).__name__, 'message': str(error),
                                     'index': getattr(error, 'index', None)})
                    oracle_sources.append({'source': text, 'sourceType': 'module' if mode == 'module' else 'script'})
                    if len(failures) <= 15:
                        print(json.dumps({'failure': failures[-1]}), flush=True)
            checked = accepted + len(failures) + len(optional_policy_exclusions)
            if checked % 2000 == 0:
                print(json.dumps({'progress': checked, 'accepted': accepted, 'failures': len(failures),
                                  'optional_policy_exclusions': len(optional_policy_exclusions)}), flush=True)
    oracle = """
const fs = require('fs'), acorn = require('./tools/reference/node_modules/acorn');
if (acorn.version !== '8.19.0') throw new Error('Expected pinned Acorn 8.19.0');
process.stdout.write(JSON.stringify(JSON.parse(fs.readFileSync(0, 'utf8')).map(item => {
  try { acorn.parse(item.source, {ecmaVersion: 2026, sourceType: item.sourceType}); return {accepted: true}; }
  catch (e) { return {accepted: false, message: e.message}; }
})));
"""
    results = json.loads(subprocess.check_output(['node', '-e', oracle], input=json.dumps(oracle_sources), text=True, cwd=ROOT)) if oracle_sources else []
    for failure, reference in zip(failures, results):
        failure['acorn'] = reference
    groups = Counter('/'.join(failure['path'].split('/')[2:4]) for failure in failures)
    summary = {'test262Revision': revision, 'target': 'ECMAScript 2026',
               'referenceAcornVersion': REFERENCE_ACORN_VERSION,
               'scope': 'Positive grammar acceptance only; fixture programs are never executed.',
               'sourceFiles': source_count,
               'coreSourceFiles': source_count - len({case['path'] for case in optional_policy_exclusions}),
               'modeChecks': accepted + len(failures) + len(optional_policy_exclusions),
               'coreModeChecks': accepted + len(failures), 'modeCounts': dict(mode_counts),
               'optional_policy_exclusions': optional_policy_exclusions,
               'accepted': accepted, 'failures': len(failures), 'omitted': dict(omitted),
               'seconds': round(time.monotonic() - started, 2), 'failureGroups': dict(groups.most_common()),
               'failureCases': failures}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({key: value for key, value in summary.items() if key != 'failureCases'}, indent=2))
    for failure in failures[:20]:
        print(json.dumps(failure))
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
