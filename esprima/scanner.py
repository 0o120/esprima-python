# -*- coding: utf-8 -*-
# Copyright JS Foundation and other contributors, https://js.foundation/
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
# THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from __future__ import absolute_import, unicode_literals

import math

from .regexp_validator import validate_regexp, RegExpSyntaxError, RegExpEditionError

from .objects import Object
from .compat import xrange, unicode, uchr, uord
from .character import Character, HEX_CONV, OCTAL_CONV, ASCII_IDENTIFIER_START, ASCII_IDENTIFIER_PART
from .messages import Messages
from .token import Token


# Literal ASCII identifier characters do not include escape introducers.
_ASCII_IDENTIFIER_PART = ASCII_IDENTIFIER_PART - {'\\'}
_ASCII_IDENTIFIER_START = ASCII_IDENTIFIER_START - {'\\'}
# Longest first, indexed by the first character; single-character punctuation
# never needs to scan the multi-character vocabulary.
_PUNCTUATOR_PREFIXES = {
    '>': ('>>>=', '>>>', '>>=', '>>', '>='),
    '<': ('<<=', '<<', '<='),
    '=': ('===', '==', '=>'),
    '!': ('!==', '!='),
    '&': ('&&=', '&&', '&='),
    '|': ('||=', '||', '|='),
    '?': ('??=', '??', '?.'),
    '*': ('**=', '**', '*='),
    '+': ('++', '+='),
    '-': ('--', '-='),
    '/': ('/=',),
    '%': ('%=',),
    '^': ('^=',),
    '.': ('...',),
}
_SINGLE_PUNCTUATORS = frozenset('(){};,[].:?~<>=!+-*%&|^/')


def hexValue(ch):
    return HEX_CONV[ch]


def octalValue(ch):
    return OCTAL_CONV[ch]


class RegExp(Object):
    def __init__(self, pattern=None, flags=None):
        self.pattern = pattern
        self.flags = flags


class Position(Object):
    def __init__(self, line=None, column=None, offset=None):
        self.line = line
        self.column = column
        self.offset = offset


class SourceLocation(Object):
    def __init__(self, start=None, end=None, source=None):
        self.start = start
        self.end = end
        self.source = source


class Comment(Object):
    def __init__(self, multiLine=None, slice=None, range=None, loc=None):
        self.multiLine = multiLine
        self.slice = slice
        self.range = range
        self.loc = loc


class RawToken(Object):
    def __init__(self, type=None, value=None, pattern=None, flags=None, regex=None, octal=None, cooked=None, head=None, tail=None, lineNumber=None, lineStart=None, start=None, end=None, bigint=None, private=False, invalidEscape=False, escaped=False):
        self.bigint = bigint
        self.private = private
        self.invalidEscape = invalidEscape
        self.escaped = escaped
        self.type = type
        self.value = value
        self.pattern = pattern
        self.flags = flags
        self.regex = regex
        self.octal = octal
        self.cooked = cooked
        self.head = head
        self.tail = tail
        self.lineNumber = lineNumber
        self.lineStart = lineStart
        self.start = start
        self.end = end


class ScannerState(Object):
    def __init__(self, index=None, lineNumber=None, lineStart=None, curlyStack=None):
        self.index = index
        self.lineNumber = lineNumber
        self.lineStart = lineStart
        self.curlyStack = curlyStack


class Octal(object):
    def __init__(self, octal, code):
        self.octal = octal
        self.code = code


