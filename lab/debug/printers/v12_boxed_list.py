# general
def f() -> int:
    x = [1, 2, 3]
    mark = 1  # repr: [1, 2, 3] expr: f.slots[2]
    return len(x)
print(f())
