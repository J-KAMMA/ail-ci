import sched


now = 0


def clock_time():
    return now


def clock_delay(d):
    global now
    print("delay", d)
    now += d


queue = sched.scheduler(clock_time, clock_delay)


def later():
    print("later", now)
    queue.enter(2, 1, finish)


def finish():
    print("finish", now)


queue.enter(1, 1, later)
queue.run()
print("now", now)
print("empty", queue.empty())
