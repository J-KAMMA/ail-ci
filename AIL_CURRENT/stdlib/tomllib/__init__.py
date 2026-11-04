# SPDX-License-Identifier: MIT
"""TOML 1.0 parser, a port of CPython 3.12's ``tomllib`` to the AIL subset.

The package keeps CPython's public surface (``loads``, ``load`` and
``TOMLDecodeError``), its results and its error messages, including the
``(at line L, column C)`` / ``(at end of document)`` suffix.  AIL refuses
several constructs that CPython's original source uses, so the parser was
rewritten around them.  Each rewrite and the refusal it answers:

1. ``re.compile`` patterns stored in module-level names and matched with a
   ``pos`` argument.  Refusal: ``not in the subset: name
   'tomllib._re.RE_DATETIME' is not defined`` (the compiler only builds a
   literal pattern used through ``.match(...)`` directly and does not build
   ``pos`` / ``endpos``).  Rewrite: ``_re.py`` holds character classes and
   ``_parser.py`` scans dates, times and numbers by hand.

2. ``from typing import Any, BinaryIO, NamedTuple`` and the ``Output``
   ``NamedTuple``.  Refusal: ``not in the subset: a class field of a
   NamedTuple is not built`` style errors around tuple elements.  Rewrite:
   the output dict and the flags are plain locals of ``loads``; no
   NamedTuple, no ``typing`` import.

3. Variable-length tuples: ``Key = tuple[str, ...]``, ``header + key``,
   ``key[:-1]`` and every ``return pos, value`` pair.  Refusal: ``not in
   the subset: a variable-length tuple (tuple[int, ...]); a fixed
   tuple[int, int] or a list is built``.  Rewrite: a key path is a
   ``list[str]``, and parsers return ``[pos, value]`` lists.

4. A module-level constant holding a tuple of unknown element type.
   Refusal: ``not in the subset: a module-level constant whose type cannot
   be told and that holds a tuple is not built; build it inside a
   function``.  Rewrite: every table of constants became either a plain
   string (``_re.py``) or an ``if``/``elif`` chain.

5. ``None`` stored in a container (``header: Key = ()`` was fine, but
   ``None`` in flag dicts and the ``parse_float=None`` comparisons were
   not).  Refusal: ``not in the subset: None stored in a list / tuple /
   dict / set, or passed to a method, cannot be followed by the Optional
   rewrite; use a sentinel value there``.  Rewrite: no ``None`` is ever
   stored in a container and ``loads``'s ``parse_float`` default is the
   integer sentinel ``0`` (``0`` means the built-in ``float``).

6. Required keyword-only parameters.  Refusal: ``not in the subset: a
   required keyword-only parameter recursive in def set (this cut requires
   every keyword-only parameter to have a default)``.  Rewrite: ``loads``
   and ``load`` take ``parse_float`` positionally with the ``0`` default,
   and the ``recursive`` / ``access_lists`` / ``multiline`` flags are plain
   positional parameters.

7. ``datetime.time`` and ``datetime.timezone(...)`` used as values in
   annotations.  ``datetime.time`` is refused by the compiler (``not in the
   subset: datetime.time is not built on the general path``), so a local
   time value is returned as its source text; every other date/time type
   is built normally.

8. ``frozenset`` / ``set`` / ``MappingProxyType`` constants and
   ``str.count(..., start, end)`` / ``str.rindex(..., start, end)``.
   Rewrite: plain strings tested with ``in``, manual coordinate counting,
   and an ``if`` chain for the escape table.
"""

__all__ = ("loads", "load", "TOMLDecodeError")

from ._parser import TOMLDecodeError, load, loads
