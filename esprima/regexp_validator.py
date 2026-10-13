"""ECMAScript 2026 regular-expression *syntax* validation.

This module deliberately does not compile patterns with Python's regex engines:
their grammars and Unicode/flag semantics are different from ECMAScript's.
The recursive-descent grammar includes the Annex B non-Unicode productions,
Unicode property escapes, Unicode set notation, and regexp modifiers.
"""

from functools import lru_cache

from .character import Character
from ._regexp_properties import BINARY_PROPERTIES, GENERAL_CATEGORIES, SCRIPTS


class RegExpSyntaxError(ValueError):
    """The supplied pattern/flags do not satisfy the ECMAScript grammar."""


class RegExpEditionError(RegExpSyntaxError):
    """Valid modern regexp syntax exceeds the selected language edition."""


def normalize_ecma_version(value=2026):
    if value == 'latest':
        return 2026
    if type(value) is not int or value not in (5, *range(2015, 2027)):
        raise ValueError('ecmaVersion must be 5 or an edition from 2015 to 2026')
    return value


_SYNTAX = frozenset('^$\\.*+?()[]{}|/')
_SET_RESERVED = frozenset(r'()[]{}\/|-')
_DOUBLE_RESERVED = frozenset('!#$%&*+,.:;<=>?@^`~')
_STRING_PROPERTIES = frozenset((
    'Basic_Emoji', 'Emoji_Keycap_Sequence', 'RGI_Emoji_Modifier_Sequence',
    'RGI_Emoji_Flag_Sequence', 'RGI_Emoji_Tag_Sequence',
    'RGI_Emoji_ZWJ_Sequence', 'RGI_Emoji',
))


def _decimal_less(a, b):
    a, b = a.lstrip('0') or '0', b.lstrip('0') or '0'
    return len(a) < len(b) or len(a) == len(b) and a < b


