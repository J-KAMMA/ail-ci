# line: 4
# names: nested class definition
def outer() -> None:
    class C:
        pass
    print(C)
outer()
