import timeit

calls = [0]


def work():
    calls[0] = calls[0] + 1


timer = timeit.Timer(work)
runs = timer.repeat(repeat=2, number=2)

print("calls:", calls[0])
print("outer_type:", type(runs).__name__, len(runs))
print("elem_types:", type(runs[0]).__name__, type(runs[1]).__name__)
print("non_negative:", runs[0] >= 0.0 and runs[1] >= 0.0)
