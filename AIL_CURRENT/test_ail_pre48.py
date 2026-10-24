"""pre48: repr() of an exception's arguments, compared with CPython 3.12.

The typed path keeps e.args[i] as its text, so `repr(e.args[i])` used to quote a number
(`'3.0'`) and an alias copied out of e.args lost the argument kind entirely.  A direct
`repr(e.args[i])`, including a negative index and every built-in argument kind, now reads the
argument's own repr on the typed path.  Storing the value in a name, container, attribute or
user function is refused by name there (the default build then takes the general path, which
already keeps the object), so no alias can silently print the wrong repr.
"""
from test_ail_pathlib import Base


DIRECT = r'''def main() -> None:
    try:
        raise ValueError(3.0, -7, True, None, "x")
    except ValueError as e:
        print(repr(e.args[0]))
        print(repr(e.args[1]))
        print(repr(e.args[2]))
        print(repr(e.args[3]))
        print(repr(e.args[4]))
        print(repr(e.args[-1]))
        print(str(e.args[0]), e.args[0])


main()
'''

OSERROR = r'''def main() -> None:
    try:
        raise OSError(2, "gone", "a.txt")
    except OSError as e:
        print(repr(e.args[0]))
        print(repr(e.args[-1]))
        print(repr(e.args))
        print(e.filename)


main()
'''

FILE_OSERROR = r'''def main() -> None:
    try:
        open("pre48_missing_file_xyz.txt", "r")
    except OSError as e:
        print(repr(e.args[-1]))
        print(repr(e.args[-2]))
        print(repr(e.args))
        print(repr(e))
        print(str(e))
        print(type(e).__name__, e.errno, e.filename, e.strerror)

    try:
        open(".", "w")
    except OSError as e:
        print(repr(e.args[-1]))
        print(repr(e.args))
        print(repr(e))
        print(type(e).__name__, e.errno, e.filename)


main()
'''

EMPTY = r'''def main() -> None:
    try:
        raise ValueError()
    except ValueError as e:
        try:
            print(repr(e.args[0]))
        except IndexError as x:
            print(type(x).__name__, x)


main()
'''

ALIASES = r'''class Box:
    def __init__(self) -> None:
        self.v = 0.0


def ident(x: float) -> float:
    return x


def main() -> None:
    try:
        raise ValueError(3.0)
    except ValueError as e:
        s = e.args[0]
        xs = [s]
        d = {"k": s}
        b = Box()
        b.v = ident(s)
        print(repr(s), repr(xs), repr(d), repr(b.v))


main()
'''

FUNCTION_ARGUMENT = r'''def show(x: float) -> None:
    print(repr(x))


def main() -> None:
    try:
        raise ValueError(3.0)
    except ValueError as e:
        show(e.args[0])


main()
'''


class ExceptionArgumentRepr(Base):
    def test_direct_repr_keeps_the_argument_kind(self):
        self.compare('pre48_direct', DIRECT, mode='typed')

    def test_oserror_args_repr(self):
        self.compare('pre48_oserror', OSERROR, mode='typed')

    def test_file_oserror_args_on_the_general_build(self):
        self.compare('pre48_file_oserror', FILE_OSERROR, mode='gonly')

    def test_empty_args_is_an_index_error(self):
        self.compare('pre48_empty', EMPTY, mode='typed')

    def test_aliases_match_on_default_and_general_builds(self):
        self.compare('pre48_alias_default', ALIASES, mode='default')
        self.compare('pre48_alias_general', ALIASES, mode='gonly')

    def test_alias_is_refused_by_name_on_the_typed_path(self):
        self.refused(ALIASES, 'storing an exception argument e.args[i]')
        self.refused(FUNCTION_ARGUMENT, 'storing an exception argument e.args[i]')
