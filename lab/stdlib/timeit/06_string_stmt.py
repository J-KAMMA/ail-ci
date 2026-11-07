import timeit

stmt = "total = 0\nfor i in range(5):\n    total = total + i"
setup = "x = 10"

timer = timeit.Timer(stmt, setup)
elapsed = timer.timeit(number=5)
runs = timer.repeat(repeat=2, number=3)
direct = timeit.timeit("y = 1 + 2", number=4)

print("elapsed_type:", type(elapsed).__name__, elapsed >= 0.0)
print("runs:", type(runs).__name__, len(runs), type(direct).__name__)
