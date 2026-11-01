# task: Map OSError errno codes to their symbolic names with the errno module by constructing OSError instances for several fixed codes.
import errno
import os
from typing import Final

FIXED_CODES: Final[tuple[int, ...]] = (1, 2, 13, 17, 22, 28, 32, 98, 110, 111)


def symbolic_name(code: int) -> str:
    """Return the symbolic errno name (e.g. 'ENOENT') for a numeric code."""
    return errno.errorcode.get(code, f"UNKNOWN_{code}")


def make_error(code: int) -> OSError:
    """Construct an OSError instance carrying the given errno code."""
    return OSError(code, f"synthetic error {code}")


def round_trips(name: str, code: int) -> bool:
    """Check that the symbolic name maps back to the same numeric code."""
    if name.startswith("UNKNOWN_"):
        return False
    return getattr(errno, name, None) == code


def main() -> None:
    header = f"{'code':>5}  {'name':<14} {'exception':<22} {'round-trip':<10} strerror"
    print(header)
    print("-" * len(header))

    for code in FIXED_CODES:
        err: OSError = make_error(code)
        assert err.errno is not None
        name: str = symbolic_name(err.errno)
        exc_name: str = type(err).__name__
        ok: bool = round_trips(name, err.errno)
        text: str = os.strerror(err.errno)
        print(f"{err.errno:>5}  {name:<14} {exc_name:<22} {str(ok):<10} {text}")

    print()
    print(f"Total codes examined: {len(FIXED_CODES)}")


if __name__ == "__main__":
    main()
