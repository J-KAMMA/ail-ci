import sched

now = 0.0


def timefunc():
    return now


def delayfunc(delay):
    global now
    now += delay


def show(label):
    print(label, "priority", now)


def main():
    scheduler = sched.scheduler(timefunc, delayfunc)
    scheduler.enter(1, 3, show, ("low",))
    scheduler.enter(1, 1, show, ("high",))
    scheduler.enter(1, 2, show, ("middle",))
    scheduler.enter(0, 9, show, ("now",))
    scheduler.run()
    print("clock", now)


main()
