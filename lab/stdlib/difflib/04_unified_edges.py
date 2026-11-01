import difflib


def render(a, b, **kwargs):
    return list(difflib.unified_diff(a, b, **kwargs))


def main():
    print(render([], []))
    print(render(["a", "b"], ["a", "b"]))
    print(render(["a", "b", "c"], ["a", "x", "c"], n=0, lineterm=""))
    print(render(["a", "b", "c"], ["a", "x", "c"], n=1, lineterm="\n"))
    print(render([], ["new"], fromfile="empty", tofile="full", lineterm=""))
    print(render(["gone"], [], fromfile="full", tofile="empty", lineterm=""))
    try:
        print(render([b"a"], [b"b"]))
    except TypeError as exc:
        print("TypeError:", exc)
    try:
        print(render(["a"], ["b"], fromfile=b"old"))
    except TypeError as exc:
        print("TypeError:", exc)


main()
