def f() -> int:
    x: list[float] = [1.5, 2.0]
    mark = 1  # repr: [1.5, 2.0] expr: v_x
    return len(x)
print(f())
