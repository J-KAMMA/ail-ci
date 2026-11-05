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
snapshot = queue.queue
queue.enterabs(3, 3, alpha, argument=(9,))
print("snapshot", len(snapshot), "live", len(queue.queue))
for event in snapshot:
    label = "alpha" if event.argument else "beta"
    print(event.time, event.priority, label)
print("empty", queue.empty())
queue.run()
print("empty", queue.empty())
print("now", now)
