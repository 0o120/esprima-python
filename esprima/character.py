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

from bisect import bisect_right
from ._unicode_data import ID_START, ID_CONTINUE, UNICODE_VERSION
from .compat import uchr

ASCII_IDENTIFIER_START = frozenset('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ$_\\')
ASCII_IDENTIFIER_PART = ASCII_IDENTIFIER_START | frozenset('0123456789')

WHITE_SPACE = set((
    '\x09', '\x0B', '\x0C', '\x20', '\xA0',
    '\u1680', '\u2000', '\u2001', '\u2002',
    '\u2003', '\u2004', '\u2005', '\u2006', '\u2007',
    '\u2008', '\u2009', '\u200A', '\u202F', '\u205F',
    '\u3000', '\uFEFF',
))
LINE_TERMINATOR = set(('\x0A', '\x0D', '\u2028', '\u2029'))

DECIMAL_CONV = dict((c, n) for n, c in enumerate('0123456789'))
OCTAL_CONV = dict((c, n) for n, c in enumerate('01234567'))
HEX_CONV = dict((c, n) for n, c in enumerate('0123456789abcdef'))
for n, c in enumerate('ABCDEF', 10):
    HEX_CONV[c] = n
DECIMAL_DIGIT = set(DECIMAL_CONV.keys())
OCTAL_DIGIT = set(OCTAL_CONV.keys())
HEX_DIGIT = set(HEX_CONV.keys())

class Character:
    @staticmethod
    def fromCodePoint(code):
        return uchr(code)

    # https://tc39.github.io/ecma262/#sec-white-space

    @staticmethod
    def isWhiteSpace(ch):
        return ch in WHITE_SPACE

    # https://tc39.github.io/ecma262/#sec-line-terminators

    @staticmethod
    def isLineTerminator(ch):
        return ch in LINE_TERMINATOR

    # https://tc39.github.io/ecma262/#sec-names-and-keywords

    @staticmethod
    def isIdentifierStart(ch):
        if len(ch) != 1:
            return False
        if ch < '\x80':
            return ch in ASCII_IDENTIFIER_START
        return bool(bisect_right(ID_START, ord(ch)) % 2)

    @staticmethod
    def isIdentifierPart(ch):
        if len(ch) != 1:
            return False
        if ch < '\x80':
            return ch in ASCII_IDENTIFIER_PART
        return bool(bisect_right(ID_CONTINUE, ord(ch)) % 2)

    # https://tc39.github.io/ecma262/#sec-literals-numeric-literals

    @staticmethod
    def isDecimalDigit(ch):
        return ch in DECIMAL_DIGIT

    @staticmethod
    def isHexDigit(ch):
        return ch in HEX_DIGIT

    @staticmethod
    def isOctalDigit(ch):
        return ch in OCTAL_DIGIT
