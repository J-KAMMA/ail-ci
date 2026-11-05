"""Token constants (CPython 3.12's Lib/token.py as AIL source).
Derived from CPython 3.12 Lib/token.py; PSF License, see stdlib/LICENSE-PSF.txt.

AIL finds this file when a program says `import token` (`ail_modules.py` searches the bundled
`stdlib/` last).  Every constant keeps CPython 3.12's name and value.  Two definitions are
rewritten because the compiler refuses CPython's form: `tok_name` and the list it extends
`__all__` with are written out as one dict literal and one list literal (CPython builds them
from `globals()`, which this compiler does not model).  Regenerate the tables with:

    python3 -c "import token; print(sorted(token.tok_name.items()))"

and copy the pairs below.  `ISTERMINAL`, `ISNONTERMINAL` and `ISEOF` keep CPython's bodies; a
program that calls `ISEOF` reads the module's `ENDMARKER`, so it is built on the general path on
the default build (the typed path reads that bare global as a `str` here), and both builds print
what CPython prints.
"""

__all__ = [
    'tok_name', 'ISTERMINAL', 'ISNONTERMINAL', 'ISEOF', 'ENDMARKER', 'NAME',
    'NUMBER', 'STRING', 'NEWLINE', 'INDENT', 'DEDENT', 'LPAR',
    'RPAR', 'LSQB', 'RSQB', 'COLON', 'COMMA', 'SEMI',
    'PLUS', 'MINUS', 'STAR', 'SLASH', 'VBAR', 'AMPER',
    'LESS', 'GREATER', 'EQUAL', 'DOT', 'PERCENT', 'LBRACE',
    'RBRACE', 'EQEQUAL', 'NOTEQUAL', 'LESSEQUAL', 'GREATEREQUAL', 'TILDE',
    'CIRCUMFLEX', 'LEFTSHIFT', 'RIGHTSHIFT', 'DOUBLESTAR', 'PLUSEQUAL', 'MINEQUAL',
    'STAREQUAL', 'SLASHEQUAL', 'PERCENTEQUAL', 'AMPEREQUAL', 'VBAREQUAL', 'CIRCUMFLEXEQUAL',
    'LEFTSHIFTEQUAL', 'RIGHTSHIFTEQUAL', 'DOUBLESTAREQUAL', 'DOUBLESLASH', 'DOUBLESLASHEQUAL', 'AT',
    'ATEQUAL', 'RARROW', 'ELLIPSIS', 'COLONEQUAL', 'EXCLAMATION', 'OP',
    'AWAIT', 'ASYNC', 'TYPE_IGNORE', 'TYPE_COMMENT', 'SOFT_KEYWORD', 'FSTRING_START',
    'FSTRING_MIDDLE', 'FSTRING_END', 'COMMENT', 'NL', 'ERRORTOKEN', 'ENCODING',
    'N_TOKENS', 'NT_OFFSET',
]

ENDMARKER = 0
NAME = 1
NUMBER = 2
STRING = 3
NEWLINE = 4
INDENT = 5
DEDENT = 6
LPAR = 7
RPAR = 8
LSQB = 9
RSQB = 10
COLON = 11
COMMA = 12
SEMI = 13
PLUS = 14
MINUS = 15
STAR = 16
SLASH = 17
VBAR = 18
AMPER = 19
LESS = 20
GREATER = 21
EQUAL = 22
DOT = 23
PERCENT = 24
LBRACE = 25
RBRACE = 26
EQEQUAL = 27
NOTEQUAL = 28
LESSEQUAL = 29
GREATEREQUAL = 30
TILDE = 31
CIRCUMFLEX = 32
LEFTSHIFT = 33
RIGHTSHIFT = 34
DOUBLESTAR = 35
PLUSEQUAL = 36
MINEQUAL = 37
STAREQUAL = 38
SLASHEQUAL = 39
PERCENTEQUAL = 40
AMPEREQUAL = 41
VBAREQUAL = 42
CIRCUMFLEXEQUAL = 43
LEFTSHIFTEQUAL = 44
RIGHTSHIFTEQUAL = 45
DOUBLESTAREQUAL = 46
DOUBLESLASH = 47
DOUBLESLASHEQUAL = 48
AT = 49
ATEQUAL = 50
RARROW = 51
ELLIPSIS = 52
COLONEQUAL = 53
EXCLAMATION = 54
OP = 55
AWAIT = 56
ASYNC = 57
TYPE_IGNORE = 58
TYPE_COMMENT = 59
SOFT_KEYWORD = 60
FSTRING_START = 61
FSTRING_MIDDLE = 62
FSTRING_END = 63
COMMENT = 64
NL = 65

