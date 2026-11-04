"""Keywords (from CPython 3.12's Lib/keyword.py).

AIL finds this file when a program says `import keyword` (`ail_modules.py` searches the bundled
`stdlib/` last).  Every public name and value is CPython 3.12's.  Two definitions are rewritten as
functions because the compiler refuses CPython's form: `iskeyword` and `issoftkeyword` are
`frozenset(...).__contains__` there, and a bound method built from a class instance is not a value
this compiler models.  `def` over a set is equal for every argument.
"""

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


def iskeyword(s: str) -> bool:
    return s in {'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await', 'break', 'class',
                 'continue', 'def', 'del', 'elif', 'else', 'except', 'finally', 'for', 'from',
                 'global', 'if', 'import', 'in', 'is', 'lambda', 'nonlocal', 'not', 'or', 'pass',
                 'raise', 'return', 'try', 'while', 'with', 'yield'}


def issoftkeyword(s: str) -> bool:
    return s in {'_', 'case', 'match', 'type'}
