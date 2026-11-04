# line: 6
# names: starred
def f(a: int) -> None:
    print(a)
xs = [1, 2]
f(*xs, 3)
