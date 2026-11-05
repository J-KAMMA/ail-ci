"""Derived from CPython 3.12 Lib/reprlib.py; PSF License, see stdlib/LICENSE-PSF.txt.

Redo the builtin repr() (representation) but with limits on most sizes.  `builtins.repr` is not
available to this compiler, so `_py_repr` asks the `%r` conversion for the builtin representation.
`recursive_repr` keeps CPython's recursion guard, keyed by object identity instead of
`(id(self), get_ident())` because `id()` is not available here; the guard is the one visible
difference and it only shows with concurrent calls on the same object in several threads, which
this single-threaded runtime does not have.  The compiler refuses `@decorator` on a def (methods
and plain functions alike), so the factory can only be applied by calling it: `f =
recursive_repr()(f)`, which behaves like the decorator.  The public surface (`Repr`, `aRepr`,
`recursive_repr`, `repr`) is unchanged.
"""

__all__ = ["Repr", "repr", "recursive_repr"]

def _py_repr(x):
    return "%r" % x


_BARE_TYPE_NAMES = (
    "slice", "object", "type", "memoryview", "property", "staticmethod",
    "classmethod", "super", "enumerate", "zip", "map", "filter", "reversed",
    "function", "builtin_function_or_method", "method", "module", "generator",
    "NoneType", "ellipsis", "NotImplementedType", "code", "frame", "traceback",
    "cell", "mappingproxy", "dict_keys", "dict_values", "dict_items",
    "getset_descriptor", "member_descriptor", "wrapper_descriptor",
    "method_descriptor",
    "BaseException", "BaseExceptionGroup", "Exception", "ExceptionGroup",
    "ArithmeticError", "AssertionError", "AttributeError", "BlockingIOError",
    "BrokenPipeError", "BufferError", "BytesWarning", "ChildProcessError",
    "ConnectionAbortedError", "ConnectionError", "ConnectionRefusedError",
    "ConnectionResetError", "DeprecationWarning", "EOFError",
    "EncodingWarning", "EnvironmentError", "FileExistsError",
    "FileNotFoundError", "FloatingPointError", "FutureWarning",
    "GeneratorExit", "IOError", "ImportError", "ImportWarning",
    "IndentationError", "IndexError", "InterruptedError", "IsADirectoryError",
    "KeyError", "KeyboardInterrupt", "LookupError", "MemoryError",
    "ModuleNotFoundError", "NameError", "NotADirectoryError",
    "NotImplementedError", "OSError", "OverflowError",
    "PendingDeprecationWarning", "PermissionError", "ProcessLookupError",
    "RecursionError", "ReferenceError", "ResourceWarning", "RuntimeError",
    "RuntimeWarning", "StopAsyncIteration", "StopIteration", "SyntaxError",
    "SyntaxWarning", "SystemError", "SystemExit", "TabError", "TimeoutError",
    "TypeError", "UnboundLocalError", "UnicodeDecodeError",
    "UnicodeEncodeError", "UnicodeError", "UnicodeTranslateError",
    "UnicodeWarning", "UserWarning", "ValueError", "Warning",
    "ZeroDivisionError",
)

_MODULE_TYPE_NAMES = {
    "deque": "collections.deque",
    "OrderedDict": "collections.OrderedDict",
    "defaultdict": "collections.defaultdict",
    "Counter": "collections.Counter",
    "UserDict": "collections.UserDict",
    "UserList": "collections.UserList",
    "UserString": "collections.UserString",
    "array": "array.array",
}


def _type_label(value):
    """CPython's `type(value)` text, rebuilt from the class name.

    This compiler exposes only `type(x).__name__`, not the class object, so the module is not
    readable.  The builtin scalar and container types are recognised by identity, the builtin
    types the compiler cannot name (a `slice`, a `memoryview`, an exception, ...) by name, and
    the collections/array classes by name with their module.  Every other class is a class of
    the program, and CPython prints `__main__` for it.
    """
    name = value.__class__.__name__
    if (type(value) is bool or type(value) is int or type(value) is str
            or type(value) is float or type(value) is complex or type(value) is bytes
            or type(value) is bytearray or type(value) is list or type(value) is tuple
            or type(value) is dict or type(value) is set or type(value) is frozenset
            or type(value) is range):
        return "<class '" + name + "'>"
    if name in _BARE_TYPE_NAMES:
        return "<class '" + name + "'>"
    if name in _MODULE_TYPE_NAMES:
        return "<class '" + _MODULE_TYPE_NAMES[name] + "'>"
    return "<class '__main__." + name + "'>"


def recursive_repr(fillvalue="..."):
    """Decorator to make a repr function return fillvalue for a recursive call."""

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
                for i in range(len(running) - 1, -1, -1):
                    if running[i] is self:
                        running.pop(i)
                        break
            return result

        return wrapper

    return decorating_function


