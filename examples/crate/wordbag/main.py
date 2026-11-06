import os

from ail_ffi import *

link("./libwordbag.a")
Bag = Handle("bag", free="wordbag_free")


@extern(header="wordbag.h", trust=True)
def wordbag_new() -> Bag: ...


@extern(header="wordbag.h", trust=True)
def wordbag_add(bag: Bag, p: bytes, n: length("p")) -> None: ...


@extern(header="wordbag.h", trust=True)
def wordbag_bump(bag: Bag, p: bytes, n: length("p"), k: c_uint64) -> None: ...


@extern(header="wordbag.h", trust=True)
def wordbag_seed(bag: Bag, p: bytes, n: length("p")) -> None: ...


@extern(header="wordbag.h", trust=True)
def wordbag_count(bag: Bag, p: bytes, n: length("p")) -> c_uint64: ...


def main():
    bag = wordbag_new()
    print(wordbag_count(bag, b"red"), wordbag_count(bag, b"blue"))
    wordbag_add(bag, b"red")
    wordbag_add(bag, b"blue")
    wordbag_add(bag, b"red")
    print(wordbag_count(bag, b"red"), wordbag_count(bag, b"blue"), wordbag_count(bag, b"green"))
    wordbag_add(bag, b"")
    print(wordbag_count(bag, b""))
    if os.environ.get("WORDLAB_BIG"):
        wordbag_seed(bag, b"huge")
        print(wordbag_count(bag, b"huge"))
        wordbag_bump(bag, b"huge", 5)
        print(wordbag_count(bag, b"huge"))
    bag.close()


main()
