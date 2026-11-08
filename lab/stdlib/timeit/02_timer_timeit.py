import timeit

calls = [0]


def work():
    calls[0] = calls[0] + 1


timer = timeit.Timer(work)
elapsed = timer.timeit(number=3)

print("calls:", calls[0])
print("type:", type(elapsed).__name__)
print("non_negative:", elapsed >= 0.0)
