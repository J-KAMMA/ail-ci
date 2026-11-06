# SPDX-License-Identifier: MIT
"""Type aliases from CPython's tomllib, kept for readers of the source.

Derived from CPython 3.12 Lib/tomllib/_types.py; MIT License (upstream tomli); PSF License text, see stdlib/LICENSE-PSF.txt.

CPython declares

    ParseFloat = Callable[[str], Any]
    Key = tuple[str, ...]
    Pos = int

The AIL compiler cannot hold a variable-length tuple in a module-level name
(it asks for a fixed `tuple[...]` or a list) and every function in this
package is unannotated, so only the documentation value remains:

* `ParseFloat` -- a callable that turns a float string into a number.
* `Key` -- a path of key parts; a `list[str]` in this port.
* `Pos` -- an index into the document; an `int`.
"""
