def f() -> int:
    x: dict[str, int] = {"a": 1, "b": 2}
    mark = 1
    return len(x)  # repr: {'a': 1, 'b': 2} expr: v_x
print(f())