class Scanner(object):
    def __init__(self, code, handler):
        self.source = unicode(code) + '\x00'
        self._sourceIsAscii = self.source.isascii()
        self.errorHandler = handler
        self.trackComment = False
        self.isModule = False

        self.length = len(code)
        self.index = 0
        self.lineNumber = 1 if self.length > 0 else 0
        self.lineStart = 0
        self.curlyStack = []
        self._utf16Offsets = None
        self.hashbang = None
        # Internal indices remain scalar; public clients select diagnostic units.
        self.positionEncoding = 'scalar'
        self.ecmaVersion = 2026

    def requireFeature(self, edition, name):
        if self.ecmaVersion < edition:
            self.tolerateUnexpectedToken('%s requires ECMAScript %s' % (name, edition))

    def utf16Offset(self, index):
        """Convert a Python scalar source index to the ESTree UTF-16 unit index."""
        if self._sourceIsAscii:
            return index if 0 <= index <= self.length else min(max(index, 0), self.length)
        if self._utf16Offsets is None:
            offsets = [0]
            for ch in self.source[:-1]:
                offsets.append(offsets[-1] + (2 if ord(ch) > 0xFFFF else 1))
            self._utf16Offsets = offsets
        return self._utf16Offsets[min(max(index, 0), self.length)]

    def utf16Column(self, index, lineStart):
        if self._sourceIsAscii and 0 <= lineStart <= index <= self.length:
            return index - lineStart
        return self.utf16Offset(index) - self.utf16Offset(lineStart)

    def saveState(self):
        return ScannerState(
            index=self.index,
            lineNumber=self.lineNumber,
            lineStart=self.lineStart,
            curlyStack=self.curlyStack[:]
        )

    def restoreState(self, state):
        self.index = state.index
        self.lineNumber = state.lineNumber
        self.lineStart = state.lineStart
        if state.curlyStack is not None:
            self.curlyStack = state.curlyStack[:]

    def eof(self):
        return self.index >= self.length

    def throwUnexpectedToken(self, message=Messages.UnexpectedTokenIllegal):
        index, column = self.errorPosition()
        return self.errorHandler.throwError(index, self.lineNumber, column, message)

    def tolerateUnexpectedToken(self, message=Messages.UnexpectedTokenIllegal):
        index, column = self.errorPosition()
        self.errorHandler.tolerateError(index, self.lineNumber, column, message)

    def errorPosition(self):
        if self.positionEncoding == 'utf16':
            return self.utf16Offset(self.index), self.utf16Column(self.index, self.lineStart) + 1
        return self.index, self.index - self.lineStart + 1

    # https://tc39.github.io/ecma262/#sec-comments

    def skipSingleLineComment(self, offset):
        comments = []

        if self.trackComment:
            start = self.index - offset
            loc = SourceLocation(
                start=Position(
                    line=self.lineNumber,
                    column=self.index - self.lineStart - offset
                ),
                end=Position()
            )

        while not self.eof():
            ch = self.source[self.index]
            self.index += 1
            if Character.isLineTerminator(ch):
                if self.trackComment:
                    loc.end = Position(
                        line=self.lineNumber,
                        column=self.index - self.lineStart - 1
                    )
                    entry = Comment(
                        multiLine=False,
                        slice=[start + offset, self.index - 1],
                        range=[start, self.index - 1],
                        loc=loc
                    )
                    comments.append(entry)

                if ch == '\r' and self.source[self.index] == '\n':
                    self.index += 1

                self.lineNumber += 1
                self.lineStart = self.index
                return comments

        if self.trackComment:
            loc.end = Position(
                line=self.lineNumber,
                column=self.index - self.lineStart
            )
            entry = Comment(
                multiLine=False,
                slice=[start + offset, self.index],
                range=[start, self.index],
                loc=loc
            )
            comments.append(entry)

        return comments

    def skipMultiLineComment(self):
        comments = []

        if self.trackComment:
            comments = []
            start = self.index - 2
            loc = SourceLocation(
                start=Position(
                    line=self.lineNumber,
                    column=self.index - self.lineStart - 2
                ),
                end=Position()
            )

        while not self.eof():
            ch = self.source[self.index]
            if Character.isLineTerminator(ch):
                if ch == '\r' and self.source[self.index + 1] == '\n':
                    self.index += 1

                self.lineNumber += 1
                self.index += 1
                self.lineStart = self.index
            elif ch == '*':
                # Block comment ends with '*/'.
                if self.source[self.index + 1] == '/':
                    self.index += 2
                    if self.trackComment:
                        loc.end = Position(
                            line=self.lineNumber,
                            column=self.index - self.lineStart
                        )
                        entry = Comment(
                            multiLine=True,
                            slice=[start + 2, self.index - 2],
                            range=[start, self.index],
                            loc=loc
                        )
                        comments.append(entry)

                    return comments

                self.index += 1
            else:
                self.index += 1

        # Ran off the end of the file - the whole thing is a comment
        if self.trackComment:
            loc.end = Position(
                line=self.lineNumber,
                column=self.index - self.lineStart
            )
            entry = Comment(
                multiLine=True,
                slice=[start + 2, self.index],
                range=[start, self.index],
                loc=loc
            )
            comments.append(entry)

        self.tolerateUnexpectedToken()
        return comments

    def scanComments(self):
        comments = []

        start = self.index == 0
        while not self.eof():
            ch = self.source[self.index]

            if self.index == 0 and self.source[:2] == '#!':
                self.requireFeature(2023, 'Hashbang comments')
                end = 2
                while end < self.length and not Character.isLineTerminator(self.source[end]):
                    end += 1
                self.hashbang = self.source[2:end]
                self.index += 2
                entries = self.skipSingleLineComment(2)
                for entry in entries:
                    entry.hashbang = True
                    self.hashbang = self.source[entry.slice[0]:entry.slice[1]]
                comments.extend(entries)
                start = True
            elif Character.isWhiteSpace(ch):
                self.index += 1
            elif Character.isLineTerminator(ch):
                self.index += 1
                if ch == '\r' and self.source[self.index] == '\n':
                    self.index += 1

                self.lineNumber += 1
                self.lineStart = self.index
                start = True
            elif ch == '/':  # U+002F is '/'
                ch = self.source[self.index + 1]
                if ch == '/':
                    self.index += 2
                    comment = self.skipSingleLineComment(2)
                    if self.trackComment:
                        comments.extend(comment)

                    start = True
                elif ch == '*':  # U+002A is '*'
                    self.index += 2
                    previousLine = self.lineNumber
                    comment = self.skipMultiLineComment()
                    # Annex B HTMLCloseComment may follow a block comment
                    # containing a line terminator, even after code on that line.
                    if self.lineNumber != previousLine:
                        start = True
                    if self.trackComment:
                        comments.extend(comment)

                else:
                    break

            elif start and ch == '-' and not self.isModule:  # U+002D is '-'
                # U+003E is '>'
                if self.source[self.index + 1:self.index + 3] == '->':
                    # '-->' is a single-line comment
                    self.index += 3
                    comment = self.skipSingleLineComment(3)
                    if self.trackComment:
                        comments.extend(comment)

                else:
                    break

            elif ch == '<' and not self.isModule:  # U+003C is '<'
                if self.source[self.index + 1:self.index + 4] == '!--':
                    self.index += 4  # `<!--`
                    comment = self.skipSingleLineComment(4)
                    if self.trackComment:
                        comments.extend(comment)

                else:
                    break

            else:
                break

        return comments

    # https://tc39.github.io/ecma262/#sec-future-reserved-words

    def isFutureReservedWord(self, id):
        return id in self.isFutureReservedWord.set
    isFutureReservedWord.set = set((
        'enum',
        'export',
        'import',
        'super',
    ))

    def isStrictModeReservedWord(self, id):
        return id in self.isStrictModeReservedWord.set
    isStrictModeReservedWord.set = set((
        'implements',
        'interface',
        'package',
        'private',
        'protected',
        'public',
        'static',
        'yield',
        'let',
    ))

    def isRestrictedWord(self, id):
        return id in self.isRestrictedWord.set
    isRestrictedWord.set = set((
        'eval', 'arguments',
    ))

    # https://tc39.github.io/ecma262/#sec-keywords

    def isKeyword(self, id):
        return id in self.isKeyword.set
    isKeyword.set = set((
        'if', 'in', 'do',

        'var', 'for', 'new',
        'try', 'let',

        'this', 'else', 'case',
        'void', 'with', 'enum',

        'while', 'break', 'catch',
        'throw', 'const', 'yield',
        'class', 'super',

        'return', 'typeof', 'delete',
        'switch', 'export', 'import',

        'default', 'finally', 'extends',

        'function', 'continue', 'debugger',

        'instanceof',
    ))

    def codePointAt(self, i):
        cp = ord(self.source[i])
        if 0xD800 <= cp <= 0xDBFF and i + 1 < self.length:
            low = ord(self.source[i + 1])
            if 0xDC00 <= low <= 0xDFFF:
                return 0x10000 + ((cp - 0xD800) << 10) + low - 0xDC00
        return cp

    def scanHexEscape(self, prefix):
        length = 4 if prefix == 'u' else 2
        code = 0

        for i in xrange(length):
            if not self.eof() and Character.isHexDigit(self.source[self.index]):
                ch = self.source[self.index]
                self.index += 1
                code = code * 16 + hexValue(ch)
            else:
                return None

        return uchr(code)

    def scanUnicodeCodePointEscape(self):
        self.requireFeature(2015, 'Unicode code-point escapes')
        ch = self.source[self.index]
        code = 0

        # At least, one hex digit is required.
        if not Character.isHexDigit(ch):
            self.throwUnexpectedToken()

        while not self.eof():
            ch = self.source[self.index]
            self.index += 1
            if not Character.isHexDigit(ch):
                break

            code = code * 16 + hexValue(ch)

        if code > 0x10FFFF or ch != '}':
            self.throwUnexpectedToken()

        return Character.fromCodePoint(code)

    def getIdentifier(self):
        start = self.index
        source = self.source
        if source[start] not in _ASCII_IDENTIFIER_START:
            return self.getComplexIdentifier()
        index = start + 1
        length = self.length
        while index < length:
            ch = source[index]
            if ch in _ASCII_IDENTIFIER_PART:
                index += 1
            elif ch == '\\' or ch >= '\x80':
                # Decode and validate the complete identifier with its first-
                # character rules, preserving escapes, Unicode and surrogates.
                return self.getComplexIdentifier()
            else:
                break
        self.index = index
        return source[start:index]

    def getComplexIdentifier(self):
        result = []
        first = True
        while not self.eof():
            cp = self.codePointAt(self.index)
            ch = chr(cp)
            if ch == '\\':
                self.index += 1
                if self.source[self.index] != 'u':
                    self.throwUnexpectedToken()
                self.index += 1
                if self.source[self.index] == '{':
                    self.index += 1
                    ch = self.scanUnicodeCodePointEscape()
                else:
                    ch = self.scanHexEscape('u')
                if ch is None or not (Character.isIdentifierStart(ch) if first else Character.isIdentifierPart(ch)) or ch == '\\':
                    self.throwUnexpectedToken()
            else:
                if not (Character.isIdentifierStart(ch) if first else Character.isIdentifierPart(ch)):
                    if first:
                        self.throwUnexpectedToken()
                    break
                if cp > 0xFFFF:
                    self.requireFeature(2015, 'Astral identifiers')
                self.index += 2 if cp > 0xFFFF and ord(self.source[self.index]) <= 0xFFFF else 1
            result.append(ch)
            first = False
        return ''.join(result)

    def octalToDecimal(self, ch):
        # \0 is not octal escape sequence
        octal = ch != '0' or Character.isDecimalDigit(self.source[self.index])
        code = octalValue(ch)

        if not self.eof() and Character.isOctalDigit(self.source[self.index]):
            octal = True
            code = code * 8 + octalValue(self.source[self.index])
            self.index += 1

            # 3 digits are only allowed when string starts
            # with 0, 1, 2, 3
            if ch in '0123' and not self.eof() and Character.isOctalDigit(self.source[self.index]):
                code = code * 8 + octalValue(self.source[self.index])
                self.index += 1

        return Octal(octal, code)

    # https://tc39.github.io/ecma262/#sec-names-and-keywords

    def scanIdentifier(self):
        start = self.index

        # Backslash (U+005C) starts an escaped character.
        id = self.getComplexIdentifier() if self.source[start] == '\\' else self.getIdentifier()

        # There is no keyword or literal with only one character.
        # Thus, it must be an identifier.
        if len(id) == 1:
            type = Token.Identifier
        elif self.isKeyword(id):
            type = Token.Keyword
        elif id == 'null':
            type = Token.NullLiteral
        elif id == 'true' or id == 'false':
            type = Token.BooleanLiteral
        else:
            type = Token.Identifier

        return RawToken(
            type=type,
            value=id,
            escaped='\\' in self.source[start:self.index],
            lineNumber=self.lineNumber,
            lineStart=self.lineStart,
            start=start,
            end=self.index
        )

    # https://tc39.github.io/ecma262/#sec-punctuators

    def scanPunctuator(self):
        start = self.index
        value = self.source[start]
        if value not in _SINGLE_PUNCTUATORS:
            self.throwUnexpectedToken()
        for candidate in _PUNCTUATOR_PREFIXES.get(value, ()):
            if self.source.startswith(candidate, self.index):
                # The optional-chain punctuator is excluded before a decimal digit.
                if candidate == '?.' and Character.isDecimalDigit(self.source[self.index + 2]):
                    continue
                value = candidate
                break
        self.index += len(value)
        if value in ('...', '=>'):
            self.requireFeature(2015, 'Modern punctuators')
        elif value in ('**', '**='):
            self.requireFeature(2016, 'Exponentiation')
        elif value in ('?.', '??'):
            self.requireFeature(2020, 'Optional chaining/nullish coalescing')
        elif value in ('&&=', '||=', '??='):
            self.requireFeature(2021, 'Logical assignment')
        if value == '{':
            self.curlyStack.append('{')
        elif value == '}' and self.curlyStack:
            self.curlyStack.pop()
        return RawToken(type=Token.Punctuator, value=value, lineNumber=self.lineNumber,
                        lineStart=self.lineStart, start=start, end=self.index)

    # https://tc39.github.io/ecma262/#sec-literals-numeric-literals

    def scanHexLiteral(self, start):
        num = ''

        while not self.eof():
            if not Character.isHexDigit(self.source[self.index]):
                break

            num += self.source[self.index]
            self.index += 1

        if len(num) == 0:
            self.throwUnexpectedToken()

        if Character.isIdentifierStart(self.source[self.index]):
            self.throwUnexpectedToken()

        return RawToken(
            type=Token.NumericLiteral,
            value=int(num, 16),
            lineNumber=self.lineNumber,
            lineStart=self.lineStart,
            start=start,
            end=self.index
        )

    def scanBinaryLiteral(self, start):
        num = ''

        while not self.eof():
            ch = self.source[self.index]
            if ch != '0' and ch != '1':
                break

            num += self.source[self.index]
            self.index += 1

        if len(num) == 0:
            # only 0b or 0B
            self.throwUnexpectedToken()

        if not self.eof():
            ch = self.source[self.index]
            if Character.isIdentifierStart(ch) or Character.isDecimalDigit(ch):
                self.throwUnexpectedToken()

        return RawToken(
            type=Token.NumericLiteral,
            value=int(num, 2),
            lineNumber=self.lineNumber,
            lineStart=self.lineStart,
            start=start,
            end=self.index
        )

    def scanOctalLiteral(self, prefix, start):
        num = ''
        octal = False

        if Character.isOctalDigit(prefix[0]):
            octal = True
            num = '0' + self.source[self.index]
        self.index += 1

        while not self.eof():
            if not Character.isOctalDigit(self.source[self.index]):
                break

            num += self.source[self.index]
            self.index += 1

        if not octal and len(num) == 0:
            # only 0o or 0O
            self.throwUnexpectedToken()

        if Character.isIdentifierStart(self.source[self.index]) or Character.isDecimalDigit(self.source[self.index]):
            self.throwUnexpectedToken()

        return RawToken(
            type=Token.NumericLiteral,
            value=int(num, 8),
            octal=octal,
            lineNumber=self.lineNumber,
            lineStart=self.lineStart,
            start=start,
            end=self.index
        )

    def isImplicitOctalLiteral(self):
        # Implicit octal, unless there is a non-octal digit.
        # (Annex B.1.1 on Numeric Literals)
        for i in xrange(self.index + 1, self.length):
            ch = self.source[i]
            if ch in '89':
                return False
            if not Character.isOctalDigit(ch):
                return True
        return True

    def _scanDigits(self, allowed, required=True):
        start = self.index
        digits = []
        previousDigit = False
        while not self.eof():
            ch = self.source[self.index]
            if ch in allowed:
                digits.append(ch)
                self.index += 1
                previousDigit = True
            elif ch == '_':
                self.requireFeature(2021, 'Numeric separators')
                if not previousDigit or self.source[self.index + 1] not in allowed:
                    self.throwUnexpectedToken()
                previousDigit = False
                self.index += 1
            else:
                break
        if required and self.index == start:
            self.throwUnexpectedToken()
        return ''.join(digits)

    def scanNumericLiteral(self):
        start = self.index
        base = 10
        legacy = False
        fraction = False
        exponent = False
        digits = ''
        first = self.source[self.index]
        if first == '0' and self.source[self.index + 1] in 'xXbBoO':
            prefix = self.source[self.index + 1].lower()
            if prefix in ('b', 'o'):
                self.requireFeature(2015, 'Binary/octal numeric literals')
            base, allowed = {'x': (16, '0123456789abcdefABCDEF'), 'b': (2, '01'), 'o': (8, '01234567')}[prefix]
            self.index += 2
            digits = self._scanDigits(allowed)
        else:
            if first != '.':
                digits = self._scanDigits('0123456789')
                rawInteger = self.source[start:self.index]
                if len(rawInteger) > 1 and rawInteger.startswith('0'):
                    if '_' in rawInteger:
                        self.throwUnexpectedToken()
                    legacy = True
                    if all(ch in '01234567' for ch in rawInteger):
                        base = 8
            if self.source[self.index] == '.' and base == 10:
                fraction = True
                self.index += 1
                digits += '.' + self._scanDigits('0123456789', required=first == '.')
            if self.source[self.index] in 'eE' and base == 10:
                exponent = True
                self.index += 1
                digits += 'e'
                if self.source[self.index] in '+-':
                    digits += self.source[self.index]
                    self.index += 1
                digits += self._scanDigits('0123456789')
        bigint = None
        if self.source[self.index] == 'n':
            self.requireFeature(2020, 'BigInt literals')
            if fraction or exponent or legacy:
                self.throwUnexpectedToken()
            self.index += 1
            # Avoid Python's decimal-input digit limit for valid arbitrary-sized BigInt.
            integer = 0
            for digit in digits:
                integer = integer * base + hexValue(digit)
            if len(digits) > 4300 and base == 10:
                bigint = digits.lstrip('0') or '0'
            else:
                # Decimal serialization is performed in chunks for oversized nondecimal values.
                chunks = []
                while integer >= 10 ** 9:
                    integer, rem = divmod(integer, 10 ** 9)
                    chunks.append('%09d' % rem)
                bigint = str(integer) + ''.join(reversed(chunks))
            value = None
        else:
            try:
                value = float(int(digits, base)) if base != 10 else float(digits)
            except OverflowError:
                value = math.inf
            if math.isfinite(value) and value.is_integer():
                value = int(value)
        if Character.isIdentifierStart(self.source[self.index]) or Character.isDecimalDigit(self.source[self.index]):
            self.throwUnexpectedToken()
        return RawToken(type=Token.NumericLiteral, value=value, bigint=bigint, octal=legacy,
                        lineNumber=self.lineNumber, lineStart=self.lineStart, start=start, end=self.index)

    # https://tc39.github.io/ecma262/#sec-literals-string-literals

    def scanStringLiteral(self):
        start = self.index
        quote = self.source[start]
        assert quote in ('\'', '"'), 'String literal must starts with a quote'

        self.index += 1
        octal = False
        str = ''

        while not self.eof():
            ch = self.source[self.index]
            self.index += 1

            if ch == quote:
                quote = ''
                break
            elif ch == '\\':
                ch = self.source[self.index]
                self.index += 1
                if not ch or not Character.isLineTerminator(ch):
                    if ch == 'u':
                        if self.source[self.index] == '{':
                            self.index += 1
                            str += self.scanUnicodeCodePointEscape()
                        else:
                            unescapedChar = self.scanHexEscape(ch)
                            if not unescapedChar:
                                self.throwUnexpectedToken()

                            str += unescapedChar

                    elif ch == 'x':
                        unescaped = self.scanHexEscape(ch)
                        if not unescaped:
                            self.throwUnexpectedToken(Messages.InvalidHexEscapeSequence)

                        str += unescaped
                    elif ch == 'n':
                        str += '\n'
                    elif ch == 'r':
                        str += '\r'
                    elif ch == 't':
                        str += '\t'
                    elif ch == 'b':
                        str += '\b'
                    elif ch == 'f':
                        str += '\f'
                    elif ch == 'v':
                        str += '\x0B'
                    elif ch in ('8', '9'):
                        str += ch
                        octal = True

                    else:
                        if ch and Character.isOctalDigit(ch):
                            octToDec = self.octalToDecimal(ch)

                            octal = octToDec.octal or octal
                            str += uchr(octToDec.code)
                        else:
                            str += ch

                else:
                    self.lineNumber += 1
                    if ch == '\r' and self.source[self.index] == '\n':
                        self.index += 1

                    self.lineStart = self.index

            elif ch in ('\n', '\r'):
                break
            else:
                # ES2019's JSON superset permits literal U+2028 and U+2029 in strings.
                if ch in ('\u2028', '\u2029'):
                    self.requireFeature(2019, 'JSON-superset string literals')
                    self.lineNumber += 1
                    self.lineStart = self.index
                str += ch

        if quote != '':
            self.index = start
            self.throwUnexpectedToken()

        return RawToken(
            type=Token.StringLiteral,
            value=str,
            octal=octal,
            lineNumber=self.lineNumber,
            lineStart=self.lineStart,
            start=start,
            end=self.index
        )

    # https://tc39.github.io/ecma262/#sec-template-literal-lexical-components

    def scanTemplate(self):
        self.requireFeature(2015, 'Template literals')
        start = self.index
        head = self.source[start] == '`'
        tail = False
        cooked = []
        invalid = False
        self.index += 1
        if not head and self.curlyStack:
            self.curlyStack.pop()
        while not self.eof():
            ch = self.source[self.index]
            self.index += 1
            if ch == '`':
                tail = True
                rawEnd = self.index - 1
                break
            if ch == '$' and self.source[self.index] == '{':
                rawEnd = self.index - 1
                self.index += 1
                self.curlyStack.append('${')
                break
            if ch == '\\':
                if self.eof():
                    self.throwUnexpectedToken()
                ch = self.source[self.index]
                self.index += 1
                if Character.isLineTerminator(ch):
                    if ch == '\r' and self.source[self.index] == '\n':
                        self.index += 1
                    self.lineNumber += 1
                    self.lineStart = self.index
                elif ch in 'nrtbfv':
                    cooked.append({'n':'\n', 'r':'\r', 't':'\t', 'b':'\b', 'f':'\f', 'v':'\v'}[ch])
                elif ch in '123456789' or ch == '0' and Character.isDecimalDigit(self.source[self.index]):
                    invalid = True
                elif ch == '0':
                    cooked.append('\0')
                elif ch in 'xu':
                    escapeStart = self.index
                    if ch == 'u' and self.source[self.index] == '{':
                        self.index += 1
                        digitsStart = self.index
                        while Character.isHexDigit(self.source[self.index]):
                            self.index += 1
                        digits = self.source[digitsStart:self.index]
                        if digits and self.source[self.index] == '}' and int(digits, 16) <= 0x10FFFF:
                            self.index += 1
                            cooked.append(chr(int(digits, 16)))
                        else:
                            invalid = True
                    else:
                        size = 2 if ch == 'x' else 4
                        digits = self.source[self.index:self.index + size]
                        if len(digits) == size and all(Character.isHexDigit(d) for d in digits):
                            self.index += size
                            cooked.append(chr(int(digits, 16)))
                        else:
                            invalid = True
                            self.index = escapeStart
                else:
                    cooked.append(ch)
            elif Character.isLineTerminator(ch):
                if ch == '\r' and self.source[self.index] == '\n':
                    self.index += 1
                self.lineNumber += 1
                self.lineStart = self.index
                cooked.append('\n' if ch in '\r\n' else ch)
            else:
                cooked.append(ch)
        else:
            self.throwUnexpectedToken()
        raw = self.source[start + 1:rawEnd].replace('\r\n', '\n').replace('\r', '\n')
        if invalid and self.ecmaVersion < 2018:
            # Tagging belongs to the parser's grammar context. Before ES2018
            # an invalid escape is a lexical error in either template context.
            self.tolerateUnexpectedToken('Invalid escape sequence in template literal')
        return RawToken(type=Token.Template, value=raw, cooked=None if invalid else ''.join(cooked),
                        invalidEscape=invalid, head=head, tail=tail, lineNumber=self.lineNumber,
                        lineStart=self.lineStart, start=start, end=self.index)

    # https://tc39.github.io/ecma262/#sec-literals-regular-expression-literals

    def testRegExp(self, pattern, flags):
        try:
            validate_regexp(pattern, flags, self.ecmaVersion)
        except RegExpEditionError as error:
            self.tolerateUnexpectedToken(str(error))
        except RegExpSyntaxError:
            self.tolerateUnexpectedToken(Messages.InvalidRegExp)
        # A JavaScript regex has no Python runtime equivalent. Preserve its descriptor.
        return None

    def scanRegExpBody(self):
        ch = self.source[self.index]
        assert ch == '/', 'Regular expression literal must start with a slash'

        str = self.source[self.index]
        self.index += 1
        classMarker = False
        terminated = False

        while not self.eof():
            ch = self.source[self.index]
            self.index += 1
            str += ch
            if ch == '\\':
                ch = self.source[self.index]
                self.index += 1
                # https://tc39.github.io/ecma262/#sec-literals-regular-expression-literals
                if Character.isLineTerminator(ch):
                    self.throwUnexpectedToken(Messages.UnterminatedRegExp)

                str += ch
            elif Character.isLineTerminator(ch):
                self.throwUnexpectedToken(Messages.UnterminatedRegExp)
            elif classMarker:
                if ch == ']':
                    classMarker = False

            else:
                if ch == '/':
                    terminated = True
                    break
                elif ch == '[':
                    classMarker = True

        if not terminated:
            self.throwUnexpectedToken(Messages.UnterminatedRegExp)

        # Exclude leading and trailing slash.
        return str[1:-1]

    def scanRegExpFlags(self):
        str = ''
        flags = ''
        while not self.eof():
            ch = self.source[self.index]
            if not Character.isIdentifierPart(ch):
                break

            self.index += 1
            if ch == '\\' and not self.eof():
                ch = self.source[self.index]
                if ch == 'u':
                    self.index += 1
                    restore = self.index
                    char = self.scanHexEscape('u')
                    if char:
                        flags += char
                        str += '\\u'
                        while restore < self.index:
                            str += self.source[restore]
                            restore += 1

                    else:
                        self.index = restore
                        flags += 'u'
                        str += '\\u'

                    self.tolerateUnexpectedToken()
                else:
                    str += '\\'
                    self.tolerateUnexpectedToken()

            else:
                flags += ch
                str += ch

        return flags

    def scanRegExp(self):
        start = self.index

        pattern = self.scanRegExpBody()
        flags = self.scanRegExpFlags()
        value = self.testRegExp(pattern, flags)

        return RawToken(
            type=Token.RegularExpression,
            value='',
            pattern=pattern,
            flags=flags,
            regex=value,
            lineNumber=self.lineNumber,
            lineStart=self.lineStart,
            start=start,
            end=self.index
        )

    def lex(self):
        if self.eof():
            return RawToken(
                type=Token.EOF,
                value='',
                lineNumber=self.lineNumber,
                lineStart=self.lineStart,
                start=self.index,
                end=self.index
            )

        ch = self.source[self.index]

        if ch == '#':
            self.requireFeature(2022, 'Private identifiers')
            start = self.index
            self.index += 1
            if not Character.isIdentifierStart(self.source[self.index]):
                self.throwUnexpectedToken()
            value = self.getComplexIdentifier()
            token = RawToken(type=Token.Identifier, value='#' + value, private=True,
                             escaped='\\' in self.source[start:self.index],
                             start=start, end=self.index, lineNumber=self.lineNumber, lineStart=self.lineStart)
            return token

        if Character.isIdentifierStart(ch):
            return self.scanIdentifier()

        # Very common: ( and ) and ;
        if ch in ('(', ')', ';'):
            return self.scanPunctuator()

        # String literal starts with single quote (U+0027) or double quote (U+0022).
        if ch in ('\'', '"'):
            return self.scanStringLiteral()

        # Dot (.) U+002E can also start a floating-point number, hence the need
        # to check the next character.
        if ch == '.':
            if Character.isDecimalDigit(self.source[self.index + 1]):
                return self.scanNumericLiteral()

            return self.scanPunctuator()

        if Character.isDecimalDigit(ch):
            return self.scanNumericLiteral()

        # Template literals start with ` (U+0060) for template head
        # or } (U+007D) for template middle or template tail.
        if ch == '`' or (ch == '}' and self.curlyStack and self.curlyStack[-1] == '${'):
            return self.scanTemplate()

        # Possible identifier start in a surrogate pair.
        cp = ord(ch)
        if cp >= 0xD800 and cp < 0xDFFF:
            cp = self.codePointAt(self.index)
            ch = Character.fromCodePoint(cp)
            if Character.isIdentifierStart(ch):
                return self.scanIdentifier()

        return self.scanPunctuator()
