# task: Set a low recursion limit with sys.setrecursionlimit, trigger RecursionError from an unbounded function, and print a fixed message when it is caught.
import sys


def unbounded(n: int) -> int:
    """Recurses without a base case, so it can only stop by exhausting the stack."""
    return unbounded(n + 1) + 1


def main() -> None:
    original_limit: int = sys.getrecursionlimit()
    low_limit: int = 200
    sys.setrecursionlimit(low_limit)
    try:
        unbounded(0)
    except RecursionError:
        print("RecursionError caught: recursion limit reached.")
    finally:
        sys.setrecursionlimit(original_limit)


if __name__ == "__main__":
    main()
