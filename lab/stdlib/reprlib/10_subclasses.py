import reprlib


class MyClass:
    def __init__(self, value):
        self.value = value


class MyRepr(reprlib.Repr):
    def repr_MyClass(self, x, level):
        return "MyClass(%d)" % x.value

    def repr_str(self, x, level):
        return "STR:" + x

    def repr_instance(self, x, level):
        if isinstance(x, MyClass):
            return self.repr_MyClass(x, level)
        s = "%r" % (x,)
        if len(s) > self.maxother:
            i = max(0, (self.maxother - 3) // 2)
            j = max(0, self.maxother - 3 - i)
            s = s[:i] + self.fillvalue + s[len(s) - j:]
        return s


def main():
    r = MyRepr()
    print("custom", r.repr(MyClass(42)))
    print("inside list", r.repr(["hello", MyClass(7), "world"]))
    print("string override", r.repr("hello"))
    print("nested", r.repr({"item": MyClass(3), "text": "abc"}))
    print("tuple", r.repr((MyClass(1), MyClass(2))))
    print("base", isinstance(r, reprlib.Repr))


main()
