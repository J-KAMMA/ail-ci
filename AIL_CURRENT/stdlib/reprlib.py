"""AIL bundled standard-library `reprlib` (CPython 3.12's Lib/reprlib.py).

`Repr` keeps the limits (`maxlevel`, `maxtuple`, `maxlist`, `maxarray`, `maxdict`, `maxset`,
`maxfrozenset`, `maxdeque`, `maxstring`, `maxlong`, `maxother`, `fillvalue`, `indent`), the
`repr_*` methods, `_possibly_sorted`, `aRepr`, `repr` and `recursive_repr`.  `recursive_repr`
tests object identity (`any(k is self for k in running)`) where CPython keys on
`(id(self), get_ident())`: the bundled module is one executable, so neither
`_thread.get_ident()` nor the builtin `id` is available, but `is` is, and a list of the objects
currently being repr'd is exactly what `id()` would compare.

`repr1` dispatches the built-in types through an explicit chain on `type(x).__name__`, then tries
`getattr(self, 'repr_' + typename)` so a subclass may add `repr_<Type>` exactly as CPython
documents, and falls back to `repr_instance` when there is no such method.  The dynamic
`getattr` for a name a *subclass* defines is still refused by the current compiler (a method is
not an instance attribute; see lab/stdlib/reprlib/RESULTS.md), so such a subclass only gets the
`getattr` route when its `repr_<Type>` is stored as a class attribute; the built-in chain and
`repr_instance` are unaffected.
"""

__all__ = ["Repr", "repr", "recursive_repr"]

from itertools import islice


def _repr_of(x):
    return '%r' % (x,)


def recursive_repr(fillvalue='...'):
    def decorating_function(user_function):
        running = []

        def wrapper(self):
            for seen in running:
                if seen is self:
                    return fillvalue
            running.append(self)
            try:
                result = user_function(self)
            finally:
                running.pop()
            return result

        return wrapper

    return decorating_function


class Repr:

    def __init__(self, *, maxlevel=6, maxtuple=6, maxlist=6, maxarray=5, maxdict=4,
                 maxset=6, maxfrozenset=6, maxdeque=6, maxstring=30, maxlong=40,
                 maxother=30, fillvalue='...', indent=None):
        self.maxlevel = maxlevel
        self.maxtuple = maxtuple
        self.maxlist = maxlist
        self.maxarray = maxarray
        self.maxdict = maxdict
        self.maxset = maxset
        self.maxfrozenset = maxfrozenset
        self.maxdeque = maxdeque
        self.maxstring = maxstring
        self.maxlong = maxlong
        self.maxother = maxother
        self.fillvalue = fillvalue
        self.indent = indent

    def repr(self, x):
        return self.repr1(x, self.maxlevel)

    def repr1(self, x, level):
        typename = type(x).__name__
        if typename == 'list':
            return self.repr_list(x, level)
        if typename == 'tuple':
            return self.repr_tuple(x, level)
        if typename == 'dict':
            return self.repr_dict(x, level)
        if typename == 'set':
            return self.repr_set(x, level)
        if typename == 'frozenset':
            return self.repr_frozenset(x, level)
        if typename == 'str':
            return self.repr_str(x, level)
        if typename == 'int':
            return self.repr_int(x, level)
        if typename == 'deque':
            return self.repr_deque(x, level)
        if typename == 'array':
            return self.repr_array(x, level)
        try:
            method = getattr(self, 'repr_' + typename)
        except AttributeError:
            return self.repr_instance(x, level)
        return method(x, level)

    def _join(self, pieces, level):
        if self.indent is None:
            return ', '.join(pieces)
        if not pieces:
            return ''
        indent = self.indent
        if isinstance(indent, int):
            if indent < 0:
                raise ValueError('Repr.indent cannot be negative int (was %r)' % (indent,))
            indent = indent * ' '
        try:
            sep = ',\n' + (self.maxlevel - level + 1) * indent
        except TypeError:
            raise TypeError('Repr.indent must be a str, int or None')
        joined = sep.join(('',) + tuple(pieces) + ('',))
        return joined[1:-len(indent) or None]

    def _repr_iterable(self, x, level, left, right, maxiter, trail=''):
        n = len(x)
        if level <= 0 and n:
            s = self.fillvalue
        else:
            newlevel = level - 1
            pieces = []
            for elem in islice(x, maxiter):
                pieces.append(self.repr1(elem, newlevel))
            if n > maxiter:
                pieces.append(self.fillvalue)
            s = self._join(pieces, level)
            if n == 1 and trail and self.indent is None:
                right = trail + right
        return '%s%s%s' % (left, s, right)

    def repr_tuple(self, x, level):
        return self._repr_iterable(x, level, '(', ')', self.maxtuple, ',')

    def repr_list(self, x, level):
        return self._repr_iterable(x, level, '[', ']', self.maxlist)

    def repr_array(self, x, level):
        if not x:
            return "array('%s')" % x.typecode
        header = "array('%s', [" % x.typecode
        return self._repr_iterable(x, level, header, '])', self.maxarray)

    def repr_set(self, x, level):
        if not x:
            return 'set()'
        x = _possibly_sorted(x)
        return self._repr_iterable(x, level, '{', '}', self.maxset)

    def repr_frozenset(self, x, level):
        if not x:
            return 'frozenset()'
        x = _possibly_sorted(x)
        return self._repr_iterable(x, level, 'frozenset({', '})', self.maxfrozenset)

    def repr_deque(self, x, level):
        return self._repr_iterable(x, level, 'deque([', '])', self.maxdeque)

    def repr_dict(self, x, level):
        n = len(x)
        if n == 0:
            return '{}'
        if level <= 0:
            return '{' + self.fillvalue + '}'
        newlevel = level - 1
        pieces = []
        for key in islice(_possibly_sorted(x), self.maxdict):
            keyrepr = self.repr1(key, newlevel)
            valrepr = self.repr1(x[key], newlevel)
            pieces.append('%s: %s' % (keyrepr, valrepr))
        if n > self.maxdict:
            pieces.append(self.fillvalue)
        s = self._join(pieces, level)
        return '{%s}' % (s,)

    def repr_str(self, x, level):
        s = _repr_of(x[:self.maxstring])
        if len(s) > self.maxstring:
            i = max(0, (self.maxstring - 3) // 2)
            j = max(0, self.maxstring - 3 - i)
            s = _repr_of(x[:i] + x[len(x) - j:])
            s = s[:i] + self.fillvalue + s[len(s) - j:]
        return s

    def repr_int(self, x, level):
        s = _repr_of(x)
        if len(s) > self.maxlong:
            i = max(0, (self.maxlong - 3) // 2)
            j = max(0, self.maxlong - 3 - i)
            s = s[:i] + self.fillvalue + s[len(s) - j:]
        return s

    def repr_instance(self, x, level):
        try:
            s = _repr_of(x)
        except Exception:
            return '<%s instance>' % (type(x).__name__,)
        if len(s) > self.maxother:
            i = max(0, (self.maxother - 3) // 2)
            j = max(0, self.maxother - 3 - i)
            s = s[:i] + self.fillvalue + s[len(s) - j:]
        return s


def _possibly_sorted(x):
    try:
        return sorted(x)
    except Exception:
        return list(x)


aRepr = Repr()


def repr(x):
    return aRepr.repr(x)
