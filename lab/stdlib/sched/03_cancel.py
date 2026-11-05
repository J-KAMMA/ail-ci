import sched

now = 0.0


def timefunc():
    return now


def delayfunc(delay):
    global now
    now += delay


def show(label):
    print("run", label)


def main():
    scheduler = sched.scheduler(timefunc, delayfunc)
    first = scheduler.enter(1, 1, show, ("first",))
    second = scheduler.enter(2, 1, show, ("second",))
    third = scheduler.enter(3, 1, show, ("third",))
    print("empty", scheduler.empty())
    scheduler.cancel(second)
    print("queue", len(scheduler.queue))
    scheduler.run()
    print("clock", now)
    print("queue", len(scheduler.queue))


main()
