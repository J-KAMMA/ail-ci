# -*- coding: utf-8 -*-
"""intmode.py -- which int semantics a Python-syntax program gets (owner decision 2026-10-31).

Default: ints are 64-bit. An operation that leaves int64 stops the program with an OverflowError-style message that names the
operation (never a silent wrap, never a different number), and a program whose source needs a big int statically (an int
literal outside int64, a constant expression like `1 << 200`) is refused at compile time. No program goes to the (about 20x
slower) general path for an int-width reason.

Opt-in: `compile --exact-int` or the environment variable AIL_EXACT_INT=1 keeps CPython's arbitrary precision ints (the exact
big-int machinery of docs/design/BIGINT.md: bigcap marks, tagged ints on the typed path, the exact general path).

Only a program written as Python (AIL_SURFACE=python) ever had exact ints; the AIL brace syntax has always been int64.
"""
import os

_TRUE = ('1', 'on', 'yes', 'true')


def exact():
    """Was the exact (arbitrary precision) int mode asked for?"""
    return os.environ.get('AIL_EXACT_INT', '').strip().lower() in _TRUE


def exact_python():
    """The program is written as Python AND the exact int mode is on: the condition that used to be `AIL_SURFACE == 'python'`
    wherever it meant "ints are Python's"."""
    return os.environ.get('AIL_SURFACE') == 'python' and exact()


def int64_python():
    """The program is written as Python and its ints are int64 (the default)."""
    return os.environ.get('AIL_SURFACE') == 'python' and not exact()


HINT = 'compile with --exact-int (or AIL_EXACT_INT=1) for exact big ints, about 20x slower'