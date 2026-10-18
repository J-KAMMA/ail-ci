# -*- coding: utf-8 -*-
# prelude_ordereddict.py -- `collections.OrderedDict` as a class (ntlib.py injects it for the uses the typed collections
# pass does not build: an OrderedDict held in a class field, an argument of a method, or at module level).

_ail_od_unset = []


class OrderedDict:
    def __init__(self, data=None):
        self.d = {}
        if data is not None:
            self.update(data)

    def update(self, other):
        if isinstance(other, OrderedDict):
            for k in other.d:
                self.d[k] = other.d[k]
        elif isinstance(other, dict):
            for k in other:
                self.d[k] = other[k]
        else:
            for pair in other:
                self.d[pair[0]] = pair[1]

    def __getitem__(self, key):
        return self.d[key]

    def __setitem__(self, key, value):
        self.d[key] = value

    def __delitem__(self, key):
        del self.d[key]

    def __contains__(self, key) -> bool:
        return key in self.d

    def __len__(self) -> int:
        return len(self.d)

    def __iter__(self):
        return list(self.d)

    def __bool__(self) -> bool:
        return len(self.d) > 0

    def keys(self) -> list:
        return list(self.d)

    def values(self) -> list:
        return list(self.d.values())

    def items(self) -> list:
        return list(self.d.items())

    def get(self, key, default=None):
        if key in self.d:
            return self.d[key]
        return default

    def pop(self, key, default=_ail_od_unset):
        if key in self.d:
            return self.d.pop(key)
        if default is _ail_od_unset:
            raise KeyError(key)
        return default

    def setdefault(self, key, default=None):
        if key not in self.d:
            self.d[key] = default
        return self.d[key]

    def clear(self):
        self.d.clear()

    def copy(self):
        out = OrderedDict()
        for k in self.d:
            out.d[k] = self.d[k]
        return out

    def move_to_end(self, key, last=True):
        v = self.d.pop(key)
        if last:
            self.d[key] = v
        else:
            rest = list(self.d.items())
            self.d.clear()
            self.d[key] = v
            for pair in rest:
                self.d[pair[0]] = pair[1]

    def popitem(self, last=True):
        if len(self.d) == 0:
            raise KeyError("dictionary is empty")
        if last:
            return self.d.popitem()
        first = list(self.d)[0]
        v = self.d.pop(first)
        return (first, v)

    def __eq__(self, other):
        if isinstance(other, OrderedDict):
            return list(self.d.items()) == list(other.d.items())
        if isinstance(other, dict):
            return self.d == other
        return False

    def __repr__(self) -> str:
        if len(self.d) == 0:
            return "OrderedDict()"
        return "OrderedDict(" + repr(self.d) + ")"
