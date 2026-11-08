"""Derived from CPython 3.12 Lib/copy.py; PSF License, see stdlib/LICENSE-PSF.txt.

Generic (shallow and deep) copying operations.

AIL source rewrite of CPython 3.12's copy.py.  The dispatch tables and the
`type(x)` lookups are replaced by isinstance() chains because this compiler
cannot use a type object as a plain value or as a dict key.  The copy/deepcopy
messages, the memo protocol and the sharing rules are CPython's.  A class
instance is copied through its `__dict__` into a plain shell object (the
compiler has no way to call `cls.__new__`); every program in
lab/stdlib/copy/ only reads the copied fields.

The `__copy__`/`__deepcopy__` hooks are not dispatched: on a value of unknown
static kind the compiler refuses the dunder call, so a class that defines them
is copied through its `__dict__` instead (see
lab/stdlib/copy/03_user_class_hooks.py and lab/stdlib/stdfall2/RESULTS.md).
"""

class Error(Exception):
    pass


error = Error

__all__ = ["Error", "copy", "deepcopy"]


class _Shell:
    def __init__(self):
        pass


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
    y = set()
    for item in x:
        y.add(item)
    return y


def _copy_bytearray(x):
    return bytearray(x)


class _Memo:
    def __init__(self):
        self.pairs = []

    def get(self, obj):
        for pair in self.pairs:
            if pair[0] is obj:
                return pair[1]
        return _NOT_FOUND

    def put(self, obj, val):
        self.pairs.append((obj, val))


class _NotFound:
    pass


_NOT_FOUND = _NotFound()


def _shell(x, deep, memo):
    y = _Shell()
    if deep:
        memo.put(x, y)
    attrs = vars(x)
    for key in attrs:
        if deep:
            setattr(y, key, deepcopy(attrs[key], memo))
        else:
            setattr(y, key, attrs[key])
    return y


def _attrs(x):
    try:
        return vars(x)
    except TypeError:
        return None


def _tuple_of(items):
    n = len(items)
    if n == 0:
        return ()
    if n == 1:
        return (items[0],)
    if n == 2:
        return (items[0], items[1])
    if n == 3:
        return (items[0], items[1], items[2])
    if n == 4:
        return (items[0], items[1], items[2], items[3])
    raise Error("un(deep)copyable tuple of length %d" % (n,))


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
            return _shell(x, False, None)
        raise Error("un(shallow)copyable object of type %s" % (type(x).__name__,))


def deepcopy(x, memo=None, _nil=[]):
    """Deep copy operation on arbitrary Python objects.

    See the module's __doc__ string for more info.
    """
    if memo is None or not isinstance(memo, _Memo):
        memo = _Memo()
    y = memo.get(x)
    if y is not _NOT_FOUND:
        return y

    if isinstance(x, frozenset):
        items = []
        for item in x:
            items.append(deepcopy(item, memo))
        return frozenset(items)

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
        y = set()
        memo.put(x, y)
        for item in x:
            y.add(deepcopy(item, memo))
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
            if item is not items[i]:
                same = False
                break
            i = i + 1
        if same:
            return x
        return _tuple_of(items)
    else:
        attrs = _attrs(x)
        if isinstance(attrs, dict):
            return _shell(x, True, memo)
        raise Error("un(deep)copyable object of type %s" % (type(x).__name__,))
