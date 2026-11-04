import difflib


def main():
    old = "one\ntwo\nthree\n".splitlines(True)
    new = "ore\ntree\nemu\n".splitlines(True)
    delta = list(difflib.ndiff(old, new))
    print("".join(delta), end="")
    print("restored old:", "".join(difflib.restore(delta, 1)), end="")
    print("restored new:", "".join(difflib.restore(delta, 2)), end="")
    unchanged = list(difflib.ndiff(["same\n"], ["same\n"]))
    print("unchanged:", unchanged)
    try:
        list(difflib.restore(delta, 3))
    except ValueError as exc:
        print("error:", exc)
    print(list(difflib.ndiff([], [])))


main()
