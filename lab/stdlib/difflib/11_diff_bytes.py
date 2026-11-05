import difflib


def main():
    old = [b"alpha\n", b"beta\n", b"gamma\n"]
    new = [b"alpha\n", b"BETA\n", b"gamma\n", b"delta\n"]
    for line in difflib.diff_bytes(
        difflib.unified_diff,
        old,
        new,
        fromfile=b"old.bin",
        tofile=b"new.bin",
        n=1,
    ):
        print(line)
    for line in difflib.diff_bytes(
        difflib.context_diff,
        old,
        new,
        fromfile=b"old.bin",
        tofile=b"new.bin",
        n=1,
    ):
        print(line)
    try:
        list(difflib.diff_bytes(difflib.unified_diff, ["a"], [b"b"]))
    except TypeError as exc:
        print("TypeError:", exc)


main()
