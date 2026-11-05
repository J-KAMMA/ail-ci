def scale(value: float, factor: float) -> float:
    return value / factor


zero = 0.0
print("prefix", scale(9.0, 3.0))
print("half", scale(1.0, 2.0))
print("next", scale(7.0, zero))
