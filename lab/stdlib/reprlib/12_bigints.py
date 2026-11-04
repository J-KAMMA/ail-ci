import reprlib


def main():
    print("before")
    print("big", reprlib.repr(10 ** 50))
    print("power", reprlib.repr(2 ** 70))
    r = reprlib.Repr(maxlong=10)
    print("cut", r.repr(123456789012345))
    print("small", r.repr(12345))
    print("negative", r.repr(-123456789012345))
    print("after")


main()
