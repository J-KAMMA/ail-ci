import sched


now = 0


def clock_time():
    return now


def clock_delay(d):
    global now
    print("delay", d)
    now += d


def report(name):
    print("event", name)


queue = sched.scheduler(clock_time, clock_delay)
first = queue.enter(1, 1, report, argument=("first",))
queue.enter(2, 1, report, argument=("second",))
queue.run()
try:
    queue.cancel(first)
except ValueError as exc:
    print("ValueError", exc)
print("empty", queue.empty())
print("now", now)
