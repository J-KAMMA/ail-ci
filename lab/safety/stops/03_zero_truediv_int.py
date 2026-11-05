def rate(total: int, count: int) -> float:
    return total / count


zero = 0
print("prefix", rate(9, 3))
print("half", rate(1, 2))
print("next", rate(7, zero))
