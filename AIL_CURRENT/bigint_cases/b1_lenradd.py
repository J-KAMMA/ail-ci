class R:
    def __radd__(self, other):
        return self

    def __len__(self):
        return 4611686018427387904


def f():
    n = len("a" + R())
    return n * 2


print(f())
