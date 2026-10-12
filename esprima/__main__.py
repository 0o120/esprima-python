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

from __future__ import absolute_import, unicode_literals, print_function, division

import sys

from .esprima import parse, tokenize, Error, toDict
from . import version


def main(argv=None):
    import argparse
    import json
    import time

    parser = argparse.ArgumentParser(description="Parse or tokenize JavaScript")
    parser.add_argument("file", nargs="?", help="UTF-8 source file; stdin if omitted")
    parser.add_argument("--version", action="version", version=version)
    for name in ("comment", "attachComment", "loc", "range", "raw", "tokens", "tolerant", "tokenize", "jsx"):
        parser.add_argument("--" + name, action="store_true")
    parser.add_argument("--module", action="store_true", help="Parse an ECMAScript module")
    parser.add_argument("--ecma-version", type=int, default=2026)
    parser.add_argument("--timing", action="store_true", help="Write timing information to stderr")
    opts = parser.parse_args(argv)
    try:
        if opts.file:
            with open(opts.file, encoding="utf-8") as source:
                code = source.read()
        elif sys.stdin.isatty():
            parser.print_help()
            return 64
        else:
            code = sys.stdin.read()
    except (OSError, UnicodeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    options = vars(opts).copy()
    for key in ("file", "module", "ecma_version", "timing", "tokenize"):
        options.pop(key)
    options["sourceType"] = "module" if opts.module else "script"
    options["ecmaVersion"] = opts.ecma_version
    started = time.perf_counter()
    try:
        result = tokenize(code, options) if opts.tokenize else parse(code, options)
        print(json.dumps(toDict(result), ensure_ascii=True, indent=2, allow_nan=False))
    except Error as error:
        print(json.dumps(error.toDict(), ensure_ascii=True), file=sys.stderr)
        return 1
    except (TypeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    if opts.timing:
        print("Parsed in %.6f seconds" % (time.perf_counter() - started), file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
