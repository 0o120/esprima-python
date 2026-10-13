"""Development-only regexp syntax check against pinned Node 24.15.0.

Node is an independent oracle; esprima never imports or invokes it at runtime.
Run from repository root: python tools/check_regexp_reference.py
"""
from pathlib import Path
import itertools
import json
import random
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from esprima.regexp_validator import validate_regexp, RegExpSyntaxError

REFERENCE_NODE_VERSION = 'v24.15.0'
version = subprocess.check_output(['node', '--version'], text=True).strip()
if version != REFERENCE_NODE_VERSION:
    raise SystemExit('Expected Node ' + REFERENCE_NODE_VERSION + ', found ' + version)

atoms = ['', 'a', '.', '^', '$', r'\b', r'\B', r'\a', r'\x00', r'\xA', r'\u', r'\u{61}',
         r'\c', r'\cA', r'\c_', r'\0', r'\07', r'\8', r'\1', r'\k', r'\k<a>',
         r'\p{L}', r'\p{gc=Lu}', r'\P{ASCII}', r'\p{RGI_Emoji}', '[a-z]', '[z-a]',
         r'[\d-a]', '[\U0001F600-\U0001F601]', '[\U0001F600-a]', '[a-\U0001F600]',
         '[]', '[^]', '[[]', '[]]', '[a&&b]', '[a--b]', r'[\q{ab|cd}]']
quantifiers = ['', '*', '+', '?', '{0}', '{1,2}', '{2,1}', '{2,}', '{a}', '{', '??', '++', '{1}?']
patterns = {atom + quantifier for atom, quantifier in itertools.product(atoms, quantifiers)}
groups = ['({})', '(?:{})', '(?={})', '(?!{})', '(?<={})', '(?<!{})', '(?<a>{})',
          '(?i:{})', '(?i-:{})', '(?im-s:{})', '(?i-i:{})', '(?g:{})', '(?P<a>{})']
patterns.update(group.format(atom) + suffix for group, atom, suffix in itertools.product(groups, atoms, ['', '*', '?']))
class_atoms = ['a', 'b', '-', '_', '&', '!', '(', ')', '/', '{', '}', '[a]', '[^a]',
               r'\d', r'\p{L}', r'\p{RGI_Emoji}', r'\q{a}', r'\q{ab}', r'\q{}', r'\q{a|b}',
               r'\q{a|}', r'\u{61}', r'\uD800', r'\uDC00', r'\c_']
patterns.update('[' + '^' * negative + a + op + b + ']' for negative, a, op, b in
                itertools.product([False, True], class_atoms, ['', '-', '--', '&&'], class_atoms))
patterns.update(['(?<a>x)|(?<a>y)', '(?<a>x)(?<a>y)', '(?<a>(?<a>x))',
                 '(?<a>x)|(?:(?<a>y)|(?<a>z))', '(?:(?<a>x)|y)(?:(?<a>z)|w)',
                 r'(?<a>x)\k', r'(?<a>x)[\k]', r'\k<1>', r'\k<1>(?<a>x)',
                 r'(?<\u{1D49C}>x)\k<\u{1D49C}>',
                 r'[\uD83D\uDE00-\uD83D\uDE4F]'])
cases = [[pattern, flags] for pattern in sorted(patterns) for flags in ['', 'u', 'v']]
# Bounded, reproducible malformed/nested grammar probes; no fixture is executed.
rng = random.Random(1202026)
fuzz_atoms = ['a', '.', '^', '$', r'\b', r'\B', r'\1', r'\3', r'\09', r'\8',
              r'\k<foo>', r'\c', '}', ']', r'\x', r'\u{2}', r'\p{L}', '[a]',
              r'[\d-a]', '[a&&b]', r'[\q{a|}]', r'[\q{ab}]', '[^]',
              '[\\]', '[a--b]', r'\q', '\\']
fuzz_groups = ['({})', '(?:{})', '(?={})', '(?!{})', '(?<={})', '(?<!{})',
               '(?<foo>{})', '(?<bar>{})', '(?i:{})', '(?m-i:{})', '(?is-im:{})', '[{}]']
fuzz_quantifiers = ['', '?', '*', '+', '??', '{1}', '{1,2}?', '{3,2}', '{2,}', '{1', '{,2}', '{foo}']


def fuzz_pattern(depth):
    if not depth or rng.random() < 0.5:
        return rng.choice(fuzz_atoms) + rng.choice(fuzz_quantifiers)
    choice = rng.randrange(3)
    if choice == 0:
        return rng.choice(fuzz_groups).format(fuzz_pattern(depth - 1)) + rng.choice(fuzz_quantifiers)
    if choice == 1:
        return fuzz_pattern(depth - 1) + '|' + fuzz_pattern(depth - 1)
    return fuzz_pattern(depth - 1) + fuzz_pattern(depth - 1)


cases.extend(sorted({(fuzz_pattern(4), rng.choice(['', 'u', 'v'])) for _ in range(60000)}))
cases.extend([['(?<a>(?<a>x)|y)', ''], ['(?<a>(?<a>x)|y)', 'u'], ['(?<a>(?<a>x)|y)', 'v']])
# Node 24 incorrectly accepts these nested duplicate names. The dated 2026
# MightBothParticipate early error is authoritative (see the corpus README).
ENGINE_DIFFERENCES = {
    ('(?<a>(?<a>x)|y)', ''): False,
    ('(?<a>(?<a>x)|y)', 'u'): False,
    ('(?<a>(?<a>x)|y)', 'v'): False,
    ('(?<bar>(?<bar>}??)+|^{,2}){2,}', ''): False,
}
script = """
const fs = require('fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(input.map(([pattern, flags]) => {
  try { new RegExp(pattern, flags); return true; }
  catch (e) { if (e instanceof SyntaxError) return false; throw e; }
})));
"""
answers = json.loads(subprocess.check_output(['node', '-e', script], input=json.dumps(cases), text=True))
mismatches = []
reference_differences = []
for (pattern, flags), expected in zip(cases, answers):
    if (pattern, flags) in ENGINE_DIFFERENCES:
        specification_result = ENGINE_DIFFERENCES[pattern, flags]
        if expected != specification_result:
            reference_differences.append({'pattern': pattern, 'flags': flags, 'node': expected, 'specification': specification_result})
        expected = specification_result
    try:
        validate_regexp(pattern, flags)
        actual = True
    except RegExpSyntaxError:
        actual = False
    if expected != actual:
        mismatches.append({'pattern': pattern, 'flags': flags, 'expected': expected, 'actual': actual})
print(json.dumps({'cases': len(cases), 'node': version, 'mismatches': len(mismatches),
                  'documentedEngineDifferences': reference_differences, 'examples': mismatches[:80]}, indent=2))
if mismatches:
    (Path(__file__).resolve().parents[1] / 'regexp-differential-mismatches.json').write_text(json.dumps(mismatches, indent=2), encoding='utf-8')
    raise SystemExit(1)
