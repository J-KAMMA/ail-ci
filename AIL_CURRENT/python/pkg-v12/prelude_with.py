# -*- coding: utf-8 -*-
# prelude_with.py -- what withlib.py adds to a program that has `with` on a user manager or contextlib names (general
# path only): the stand-in of the exception class that __exit__ receives, and the classes of contextlib.


_ail_with_builtin_exc = ["BaseException", "Exception", "ArithmeticError", "AssertionError", "AttributeError",
                         "EOFError", "FloatingPointError", "IndexError", "KeyError", "LookupError", "MemoryError",
                         "NameError", "NotImplementedError", "OSError", "OverflowError", "RecursionError",
                         "RuntimeError", "StopIteration", "SystemExit", "TypeError", "ValueError",
                         "ZeroDivisionError", "UnicodeError", "UnicodeDecodeError", "UnicodeEncodeError",
                         "FileNotFoundError", "FileExistsError", "PermissionError", "IsADirectoryError",
                         "NotADirectoryError", "TimeoutError", "ConnectionError", "KeyboardInterrupt"]


class _AilExcType:
    # the first argument of __exit__: there are no class values here, so a value that prints, compares by name
    # (withlib.py rewrites `exc_type is X` / `issubclass(exc_type, X)` inside __exit__) and has __name__
    def __init__(self, name: str):
        self.__name__ = name
        self.__qualname__ = name

    def __repr__(self) -> str:
        if self.__name__ in _ail_with_builtin_exc:
            return "<class '" + self.__name__ + "'>"
        return "<class '__main__." + self.__name__ + "'>"

    def __str__(self) -> str:
        return self.__repr__()


class _AilTraceback:
    # the third argument of __exit__ when the body raised: AIL has no traceback object, so it is only a
    # non-None stand-in; withlib.py refuses any use other than an `is None` / `is not None` test
    pass


class _AilGenCM:
    # @contextmanager: the generator's `yield` statements were rewritten (withlib.py) so that send(exc) raises exc there
    def __init__(self, gen):
        self.gen = gen

    def __enter__(self):
        try:
            return next(self.gen)
        except StopIteration:
            raise RuntimeError("generator didn't yield")

    def __exit__(self, exc_type, exc, tb):
        if exc is None:
            try:
                next(self.gen)
            except StopIteration:
                return False
            raise RuntimeError("generator didn't stop")
        try:
            self.gen.send(exc)
        except StopIteration:
            return True
        except RuntimeError as e2:
            # CPython's contextlib re-raises the original value when throw() wrapped a sent
            # StopIteration in PEP 479's RuntimeError (the runtime keeps that cause identity);
            # it does not suppress a RuntimeError raised for any other reason.
            if e2 is exc or (isinstance(exc, StopIteration) and _ail_exc_cause_is(e2, exc)):
                return False
            raise
        except Exception as e2:
            if e2 is exc:
                return False
            raise
        raise RuntimeError("generator didn't stop after throw()")


class _AilClosing:
    def __init__(self, thing):
        self.thing = thing

    def __enter__(self):
        return self.thing

    def __exit__(self, exc_type, exc, tb):
        self.thing.close()
        return False


class _AilNullContext:
    def __init__(self, enter_result=None):
        self.enter_result = enter_result

    def __enter__(self):
        return self.enter_result

    def __exit__(self, exc_type, exc, tb):
        return False


class _AilMissing:
    pass


_ail_missing = _AilMissing()

