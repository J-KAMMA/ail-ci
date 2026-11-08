"""Derived from CPython 3.12 Lib/copy.py; PSF License, see stdlib/LICENSE-PSF.txt.

Generic (shallow and deep) copying operations.

AIL source rewrite of CPython 3.12's copy.py.  The dispatch tables and the
`type(x)` lookups are replaced by isinstance() chains because this compiler
cannot use a type object as a plain value or as a dict key.  The copy/deepcopy
messages, the memo protocol and the sharing rules are CPython's for the types
this compiler builds: None, bool, int, float, str, bytes, bytearray, list,
tuple (of any length), dict, set and frozenset.  This compiler has no `id`, so
each memoised object gets a process-unique integer token inside the caller's
memo dict (with one keep-alive entry), not CPython's `id(x)` key.  The dict is
used in place: clearing or reusing it cannot return a stale copy, and existing
keys are never overwritten.

A class instance cannot be rebuilt here: the compiler has no `object.__new__`,
no `cls.__new__` and no `type(x)` as a value, so a copy would not have the
class of the original.  Such a value (and the `__copy__`/`__deepcopy__` hooks,
which need the same dunder dispatch) is refused by name, naming its type,
instead of returning a look-alike of another class.
"""

class Error(Exception):
    pass


error = Error

__all__ = ["Error", "copy", "deepcopy"]


def _is_atomic(x):
    if x is None or x is True or x is False:
        return True
    if isinstance(x, int) or isinstance(x, float):
        return True
    if isinstance(x, str) or isinstance(x, bytes) or isinstance(x, frozenset):
        return True
    if isinstance(x, range):
        return True
    return False


def _same(a, b):
    if isinstance(a, int) and isinstance(b, int):
        return a == b
    return a is b


def _copy_list(x):
    y = []
    for item in x:
        y.append(item)
    return y


def _copy_dict(x):
    y = {}
    for key in x:
        y[key] = x[key]
    return y


def _copy_set(x):
    return x.copy()


def _copy_bytearray(x):
    return bytearray(x)


class _MemoMark:
    def __init__(self) -> None:
        self.tag = 0


_MEMO_STATE = _MemoMark()
_next_token = [0]


def _new_token(d):
    token = _next_token[0]
    while token in d:
        token = token - 1
    _next_token[0] = token - 1
    return token


class _Memo:
    def __init__(self, d):
        self.d = d

    def get(self, obj):
        state = []
        found = False
        for key in self.d:
            value = self.d[key]
            if isinstance(value, list) and len(value) > 0 and value[0] is _MEMO_STATE:
                state = value
                found = True
                break
        if not found:
            return _NOT_FOUND
        i = 1
        while i < len(state):
            if _same(state[i], obj):
                token = state[i + 1]
                if token in self.d:
                    return self.d[token]
                return _NOT_FOUND
            i = i + 2
        return _NOT_FOUND

    def put(self, obj, val):
        state = []
        found = False
        for key in self.d:
            value = self.d[key]
            if isinstance(value, list) and len(value) > 0 and value[0] is _MEMO_STATE:
                state = value
                found = True
                break
        if found:
            i = 1
            while i < len(state):
                if _same(state[i], obj):
                    self.d[state[i + 1]] = val
                    return
                i = i + 2
        else:
            key = _new_token(self.d)
            state = [_MEMO_STATE]
            self.d[key] = state
        token = _new_token(self.d)
        self.d[token] = val
        state.append(obj)
        state.append(token)


class _NotFound:
    def __init__(self) -> None:
        self.tag = 0


_NOT_FOUND = _NotFound()


def _refuse(x, deep):
    kind = "deep" if deep else "shallow"
    raise Error("un(%s)copyable object of type %s (class instances have no "
                "instance constructor in this compiler)" % (kind, type(x).__name__))


def _attrs(x):
    try:
        return vars(x)
    except TypeError:
        return None


def copy(x):
    """Shallow copy operation on arbitrary Python objects.

    See the module's __doc__ string for more info.
    """
    if _is_atomic(x):
        return x
    elif isinstance(x, list):
        return _copy_list(x)
    elif isinstance(x, dict):
        return _copy_dict(x)
    elif isinstance(x, set):
        return _copy_set(x)
    elif isinstance(x, bytearray):
        return _copy_bytearray(x)
    elif isinstance(x, tuple):
        return x
    else:
        attrs = _attrs(x)
        if isinstance(attrs, dict):
            _refuse(x, False)
        raise Error("un(shallow)copyable object of type %s" % (type(x).__name__,))


def deepcopy(x, memo=None, _nil=[]):
    """Deep copy operation on arbitrary Python objects.

    See the module's __doc__ string for more info.
    """
    if memo is None:
        memo = _Memo({})
    elif not isinstance(memo, _Memo):
        if not isinstance(memo, dict):
            raise TypeError("memo must be a dict")
        memo = _Memo(memo)
    y = memo.get(x)
    if y is not _NOT_FOUND:
        return y

    if isinstance(x, frozenset):
        y = x | frozenset()
        memo.put(x, y)
        return y

    if _is_atomic(x):
        return x
    elif isinstance(x, list):
        y = []
        memo.put(x, y)
        for item in x:
            y.append(deepcopy(item, memo))
        return y
    elif isinstance(x, dict):
        y = {}
        memo.put(x, y)
        for key in x:
            y[deepcopy(key, memo)] = deepcopy(x[key], memo)
        return y
    elif isinstance(x, set):
        y = x.copy()
        memo.put(x, y)
        return y
    elif isinstance(x, bytearray):
        y = bytearray(x)
        memo.put(x, y)
        return y
    elif isinstance(x, tuple):
        items = []
        for item in x:
            items.append(deepcopy(item, memo))
        old = memo.get(x)
        if old is not _NOT_FOUND:
            return old
        same = True
        i = 0
        for item in x:
            if not _same(item, items[i]):
                same = False
                break
            i = i + 1
        if same:
            return x
        y = tuple(items)
        memo.put(x, y)
        return y
    else:
        attrs = _attrs(x)
        if isinstance(attrs, dict):
            _refuse(x, True)
        raise Error("un(deep)copyable object of type %s" % (type(x).__name__,))
