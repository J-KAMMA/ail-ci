def describe(v):
    if isinstance(v, int):
        return "int " + str(v)
    return "other " + repr(v)


def main():
    items = [1, "two", 3.5]
    for it in items:
        print(describe(it))


main()
