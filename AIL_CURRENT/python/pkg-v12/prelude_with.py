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