class Repr:

    def __init__(
        self, maxlevel=6, maxtuple=6, maxlist=6, maxarray=5, maxdict=4,
        maxset=6, maxfrozenset=6, maxdeque=6, maxstring=30, maxlong=40,
        maxother=30, fillvalue="...", indent=None,
    ):
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
        if typename == "list":
            return self.repr_list(x, level)
        if typename == "tuple":
            return self.repr_tuple(x, level)
        if typename == "str":
            return self.repr_str(x, level)
        if typename == "int":
            return self.repr_int(x, level)
        if typename == "dict":
            return self.repr_dict(x, level)
        if typename == "set":
            return self.repr_set(x, level)
        if typename == "frozenset":
            return self.repr_frozenset(x, level)
        if typename == "deque":
            return self.repr_deque(x, level)
        if typename == "array":
            return self.repr_array(x, level)
        return self.repr_instance(x, level)

    def _join(self, pieces, level):
        if self.indent is None:
            return ", ".join(pieces)
        if not pieces:
            return ""
        indent = self.indent
        if isinstance(indent, int):
            if indent < 0:
                raise ValueError(
                    f"Repr.indent cannot be negative int (was {indent!r})"
                )
            indent *= " "
        try:
            sep = ",\n" + (self.maxlevel - level + 1) * indent
        except TypeError:
            raise TypeError(
                "Repr.indent must be a str, int or None, not %s"
                % _type_label(indent)
            )
        allpieces = [""]
        allpieces.extend(pieces)
        allpieces.append("")
        return sep.join(allpieces)[1:-len(indent) or None]

    def _repr_iterable(self, x, level, left, right, maxiter, trail=""):
        n = len(x)
        if level <= 0 and n:
            s = self.fillvalue
        else:
            newlevel = level - 1
            pieces = []
            count = 0
            for elem in x:
                if count >= maxiter:
                    break
                pieces.append(self.repr1(elem, newlevel))
                count = count + 1
            if n > maxiter:
                pieces.append(self.fillvalue)
            s = self._join(pieces, level)
            if n == 1 and trail and self.indent is None:
                right = trail + right
        return "%s%s%s" % (left, s, right)

    def repr_tuple(self, x, level):
        return self._repr_iterable(x, level, "(", ")", self.maxtuple, ",")

    def repr_list(self, x, level):
        return self._repr_iterable(x, level, "[", "]", self.maxlist)

    def repr_array(self, x, level):
        if not x:
            return "array('%s')" % x.typecode
        header = "array('%s', [" % x.typecode
        return self._repr_iterable(x, level, header, "])", self.maxarray)

    def repr_set(self, x, level):
        if not x:
            return "set()"
        x = _possibly_sorted(x)
        return self._repr_iterable(x, level, "{", "}", self.maxset)

    def repr_frozenset(self, x, level):
        if not x:
            return "frozenset()"
        x = _possibly_sorted(x)
        return self._repr_iterable(x, level, "frozenset({", "})",
                                   self.maxfrozenset)

    def repr_deque(self, x, level):
        return self._repr_iterable(x, level, "deque([", "])", self.maxdeque)

    def repr_dict(self, x, level):
        n = len(x)
        if n == 0:
            return "{}"
        if level <= 0:
            return "{" + self.fillvalue + "}"
        newlevel = level - 1
        pieces = []
        keys = _possibly_sorted(x)
        for key in keys[:self.maxdict]:
            keyrepr = self.repr1(key, newlevel)
            valrepr = self.repr1(x[key], newlevel)
            pieces.append("%s: %s" % (keyrepr, valrepr))
        if n > self.maxdict:
            pieces.append(self.fillvalue)
        s = self._join(pieces, level)
        return "{%s}" % (s,)

    def repr_str(self, x, level):
        s = _py_repr(x[:self.maxstring])
        if len(s) > self.maxstring:
            i = max(0, (self.maxstring - 3) // 2)
            j = max(0, self.maxstring - 3 - i)
            s = _py_repr(x[:i] + x[len(x) - j:])
            s = s[:i] + self.fillvalue + s[len(s) - j:]
        return s

    def repr_int(self, x, level):
        s = _py_repr(x)
        if len(s) > self.maxlong:
            i = max(0, (self.maxlong - 3) // 2)
            j = max(0, self.maxlong - 3 - i)
            s = s[:i] + self.fillvalue + s[len(s) - j:]
        return s

    def repr_instance(self, x, level):
        try:
            s = _py_repr(x)
        except Exception:
            return "<%s instance at %#x>" % (x.__class__.__name__, hash(x))
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
