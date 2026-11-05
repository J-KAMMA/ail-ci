import sched


now = 0


def clock_time():
    return now


def clock_delay(d):
    global now
    print("delay", d)
    now += d


def ok(label):
    print("ok", label)


def boom():
    print("boom")
    raise RuntimeError("kaboom")


queue = sched.scheduler(clock_time, clock_delay)
queue.enterabs(1, 1, ok, argument=("one",))
queue.enterabs(2, 1, boom)
queue.enterabs(3, 1, ok, argument=("three",))
try:
    queue.run()
except RuntimeError as exc:
    print("caught", exc)
print("empty after error", queue.empty())
queue.run()
print("empty", queue.empty())
print("now", now)
