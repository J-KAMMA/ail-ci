def first(items: list[int]) -> int:
    return next(iter(items))


print("prefix", first([7, 8]))
print("single", first([9]))
print("next", first([]))