_ail_exc_bases = {
    "BaseException": "",
    "SystemExit": "BaseException",
    "KeyboardInterrupt": "BaseException",
    "GeneratorExit": "BaseException",
    "Exception": "BaseException",
    "StopIteration": "Exception",
    "StopAsyncIteration": "Exception",
    "ArithmeticError": "Exception",
    "FloatingPointError": "ArithmeticError",
    "OverflowError": "ArithmeticError",
    "ZeroDivisionError": "ArithmeticError",
    "AssertionError": "Exception",
    "AttributeError": "Exception",
    "BufferError": "Exception",
    "EOFError": "Exception",
    "ImportError": "Exception",
    "ModuleNotFoundError": "ImportError",
    "LookupError": "Exception",
    "IndexError": "LookupError",
    "KeyError": "LookupError",
    "MemoryError": "Exception",
    "NameError": "Exception",
    "UnboundLocalError": "NameError",
    "OSError": "Exception",
    "BlockingIOError": "OSError",
    "ChildProcessError": "OSError",
    "ConnectionError": "OSError",
    "BrokenPipeError": "ConnectionError",
    "ConnectionAbortedError": "ConnectionError",
    "ConnectionRefusedError": "ConnectionError",
    "ConnectionResetError": "ConnectionError",
    "FileExistsError": "OSError",
    "FileNotFoundError": "OSError",
    "InterruptedError": "OSError",
    "IsADirectoryError": "OSError",
    "NotADirectoryError": "OSError",
    "PermissionError": "OSError",
    "ProcessLookupError": "OSError",
    "TimeoutError": "OSError",
    "ReferenceError": "Exception",
    "RuntimeError": "Exception",
    "NotImplementedError": "RuntimeError",
    "RecursionError": "RuntimeError",
    "SyntaxError": "Exception",
    "IndentationError": "SyntaxError",
    "TabError": "IndentationError",
    "SystemError": "Exception",
    "TypeError": "Exception",
    "ValueError": "Exception",
    "UnicodeError": "ValueError",
    "UnicodeDecodeError": "UnicodeError",
    "UnicodeEncodeError": "UnicodeError",
    "UnicodeTranslateError": "UnicodeError",
    "Warning": "Exception",
}



def _ail_exc_is(exc, name: str) -> bool:
    current = _ail_exc_name(exc)
    while current:
        if current == name:
            return True
        if current in _ail_exc_bases:
            current = _ail_exc_bases[current]
        else:
            current = ""
    return False


class _AilExitStack:
    def __init__(self):
        self.kinds: list = []
        self.managers: list = []
        self.funcs: list = []
        self.args1: list = []
        self.args2: list = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        received = exc_type is not None
        suppressed = False
        pending = None
        while self.kinds:
            kind = self.kinds.pop()
            try:
                if kind == 0:
                    cm = self.managers.pop()
                    result = cm.__exit__(exc_type, exc, tb)
                elif kind == 1:
                    func = self.funcs.pop()
                    arg1 = self.args1.pop()
                    arg2 = self.args2.pop()
                    if arg1 is _ail_missing:
                        func()
                    elif arg2 is _ail_missing:
                        func(arg1)
                    else:
                        func(arg1, arg2)
                    result = False
                else:
                    func = self.funcs.pop()
                    result = func(exc_type, exc, tb)
            except Exception as e:
                pending = e
                exc_type = _AilExcType(_ail_exc_name(e))
                exc = e
                tb = _AilTraceback()
                result = False
            if result:
                suppressed = True
                pending = None
                exc_type = None
                exc = None
                tb = None
        if pending is not None:
            raise pending
        return received and suppressed

    def enter_context(self, cm):
        result = cm.__enter__()
        self.kinds.append(0)
        self.managers.append(cm)
        return result

    def push(self, exit):
        # CPython registers the __exit__ of a manager without entering it; a plain callable is called with the
        # three __exit__ arguments.
        if callable(exit):
            self.kinds.append(2)
            self.funcs.append(exit)
        else:
            self.kinds.append(0)
            self.managers.append(exit)
        return exit

    def callback(self, func, arg1=_ail_missing, arg2=_ail_missing):
        self.kinds.append(1)
        self.funcs.append(func)
        self.args1.append(arg1)
        self.args2.append(arg2)
        return func

    def pop_all(self):
        new = _AilExitStack()
        new.kinds = self.kinds
        new.managers = self.managers
        new.funcs = self.funcs
        new.args1 = self.args1
        new.args2 = self.args2
        self.kinds = []
        self.managers = []
        self.funcs = []
        self.args1 = []
        self.args2 = []
        return new

    def close(self):
        pending = None
        while self.kinds:
            kind = self.kinds.pop()
            try:
                if kind == 0:
                    cm = self.managers.pop()
                    cm.__exit__(None, None, None)
                elif kind == 1:
                    func = self.funcs.pop()
                    arg1 = self.args1.pop()
                    arg2 = self.args2.pop()
                    if arg1 is _ail_missing:
                        func()
                    elif arg2 is _ail_missing:
                        func(arg1)
                    else:
                        func(arg1, arg2)
                else:
                    func = self.funcs.pop()
                    func(None, None, None)
            except Exception as e:
                pending = e
        if pending is not None:
            raise pending


class _AilChdir:
    def __init__(self, path):
        self.path = path
        self.old = ""

    def __enter__(self):
        self.old = _ail_os_getcwd()
        _ail_os_chdir(self.path)

    def __exit__(self, exc_type, exc, tb):
        _ail_os_chdir(self.old)
        return False
