import timeit

t0 = timeit.default_timer()
total = 0
for i in range(100):
    total = total + i
t1 = timeit.default_timer()
diff = t1 - t0

print("total:", total)
print("types:", type(t0).__name__, type(t1).__name__, type(diff).__name__)
print("non_negative:", diff >= 0.0)
