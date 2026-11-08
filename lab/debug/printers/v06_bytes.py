def f() -> int:
    x = b"hi\n"
    mark = 1  # repr: b'hi\n' expr: v_x
    return len(x)
print(f())
