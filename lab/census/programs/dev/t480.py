import sys
from collections import OrderedDict


def main() -> None:
    words: list[str] = sys.stdin.read().split()
    mru: OrderedDict[str, None] = OrderedDict()

    for word in words:
        if word in mru:
            mru.move_to_end(word)
        else:
            mru[word] = None
        print(" ".join(mru))

    print(" ".join(mru))


if __name__ == "__main__":
    main()
