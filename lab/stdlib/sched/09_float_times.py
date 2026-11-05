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
queue.enter(0.5, 1, report, argument=("half",))
queue.enterabs(1.25, 1, report, argument=("quarter",))
queue.enter(0.1, 1, report, argument=("tenth",))
print("next", queue.run(blocking=False))
queue.run()
print("now", now)
