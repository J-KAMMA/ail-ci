import sched


now = 0


def clock_time():
    return now


def clock_delay(d):
    global now
    print("delay", d)
    now += d


def report(name):
    print(name)


queue = sched.scheduler(clock_time, clock_delay)
queue.enterabs(10, 2, report, argument=("late-priority",))
queue.enterabs(10, 1, report, argument=("early-priority",))
queue.enterabs(10, 1, report, argument=("same-first",))
queue.enterabs(10, 1, report, argument=("same-second",))
queue.enterabs(5, 5, report, argument=("sooner",))
queue.run()
print("now", now)