# These aren't used by the C tokenizer but are needed for tokenize.py
ERRORTOKEN = 66
ENCODING = 67
N_TOKENS = 68
# Special definitions for cooperation with parser
NT_OFFSET = 256

tok_name = {
    0: 'ENDMARKER',
    1: 'NAME',
    2: 'NUMBER',
    3: 'STRING',
    4: 'NEWLINE',
    5: 'INDENT',
    6: 'DEDENT',
    7: 'LPAR',
    8: 'RPAR',
    9: 'LSQB',
    10: 'RSQB',
    11: 'COLON',
    12: 'COMMA',
    13: 'SEMI',
    14: 'PLUS',
    15: 'MINUS',
    16: 'STAR',
    17: 'SLASH',
    18: 'VBAR',
    19: 'AMPER',
    20: 'LESS',
    21: 'GREATER',
    22: 'EQUAL',
    23: 'DOT',
    24: 'PERCENT',
    25: 'LBRACE',
    26: 'RBRACE',
    27: 'EQEQUAL',
    28: 'NOTEQUAL',
    29: 'LESSEQUAL',
    30: 'GREATEREQUAL',
    31: 'TILDE',
    32: 'CIRCUMFLEX',
    33: 'LEFTSHIFT',
    34: 'RIGHTSHIFT',
    35: 'DOUBLESTAR',
    36: 'PLUSEQUAL',
    37: 'MINEQUAL',
    38: 'STAREQUAL',
    39: 'SLASHEQUAL',
    40: 'PERCENTEQUAL',
    41: 'AMPEREQUAL',
    42: 'VBAREQUAL',
    43: 'CIRCUMFLEXEQUAL',
    44: 'LEFTSHIFTEQUAL',
    45: 'RIGHTSHIFTEQUAL',
    46: 'DOUBLESTAREQUAL',
    47: 'DOUBLESLASH',
    48: 'DOUBLESLASHEQUAL',
    49: 'AT',
    50: 'ATEQUAL',
    51: 'RARROW',
    52: 'ELLIPSIS',
    53: 'COLONEQUAL',
    54: 'EXCLAMATION',
    55: 'OP',
    56: 'AWAIT',
    57: 'ASYNC',
    58: 'TYPE_IGNORE',
    59: 'TYPE_COMMENT',
    60: 'SOFT_KEYWORD',
    61: 'FSTRING_START',
    62: 'FSTRING_MIDDLE',
    63: 'FSTRING_END',
    64: 'COMMENT',
    65: 'NL',
    66: 'ERRORTOKEN',
    67: 'ENCODING',
    68: 'N_TOKENS',
    256: 'NT_OFFSET',
}

EXACT_TOKEN_TYPES = {
    '!': 54,
    '!=': 28,
    '%': 24,
    '%=': 40,
    '&': 19,
    '&=': 41,
    '(': 7,
    ')': 8,
    '*': 16,
    '**': 35,
    '**=': 46,
    '*=': 38,
    '+': 14,
    '+=': 36,
    ',': 12,
    '-': 15,
    '-=': 37,
    '->': 51,
    '.': 23,
    '...': 52,
    '/': 17,
    '//': 47,
    '//=': 48,
    '/=': 39,
    ':': 11,
    ':=': 53,
    ';': 13,
    '<': 20,
    '<<': 33,
    '<<=': 44,
    '<=': 29,
    '=': 22,
    '==': 27,
    '>': 21,
    '>=': 30,
    '>>': 34,
    '>>=': 45,
    '@': 49,
    '@=': 50,
    '[': 9,
    ']': 10,
    '^': 32,
    '^=': 43,
    '{': 25,
    '|': 18,
    '|=': 42,
    '}': 26,
    '~': 31,
}


def ISTERMINAL(x: int) -> bool:
    return x < NT_OFFSET


def ISNONTERMINAL(x: int) -> bool:
    return x >= NT_OFFSET


def ISEOF(x: int) -> bool:
    return x == ENDMARKER
