# line: 3
# names: keyword-only parameter
def f(*, a: int) -> None:
    print(a)
f(a=1)
