from contextlib import ExitStack, closing, nullcontext


class Step:
    def __init__(self, name, swallow=False):
        self.name = name
        self.swallow = swallow

    def __enter__(self):
        print("open", self.name)
        return self

    def __exit__(self, exc_type, exc, tb):
        print("close", self.name, exc_type is None, tb is not None)
        return self.swallow


class Closer:
    def __init__(self, name):
        self.name = name

    def close(self):
        print("closer", self.name)


with ExitStack() as stack:
    a = stack.enter_context(Step("a"))
    b = stack.push(Step("b"))
    c = stack.enter_context(closing(Closer("c")))
    d = stack.enter_context(nullcontext("d"))
    print("values", a.name, b.name, d)

try:
    with ExitStack() as stack:
        stack.enter_context(Step("outer"))
        stack.enter_context(Step("inner"))
        raise KeyError("body")
except KeyError as e:
    print("body error", e)


class Guard:
    def __init__(self):
        self.errors = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.errors.append(None if exc_type is None else exc_type.__name__)
        print("guard", self.errors[-1])
        return True


def failing_cleanup():
    raise ValueError("cleanup")


guard = Guard()
stack = ExitStack()
stack.push(guard)
stack.callback(failing_cleanup)
stack.close()
print("cleanup suppressed", guard.errors)
