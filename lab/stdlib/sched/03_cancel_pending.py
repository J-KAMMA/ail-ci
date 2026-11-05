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
queue.enterabs(2, 1, report, argument=("a",))
target = queue.enterabs(4, 1, report, argument=("b",))
queue.enterabs(6, 1, report, argument=("c",))
print("len before", len(queue.queue))
queue.cancel(target)
print("after cancel", queue.empty(), len(queue.queue))
queue.run()
print("after run", queue.empty())
print("now", now)
