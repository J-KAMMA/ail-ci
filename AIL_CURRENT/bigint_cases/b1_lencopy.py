class L:
    def __len__(self):
        return 4611686018427387904

    def copy(self):
        return self

    def split(self):
        return self

    def items(self):
        return self


def via_copy():
    n = len(L().copy())
    return n * 2


def via_split():
    n = len(L().split())
    return n * 2


def via_items():
    n = len(L().items())
    return n * 2


print(via_copy())
print(via_split())
print(via_items())
