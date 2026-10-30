"""An `e.errno` / `e.strerror` read in a handler, with the OSError raised by the runtime (open ...) and an outer handler that
binds no name, against CPython 3.12.

The runtime's own OSErrors carry their errno and strerror only in a program that reads exception values; a program whose
only read was `e.errno` kept the old runtime, so `e.errno` raised a RuntimeError that an outer `except Exception:` (or a
bare `except:`) swallowed: "caught" was printed where CPython prints the errno.
"""
import unittest

from test_ail_pathlib import Base

NOBIND = r'''def inner_errno() -> None:
    try:
        open("/nonexistent")
    except OSError as e:
        print(e.errno)


def inner_strerror() -> None:
    try:
        open("/nonexistent/x")
    except OSError as e:
        print(e.strerror)


def inner_both() -> None:
    try:
        open("/nonexistent")
    except FileNotFoundError as e:
        print(e.errno, e.strerror)


def inner_loop() -> None:
    for i in range(3):
        try:
            open("/nonexistent")
        except OSError as e:
            print(i, e.errno)


def inner_finally() -> None:
    try:
        try:
            open("/nonexistent")
        except OSError as e:
            print(e.errno)
        finally:
            print("fin")
    finally:
        print("fin2")


def inner_user() -> None:
    try:
        raise OSError(13, "denied")
    except OSError as e:
        print(e.errno, e.strerror)


def inner_value() -> None:
    try:
        int("x")
    except ValueError:
        print("value")


def main():
    try:
        inner_errno()
    except Exception:
        print("caught Exception")
    try:
        inner_strerror()
    except Exception:
        print("caught Exception")
    try:
        inner_both()
    except Exception:
        print("caught Exception")
    try:
        inner_loop()
    except Exception:
        print("caught Exception")
    try:
        inner_finally()
    except Exception:
        print("caught Exception")
    try:
        inner_user()
    except Exception:
        print("caught Exception")
    try:
        inner_value()
    except Exception:
        print("caught Exception")
    try:
        inner_errno()
    except OSError:
        print("caught OSError")
    try:
        inner_strerror()
    except (ValueError, KeyError):
        print("caught ValueError")
    try:
        inner_loop()
    except Exception as ex:
        print("caught bound")
    try:
        for _ in range(2):
            inner_errno()
    except Exception:
        print("caught loop")
    try:
        try:
            open("/nonexistent")
        except OSError as e:
            print(e.errno)
    except Exception:
        print("caught same function")
    print("end")


main()
'''

BARE = r'''def work() -> None:
    try:
        open("/nonexistent")
    except OSError as e:
        print(e.errno)


def main():
    try:
        work()
    except:
        print("caught")
    print("end")


main()
'''


class NoBind(Base):
    def test_outer_handlers_without_a_name_typed(self):
        self.compare("nobind", NOBIND, mode="typed", irs=("0", "1"))

    def test_bare_except_outer(self):
        self.compare("bare", BARE, mode="typed", irs=("0", "1"))


if __name__ == "__main__":
    unittest.main()
