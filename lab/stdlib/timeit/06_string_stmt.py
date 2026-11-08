import timeit

# The string form needs exec/compile.  This program therefore uses exec, which
# the AIL compiler refuses by name at build time (there is no source text to run
# ahead of time); the callable form is exercised by the other timeit programs.
stmt = "total = 0\nfor i in range(5):\n    total = total + i"
setup = "x = 10"
exec(setup)
exec(stmt)

timer = timeit.Timer(stmt, setup)
elapsed = timer.timeit(number=5)
runs = timer.repeat(repeat=2, number=3)
direct = timeit.timeit("y = 1 + 2", number=4)

print("elapsed_type:", type(elapsed).__name__, elapsed >= 0.0)
print("runs:", type(runs).__name__, len(runs), type(direct).__name__)