class _Validator:
    def __init__(self, pattern, flags, ecma_version=2026):
        self.ecma_version = normalize_ecma_version(ecma_version)
        self.features = {}
        if any(flag not in 'dgimsuvy' for flag in flags) or len(set(flags)) != len(flags):
            raise RegExpSyntaxError('Invalid or duplicate regular-expression flag')
        if 'u' in flags and 'v' in flags:
            raise RegExpSyntaxError('The u and v flags are mutually exclusive')
        for flag, edition in (('u', 2015), ('y', 2015), ('s', 2018), ('d', 2022), ('v', 2024)):
            if flag in flags:
                self.require_feature('RegExp flag ' + flag, edition)
        self.unicode = 'u' in flags or 'v' in flags
        self.sets = 'v' in flags
        if self.unicode:
            self.p = pattern
        else:
            # Legacy patterns are grammars over UTF-16 code units, including
            # literal astral characters and lone surrogates.
            self.p = ''.join(ch if ord(ch) <= 0xFFFF else
                             chr(0xD800 + ((ord(ch) - 0x10000) >> 10)) +
                             chr(0xDC00 + ((ord(ch) - 0x10000) & 0x3FF))
                             for ch in pattern)
        self.n = len(self.p)
        self.i = 0
        self.captures = 0
        self.names = {}
        self.numeric_refs = []
        self.named_refs = []
        self.disjunction_id = 0
        self.path = []
        self.has_named_captures = self._has_named_captures()

    def require_feature(self, name, edition):
        self.features[name] = edition
        if self.ecma_version < edition:
            raise RegExpEditionError('%s requires ECMAScript %s' % (name, edition))

    def _has_named_captures(self):
        escaped = False
        in_class = False
        for i, ch in enumerate(self.p):
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == '[':
                in_class = True
            elif ch == ']':
                in_class = False
            elif not in_class and self.p.startswith('(?<', i) and self.p[i + 3:i + 4] not in ('=', '!'):
                return True
        return False

    def fail(self, message='Invalid regular-expression pattern'):
        raise RegExpSyntaxError('%s at pattern offset %s' % (message, self.i))

    def peek(self, offset=0):
        at = self.i + offset
        return self.p[at] if at < self.n else ''

    def take(self, value):
        if self.p.startswith(value, self.i):
            self.i += len(value)
            return True
        return False

    def validate(self):
        self.disjunction()
        if self.i != self.n:
            self.fail('Unmatched closing parenthesis')
        if self.unicode:
            limit = str(self.captures)
            if any(_decimal_less(limit, ref) for ref in self.numeric_refs):
                self.fail('Invalid numeric backreference')
        for name in self.named_refs:
            if name not in self.names:
                self.fail('Unknown named backreference')

    def disjunction(self):
        ident = self.disjunction_id
        self.disjunction_id += 1
        original = self.path
        branch = 0
        while True:
            self.path = original + [(ident, branch)]
            while self.i < self.n and self.peek() not in '|)':
                self.term()
            if not self.take('|'):
                break
            branch += 1
        self.path = original

    def term(self):
        ch = self.peek()
        quantifiable = True
        if ch in '^$':
            self.i += 1
            quantifiable = False
        elif ch == '\\' and self.peek(1) in ('b', 'B'):
            self.i += 2
            quantifiable = False
        elif ch == '(':
            quantifiable = self.group()
        elif ch == '[':
            self.character_class()
        elif ch == '\\':
            self.escape()
        elif ch in '*+?':
            self.fail('Nothing to repeat')
        elif ch == '{':
            if self.quantifier(check_only=True):
                self.fail('Nothing to repeat')
            if self.unicode:
                self.fail('Invalid quantifier')
            self.i += 1
        elif self.unicode and ch in ']}':
            self.fail('Unescaped syntax character')
        else:
            self.i += 1
        repeated = self.quantifier()
        if repeated and not quantifiable:
            self.fail('Assertion cannot be quantified')

    def quantifier(self, check_only=False):
        start = self.i
        ch = self.peek()
        if ch and ch in '*+?':
            if not check_only:
                self.i += 1
                self.take('?')
            return True
        if ch != '{':
            return False
        j = self.i + 1
        lower_start = j
        while j < self.n and '0' <= self.p[j] <= '9':
            j += 1
        if lower_start == j:
            return False
        lower = self.p[lower_start:j]
        upper = lower
        if j < self.n and self.p[j] == ',':
            j += 1
            upper_start = j
            while j < self.n and '0' <= self.p[j] <= '9':
                j += 1
            upper = self.p[upper_start:j] or None
        if j == self.n or self.p[j] != '}':
            return False
        if upper is not None and _decimal_less(upper, lower):
            self.fail('Quantifier bounds are out of order')
        if not check_only:
            self.i = j + 1
            self.take('?')
        else:
            self.i = start
        return True

    def group(self):
        self.i += 1
        assertion = False
        lookahead = False
        name = None
        capturing = True
        if self.take('?'):
            capturing = False
            if self.take(':'):
                pass
            elif self.take('=') or self.take('!'):
                assertion = True
                lookahead = True
            elif self.take('<'):
                if self.take('=') or self.take('!'):
                    self.require_feature('RegExp lookbehind assertions', 2018)
                    assertion = True
                else:
                    self.require_feature('RegExp named capture groups', 2018)
                    capturing = True
                    name = self.group_name()
            else:
                self.modifiers()
        if capturing:
            self.captures += 1
            if name is not None:
                for other_path in self.names.get(name, []):
                    # Duplicate names are permitted only in disjoint alternatives.
                    other = dict(other_path)
                    if not any(key in other and other[key] != branch for key, branch in self.path):
                        self.fail('Duplicate capture group name')
                if name in self.names:
                    self.require_feature('RegExp disjoint duplicate capture names', 2025)
                self.names.setdefault(name, []).append(self.path[:])
        self.disjunction()
        if not self.take(')'):
            self.fail('Unterminated group')
        return not assertion or lookahead and not self.unicode

    def modifiers(self):
        enabled = []
        disabled = []
        while self.peek() and self.peek() in 'ims':
            enabled.append(self.peek())
            self.i += 1
        if self.take('-'):
            while self.peek() and self.peek() in 'ims':
                disabled.append(self.peek())
                self.i += 1
        all_flags = enabled + disabled
        if not all_flags or len(set(all_flags)) != len(all_flags) or not self.take(':'):
            self.fail('Invalid regular-expression modifiers')
        self.require_feature('RegExp scoped modifiers', 2025)

    def group_name(self):
        chars = []
        while self.i < self.n and self.peek() != '>':
            if self.take('\\u'):
                cp = self.unicode_escape(force=True)
                ch = chr(cp)
            else:
                ch = self.peek()
                self.i += 1
                if 0xD800 <= ord(ch) <= 0xDBFF and self.peek() and 0xDC00 <= ord(self.peek()) <= 0xDFFF:
                    ch = chr(0x10000 + ((ord(ch) - 0xD800) << 10) + ord(self.peek()) - 0xDC00)
                    self.i += 1
            if ch == '\\' or not (Character.isIdentifierStart(ch) if not chars else Character.isIdentifierPart(ch)):
                self.fail('Invalid capture group name')
            chars.append(ch)
        if not chars or not self.take('>'):
            self.fail('Invalid capture group name')
        return ''.join(chars)

    def hex_escape(self, count):
        digits = self.p[self.i:self.i + count]
        if len(digits) != count or any(ch not in '0123456789abcdefABCDEF' for ch in digits):
            return None
        self.i += count
        return int(digits, 16)

    def unicode_escape(self, force=False):
        start = self.i
        if (self.unicode or force) and self.take('{'):
            digits_start = self.i
            while self.peek() and self.peek() in '0123456789abcdefABCDEF':
                self.i += 1
            digits = self.p[digits_start:self.i]
            if not digits or not self.take('}'):
                self.fail('Invalid Unicode escape')
            cp = int(digits, 16)
            if cp > 0x10FFFF:
                self.fail('Unicode escape out of range')
            return cp
        cp = self.hex_escape(4)
        if cp is None:
            if self.unicode or force:
                self.fail('Invalid Unicode escape')
            self.i = start
            return ord('u')
        if (self.unicode or force) and 0xD800 <= cp <= 0xDBFF and self.take('\\u'):
            low_start = self.i
            low = self.hex_escape(4)
            if low is not None and 0xDC00 <= low <= 0xDFFF:
                return 0x10000 + ((cp - 0xD800) << 10) + low - 0xDC00
            self.i = low_start - 2
        return cp

    def property_escape(self, negative):
        self.require_feature('RegExp Unicode property escapes', 2018)
        if not self.take('{'):
            self.fail('Invalid Unicode property escape')
        start = self.i
        while self.peek() and self.peek() != '}':
            self.i += 1
        name = self.p[start:self.i]
        if not self.take('}'):
            self.fail('Unterminated Unicode property escape')
        if '=' in name:
            property_name, value = name.split('=', 1)
            valid = ((property_name in ('General_Category', 'gc') and value in GENERAL_CATEGORIES)
                     or (property_name in ('Script', 'sc', 'Script_Extensions', 'scx') and value in SCRIPTS))
            strings = False
        else:
            strings = name in _STRING_PROPERTIES
            valid = (name in GENERAL_CATEGORIES or name in BINARY_PROPERTIES
                     or self.sets and strings and not negative)
        if not valid:
            self.fail('Unknown Unicode property or value')
        return None, strings

    def escape(self, in_class=False, in_string=False):
        if not self.take('\\') or self.i == self.n:
            self.fail('Trailing backslash')
        ch = self.peek()
        self.i += 1
        if ch in 'dDsSwW':
            if in_string:
                self.fail('Character class escape in class string')
            return None, False
        if ch == 'b' and in_class:
            return 8, False
        if ch in 'fnrtv':
            return {'f': 12, 'n': 10, 'r': 13, 't': 9, 'v': 11}[ch], False
        if ch == 'c':
            letter = self.peek()
            if letter and ('a' <= letter <= 'z' or 'A' <= letter <= 'Z'):
                self.i += 1
                return ord(letter.upper()) % 32, False
            if not self.unicode and in_class and letter and ('0' <= letter <= '9' or letter == '_'):
                self.i += 1
                return ord(letter) % 32, False
            if self.unicode:
                self.fail('Invalid control escape')
            # Annex B treats an incomplete control escape as a literal backslash.
            self.i -= 1
            return 92, False
        if ch == 'x':
            cp = self.hex_escape(2)
            if cp is None:
                if self.unicode:
                    self.fail('Invalid hexadecimal escape')
                cp = ord('x')
            return cp, False
        if ch == 'u':
            return self.unicode_escape(), False
        if ch in 'pP' and self.unicode:
            if in_string:
                self.fail('Property escape in class string')
            return self.property_escape(ch == 'P')
        if ch == 'q' and self.sets and in_class:
            if in_string:
                self.fail('Nested class string')
            return self.class_string()
        if ch == 'k' and in_class and self.has_named_captures:
            self.fail('Named backreference is not allowed in a character class')
        if ch == 'k' and not in_class:
            if not self.unicode and not self.has_named_captures:
                return ord('k'), False
            if self.peek() == '<':
                self.i += 1
                self.named_refs.append(self.group_name())
                return None, False
            self.fail('Invalid named backreference')
        if '0' <= ch <= '9':
            if ch == '0':
                if self.unicode and self.peek() and '0' <= self.peek() <= '9':
                    self.fail('Invalid decimal escape')
                if not self.unicode:
                    count = 1
                    value = 0
                    while count < 3 and self.peek() and self.peek() in '01234567':
                        value = value * 8 + int(self.peek())
                        self.i += 1
                        count += 1
                    return value, False
                return 0, False
            if not in_class:
                digits = ch
                while self.peek() and '0' <= self.peek() <= '9':
                    digits += self.peek()
                    self.i += 1
                self.numeric_refs.append(digits)
                return None, False
            if self.unicode:
                self.fail('Decimal escape in character class')
            if ch in '1234567':
                value = int(ch)
                limit = 3 if ch in '123' else 2
                for _ in range(limit - 1):
                    if self.peek() and self.peek() in '01234567':
                        value = value * 8 + int(self.peek())
                        self.i += 1
                    else:
                        break
                return value, False
            return ord(ch), False
        allowed = ch in _SYNTAX or in_class and ch == '-'
        if self.sets and in_class:
            allowed = allowed or ch in _DOUBLE_RESERVED
        if self.unicode and not allowed:
            self.fail('Invalid identity escape')
        return ord(ch), False

    def class_atom(self, string=False):
        if self.peek() == '\\':
            return self.escape(in_class=True, in_string=string)
        ch = self.peek()
        if not ch:
            self.fail('Unterminated character class')
        if self.sets:
            if ch in _SET_RESERVED:
                self.fail('Unescaped Unicode-set reserved character')
            if ch in _DOUBLE_RESERVED and self.peek(1) == ch:
                self.fail('Reserved double punctuator in Unicode set')
        self.i += 1
        cp = ord(ch)
        if self.unicode and 0xD800 <= cp <= 0xDBFF and self.peek() and 0xDC00 <= ord(self.peek()) <= 0xDFFF:
            cp = 0x10000 + ((cp - 0xD800) << 10) + ord(self.peek()) - 0xDC00
            self.i += 1
        return cp, False

    def class_string(self):
        if not self.take('{'):
            self.fail('Invalid class string disjunction')
        length = 0
        strings = False
        while True:
            if self.take('|'):
                strings = strings or length != 1
                length = 0
            elif self.take('}'):
                return None, strings or length != 1
            else:
                if not self.peek():
                    self.fail('Unterminated class string disjunction')
                self.class_atom(string=True)
                length += 1

    def character_class(self):
        self.i += 1  # [
        negative = self.take('^')
        strings = False
        if self.sets:
            strings = self.set_expression()
        else:
            while self.i < self.n and self.peek() != ']':
                first, _ = self.class_atom()
                if self.peek() == '-' and self.peek(1) and self.peek(1) != ']':
                    self.i += 1
                    last, _ = self.class_atom()
                    if first is None or last is None:
                        if self.unicode:
                            self.fail('Character-class escape cannot bound a range')
                    elif first > last:
                        self.fail('Character range out of order')
        if not self.take(']'):
            self.fail('Unterminated character class')
        if negative and strings:
            self.fail('Negated Unicode set may contain strings')
        return None, strings

    def set_operand(self):
        if self.peek() == '[':
            return self.character_class()
        return self.class_atom()

    def set_expression(self):
        if self.peek() == ']':
            return False
        first, strings = self.set_operand()
        mode = None
        if self.p.startswith('&&', self.i) or self.p.startswith('--', self.i):
            mode = self.p[self.i:self.i + 2]
            self.i += 2
            if mode == '&&' and self.peek() == '&':
                self.fail('Reserved double punctuator after set intersection')
            _, other_strings = self.set_operand()
            strings = strings and other_strings if mode == '&&' else strings
            while self.p.startswith(mode, self.i):
                self.i += 2
                if mode == '&&' and self.peek() == '&':
                    self.fail('Reserved double punctuator after set intersection')
                _, other_strings = self.set_operand()
                strings = strings and other_strings if mode == '&&' else strings
            if self.peek() != ']':
                self.fail('Cannot mix Unicode-set operations without nesting')
            return strings
        # Union permits ranges, but neither range bounds nor union elements can
        # be combined directly with intersection/subtraction productions.
        while True:
            if self.peek() == '-' and self.peek(1) != '-':
                self.i += 1
                last, last_strings = self.set_operand()
                if first is None or last is None or first > last:
                    self.fail('Invalid Unicode-set range')
                strings = strings or last_strings
            if self.peek() == ']':
                return strings
            if self.p.startswith('&&', self.i) or self.p.startswith('--', self.i):
                self.fail('Cannot mix Unicode-set union and set operations')
            first, more_strings = self.set_operand()
            strings = strings or more_strings


def _validated_features(pattern, flags, ecma_version):
    validator = _Validator(pattern, flags, ecma_version)
    validator.validate()
    return tuple(validator.features.items())


_cached_features = lru_cache(maxsize=128)(_validated_features)


def _features(pattern, flags, ecma_version):
    # Exact immutable inputs avoid custom string/hash coercion and preserve
    # uncached exceptions. Bound both entry count and retained pattern size.
    if type(pattern) is str and type(flags) is str and type(ecma_version) is int and len(pattern) <= 512 and len(flags) <= 8:
        return _cached_features(pattern, flags, ecma_version)
    return _validated_features(pattern, flags, ecma_version)


def validate_regexp(pattern, flags='', ecma_version=2026):
    """Validate a JS regexp descriptor, returning None or raising RegExpSyntaxError."""
    _features(pattern, flags, ecma_version)


def regexp_features(pattern, flags=''):
    """Return feature/minimum-edition pairs from parsed grammar, not raw text."""
    return dict(_features(pattern, flags, 2026))
