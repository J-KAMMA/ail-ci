# task: Write a contextlib.contextmanager that logs entry, normal exit, and any exception raised inside its with block, then exercise it twice.
import contextlib
from typing import Iterator


@contextlib.contextmanager
def logged(name: str) -> Iterator[None]:
    print(f"[{name}] enter")
    try:
        yield
    except BaseException as exc:
        print(f"[{name}] exception: {type(exc).__name__}: {exc}")
        raise
    else:
        print(f"[{name}] normal exit")
    finally:
        print(f"[{name}] leave")


def main() -> None:
    with logged("first"):
        print("  working inside first block")

    try:
        with logged("second"):
            print("  working inside second block")
            raise ValueError("something went wrong")
    except ValueError as caught:
        print(f"caught outside: {caught}")


if __name__ == "__main__":
    main()
