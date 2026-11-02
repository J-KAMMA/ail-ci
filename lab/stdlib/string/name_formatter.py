import string
from string import capwords as title_case

NAMES = ["  ada lovelace ", "GRACE HOPPER", "edsger,w,dijkstra", "", "  ", "alan turing"]


def format_name(raw, sep=None):
    return title_case(raw, sep) if sep is not None else title_case(raw)


def main():
    for name in NAMES:
        print(repr(string.capwords(name)))
        print(repr(format_name(name)))
    print(repr(string.capwords("a,b,,c", ",")))
    print(repr(string.capwords("a,b,,c", sep=",")))
    print(repr(title_case("  multi   space  name ")))
    try:
        print(string.capwords("a b", 3))
    except Exception as exc:
        print(type(exc).__name__, exc)


main()
