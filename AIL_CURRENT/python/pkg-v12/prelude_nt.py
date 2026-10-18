# -*- coding: utf-8 -*-
# prelude_nt.py -- the base class of the classes ntlib.py builds for `namedtuple` / `NamedTuple`, as Python source.
#
# A named tuple is an instance whose class derives from _AilNT and defines `_ail_vals(self)` (the fields in order),
# `__init__`, `__repr__`, `_asdict` and `_replace`. The base gives it the tuple behaviour: len, indexing, iteration (so
# unpacking and for loops), equality with other named tuples and with tuples, ordering, hashing, `in`, count, index.


class _AilNT:
    def _ail_vals(self) -> list:
        return []

    def _ail_names(self) -> list:
        return []

    def _ail_typename(self) -> str:
        return "tuple"

    def _ail_from(self, vals: list):
        return self

    def __repr__(self) -> str:
        names = self._ail_names()
        vals = self._ail_vals()
        parts = []
        i = 0
        while i < len(names):
            parts.append(names[i] + "=" + repr(vals[i]))
            i = i + 1
        return self._ail_typename() + "(" + ", ".join(parts) + ")"

    def _asdict(self) -> dict:
        names = self._ail_names()
        vals = self._ail_vals()
        d = {}
        i = 0
        while i < len(names):
            d[names[i]] = vals[i]
            i = i + 1
        return d

    def _replace(self, **kw):
        names = self._ail_names()
        vals = self._ail_vals()
        bad = []
        for k in kw:
            if k not in names:
                bad.append(k)
        if len(bad) > 0:
            raise ValueError("Got unexpected field names: " + repr(bad))
        out = []
        i = 0
        while i < len(names):
            if names[i] in kw:
                out.append(kw[names[i]])
            else:
                out.append(vals[i])
            i = i + 1
        return self._ail_from(out)

    def __len__(self) -> int:
        return len(self._ail_vals())

    def __getitem__(self, i):
        v = self._ail_vals()
        if i < -len(v) or i >= len(v):
            raise IndexError("tuple index out of range")
        return v[i]

    def __iter__(self):
        return self._ail_vals()

    def __contains__(self, x) -> bool:
        return x in self._ail_vals()

    def __eq__(self, other):
        if isinstance(other, _AilNT):
            return self._ail_vals() == other._ail_vals()
        if isinstance(other, tuple):
            return self._ail_vals() == list(other)
        return False

    def __lt__(self, other):
        if isinstance(other, _AilNT):
            return self._ail_vals() < other._ail_vals()
        return self._ail_vals() < list(other)

    def __gt__(self, other):
        if isinstance(other, _AilNT):
            return self._ail_vals() > other._ail_vals()
        return self._ail_vals() > list(other)

    def __hash__(self):
        return hash(tuple(self._ail_vals()))

    def count(self, x) -> int:
        n = 0
        for v in self._ail_vals():
            if v == x:
                n = n + 1
        return n

    def index(self, x) -> int:
        i = 0
        for v in self._ail_vals():
            if v == x:
                return i
            i = i + 1
        raise ValueError("tuple.index(x): x not in tuple")

