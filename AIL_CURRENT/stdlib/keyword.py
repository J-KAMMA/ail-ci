"""Keywords (from CPython 3.12's Lib/keyword.py).

Derived from CPython 3.12 Lib/keyword.py; PSF License, see stdlib/LICENSE-PSF.txt.

AIL finds this file when a program says `import keyword` (`ail_modules.py` searches the bundled
`stdlib/` last).  `kwlist`, `softkwlist`, `__all__` and the two predicates' names and results are
CPython 3.12's.

CPython writes `iskeyword = frozenset(kwlist).__contains__`.  The typed path has no value for a
bound method of a builtin, so `@lru_cache` marks the two predicates: a call spelled
`keyword.iskeyword(s)` is still built (and typed), while taking either one as a first-class value
(`f = keyword.iskeyword`) is a named typed-path refusal and the program is built on the general
path, where the value is a real callable and prints `True`/`False` as CPython does.  A bare `def`
would instead be a typed function value whose `bool` result becomes a plain `1`/`0` when printed
through the saved reference -- a silent mismatch this form avoids.
"""
from functools import lru_cache

__all__ = ["iskeyword", "issoftkeyword", "kwlist", "softkwlist"]

kwlist = [
    'False',
    'None',
    'True',
    'and',
    'as',
    'assert',
    'async',
    'await',
    'break',
    'class',
    'continue',
    'def',
    'del',
    'elif',
    'else',
    'except',
    'finally',
    'for',
    'from',
    'global',
    'if',
    'import',
    'in',
    'is',
    'lambda',
    'nonlocal',
    'not',
    'or',
    'pass',
    'raise',
    'return',
    'try',
    'while',
    'with',
    'yield'
]

softkwlist = [
    '_',
    'case',
    'match',
    'type'
]


@lru_cache
def iskeyword(s: str) -> bool:
    return s in {'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await', 'break', 'class',
                 'continue', 'def', 'del', 'elif', 'else', 'except', 'finally', 'for', 'from',
                 'global', 'if', 'import', 'in', 'is', 'lambda', 'nonlocal', 'not', 'or', 'pass',
                 'raise', 'return', 'try', 'while', 'with', 'yield'}


@lru_cache
def issoftkeyword(s: str) -> bool:
    return s in {'_', 'case', 'match', 'type'}
