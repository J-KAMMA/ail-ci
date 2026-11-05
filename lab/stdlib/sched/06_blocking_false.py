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
queue.enterabs(2 ** 62, 1, report, argument=("large",))
queue.enterabs(2 ** 62 + 3, 2, report, argument=("later",))
print("next", queue.run(blocking=False))
print("empty", queue.empty())
queue.run()
print("now", now)
print("empty", queue.empty())
