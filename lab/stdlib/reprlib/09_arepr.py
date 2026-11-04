import reprlib


def main():
    print("maxlist", reprlib.aRepr.maxlist)
    print("maxstring", reprlib.aRepr.maxstring)
    print("maxdict", reprlib.aRepr.maxdict)
    print("maxlevel", reprlib.aRepr.maxlevel)
    print("maxother", reprlib.aRepr.maxother)
    print("fillvalue", reprlib.aRepr.fillvalue)
    print("repr", reprlib.aRepr.repr(list(range(10))))
    print("module repr", reprlib.repr(list(range(10))))
    old = reprlib.aRepr.maxlist
    reprlib.aRepr.maxlist = 2
    print("changed", reprlib.repr(list(range(5))))
    reprlib.aRepr.maxlist = old
    print("restored", reprlib.repr(list(range(5))))
    print("same", reprlib.aRepr.repr("abcdefghijklmnopqrstuvwxyz0123456789"))


main()
