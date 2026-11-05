import sched


now = 0


def clock_time():
    return now


def clock_delay(d):
    global now
    print("delay", d)
    now += d


def alpha(value):
    print("alpha", value)


def beta():
    print("beta")


queue = sched.scheduler(clock_time, clock_delay)
queue.enterabs(2.5, 2, beta)
queue.enterabs(1, 1, alpha, argument=(7,))
for event in queue.queue:
    label = "alpha" if event[4] else "beta"
    print(event[0], event[1], label)
print("empty", queue.empty())
queue.run()
print("empty", queue.empty())
print("now", now)
