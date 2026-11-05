# SPDX-License-Identifier: MIT
"""Character classes used by the TOML parser.
Derived from CPython 3.12 Lib/tomllib/_re.py; PSF License, see stdlib/LICENSE-PSF.txt.

CPython's tomllib recognises dates and numbers with compiled regular
expressions (`RE_DATETIME`, `RE_NUMBER`, `RE_LOCALTIME`).  The AIL compiler
only builds `re.compile` for a literal pattern used through `.match(...)`
in the same expression and refuses a compiled pattern that is stored in a
module-level name and later used as a value, so this port scans the same
grammars by hand.  Keeping the character classes here makes the scanner
read like the regular expressions it replaces.
"""

WS = " \t"
WS_AND_NEWLINE = " \t\n"
DIGITS = "0123456789"
HEXDIGITS = "0123456789abcdefABCDEF"
BARE_KEY_CHARS = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789-_"
)
