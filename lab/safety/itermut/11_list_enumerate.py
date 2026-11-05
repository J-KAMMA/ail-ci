xs: list[int] = [10, 20, 30]
seen_index: list[int] = []
seen_value: list[int] = []
for i, x in enumerate(xs):
    seen_index.append(i)
    seen_value.append(x)
    if i == 0:
        xs.append(40)
print("index", seen_index)
print("visited", seen_value)
print("final", xs)
