# general
def f() -> None:
    x = None
    mark = 1  # repr: None expr: f.slots[1]
    return x
print(f())
