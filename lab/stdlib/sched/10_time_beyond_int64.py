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
queue.enterabs(2 ** 62, 1, report, argument=("two62",))
print("next", queue.run(blocking=False))
queue.run()
print("now", now)
queue.enterabs(2 ** 63, 1, report, argument=("two63",))
print("next", queue.run(blocking=False))
queue.run()
print("now", now)
