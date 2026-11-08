def f() -> int:
    x = (1, "x")
    mark = 1  # repr: (1, 'x') expr: v_x
    return len(x)
print(f())
