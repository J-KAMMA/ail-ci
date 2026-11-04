# line: 5
# names: is not defined
def outer() -> None:
    def inner() -> None:
        return missing_name

    inner()

outer()
