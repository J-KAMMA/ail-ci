import timeit

state = [0, 0, 0]


def setup_fn():
    state[0] = state[0] + 1


def work_fn():
    state[1] = state[1] + 1


def fake_clock():
    state[2] = state[2] + 10
    return float(state[2])


t = timeit.Timer(work_fn, setup_fn, fake_clock)
d1 = t.timeit(number=4)
d_rep = t.repeat(repeat=2, number=3)
print("setups:", state[0], "calls:", state[1])
print("fake_elapsed:", d1, d_rep)
