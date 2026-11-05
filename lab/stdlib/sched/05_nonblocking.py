import sched

now = 0.0


def timefunc():
    return now


def delayfunc(delay):
    global now
    now += delay


def show(label):
    print("run", label, "at", now)


def main():
    global now
    scheduler = sched.scheduler(timefunc, delayfunc)
    scheduler.enter(0, 1, show, ("due",))
    scheduler.enter(5, 1, show, ("future",))
    delay = scheduler.run(blocking=False)
    print("delay", delay)
    print("clock", now)
    print("left", len(scheduler.queue))
    now += 10
    scheduler.run(blocking=False)
    print("clock", now)
    print("empty", scheduler.empty())


main()
