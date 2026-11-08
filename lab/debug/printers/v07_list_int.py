def f() -> int:
    x: list[int] = [1, 2, 3]
    mark = 1  # repr: [1, 2, 3] expr: v_x
    return len(x)
print(f())
