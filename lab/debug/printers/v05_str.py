def f() -> int:
    x = "héllo"
    mark = 1  # repr: 'héllo' expr: v_x
    return len(x)
print(f())
