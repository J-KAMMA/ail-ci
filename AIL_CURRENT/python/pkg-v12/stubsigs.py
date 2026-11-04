"""Lookup API for the vendored typeshed signature table (`stubsigs_table.SIGS`).

`lookup(qualname)` returns `(ret, params, flags)` or `None`:

* `ret` is one of `int float bool str bytes None obj`;
* `params` is a tuple of `(name, kind, annotation_text)` with `kind` in `pos kw star dstar`;
* `flags` is `""` or `"overload"` (the overloads did not agree on a return type).

A stub `int` means AIL's checked int64 (the int64 default), not CPython's unbounded int. `float`, `bool`,
`str` and `bytes` are AIL's ordinary float/bool/string/bytes values; `obj` means "not one of the scalar
returns" (a TypeVar, a generic, an alias, `Any`, a `Literal`, a union, a class, ...).

The table module is imported on the first `lookup` call only, so a compiler that never asks for a signature
does not pay for the import.
"""

_SIGS = None


def lookup(qualname):
    global _SIGS
    if _SIGS is None:
        from stubsigs_table import SIGS
        _SIGS = SIGS
    return _SIGS.get(qualname)
