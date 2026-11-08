def f() -> int:
    x: list[str] = ["a", "b"]
    mark = 1  # repr: ['a', 'b'] expr: v_x
    return len(x)
print(f())
