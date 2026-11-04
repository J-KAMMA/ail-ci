import reprlib


def main():
    deep = [[[[[[1, 2, 3]]]]]]
    print("default", reprlib.repr(deep))
    r = reprlib.Repr()
    r.maxlevel = 3
    print("level 3", r.repr(deep))
    r.maxlevel = 1
    print("level 1", r.repr([1, [2, [3]]]))
    r.maxlevel = 0
    print("level 0", r.repr([1, 2, 3]))
    print("wide", reprlib.repr([1, 2, 3, 4, 5, 6, 7, 8]))
    tracked = {"level1": {"level2": {"level3": {"level4": [1, 2, 3]}}}}
    print("tracked", reprlib.repr(tracked))


main()
