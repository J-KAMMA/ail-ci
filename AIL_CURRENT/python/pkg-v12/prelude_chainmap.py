# -*- coding: utf-8 -*-
# prelude_chainmap.py -- `collections.ChainMap` as Python source (ntlib.py injects it).


_ail_cm_unset = []


class ChainMap:
    def __init__(self, *maps):
        self.maps = list(maps)
        if len(self.maps) == 0:
            self.maps = [{}]

    def __getitem__(self, key):
        for m in self.maps:
            if key in m:
                return m[key]
        raise KeyError(key)

    def get(self, key, default=None):
        for m in self.maps:
            if key in m:
                return m[key]
        return default

    def __contains__(self, key) -> bool:
        for m in self.maps:
            if key in m:
                return True
        return False

    def __setitem__(self, key, value):
        self.maps[0][key] = value

    def __delitem__(self, key):
        if key in self.maps[0]:
            del self.maps[0][key]
        else:
            raise KeyError("Key not found in the first mapping: " + repr(key))

    def _ail_keys(self) -> list:
        d = {}
        i = len(self.maps) - 1
        while i >= 0:
            for k in self.maps[i]:
                d[k] = 0
            i = i - 1
        return list(d)

    def __iter__(self):
        return self._ail_keys()

    def __len__(self) -> int:
        return len(self._ail_keys())

    def __bool__(self) -> bool:
        for m in self.maps:
            if len(m) > 0:
                return True
        return False

    def keys(self) -> list:
        return self._ail_keys()

    def values(self) -> list:
        out = []
        for k in self._ail_keys():
            out.append(self[k])
        return out

    def items(self) -> list:
        out = []
        for k in self._ail_keys():
            out.append((k, self[k]))
        return out

    def setdefault(self, key, default=None):
        if key not in self:
            self.maps[0][key] = default
        return self[key]

    def update(self, other):
        self.maps[0].update(other)

    def pop(self, key, default=_ail_cm_unset):
        if key in self.maps[0]:
            return self.maps[0].pop(key)
        if default is _ail_cm_unset:
            raise KeyError("Key not found in the first mapping: " + repr(key))
        return default

    def clear(self):
        self.maps[0].clear()

    def new_child(self, m=None):
        out = ChainMap({})
        out.maps = list(self.maps)
        if m is None:
            out.maps.insert(0, {})
        else:
            out.maps.insert(0, m)
        return out

    def _ail_parents(self):
        out = ChainMap({})
        out.maps = self.maps[1:]
        if len(out.maps) == 0:
            out.maps = [{}]
        return out

    def copy(self):
        out = ChainMap({})
        out.maps = [dict(self.maps[0])] + self.maps[1:]
        return out

    def __repr__(self) -> str:
        parts = []
        for m in self.maps:
            parts.append(repr(m))
        return "ChainMap(" + ", ".join(parts) + ")"
