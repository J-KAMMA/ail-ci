import timeit

calls = [0]


def step():
    calls[0] = calls[0] + 1


t_single = timeit.timeit(step, number=5)
t_rep = timeit.repeat(step, repeat=3, number=2)

print("calls:", calls[0])
print("single:", type(t_single).__name__, t_single >= 0.0)
print("repeat:", type(t_rep).__name__, len(t_rep), all(isinstance(x, float) and x >= 0.0 for x in t_rep))
