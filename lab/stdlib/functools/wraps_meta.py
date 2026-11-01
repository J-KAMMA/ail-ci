"""A logging decorator that keeps the wrapped function's metadata with functools.wraps."""
import functools


def logged(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        print("call", fn.__name__, args)
        result = fn(*args, **kwargs)
        print("done", fn.__name__, result)
        return result

    return wrapper


@logged
def add(a, b):
    """Add two numbers."""
    return a + b


@logged
def greet(name, punctuation="!"):
    """Greet somebody."""
    return "hello " + name + punctuation


def main() -> None:
    print(add(2, 3))
    print(greet("sam"))
    print(greet("ada", punctuation="?"))
    print("name", add.__name__, greet.__name__)
    print("doc", add.__doc__, greet.__doc__)
    print("wrapped", add.__wrapped__(10, 20))
    print("type", type(add).__name__, type(greet).__name__)


main()
