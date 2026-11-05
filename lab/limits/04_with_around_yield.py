class Ctx:
    def __enter__(self):
        return 1

    def __exit__(self, t, v, tb):
        return False


def gen():
    with Ctx():
        yield 1


print(list(gen()))
