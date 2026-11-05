import sched

now = 100.0


def timefunc():
    return now


def delayfunc(delay):
    global now
    now += delay


def greet(greeting, name):
    print(greeting, name, "at", now)


def main():
    scheduler = sched.scheduler(timefunc, delayfunc)
    scheduler.enterabs(101, 2, greet, ("hi", "bob"))
    scheduler.enterabs(100, 1, greet, ("hello", "ann"))
    scheduler.enter(4, 1, greet, ("hey", "cat"))
    scheduler.run()
    print("clock", now)
    print("empty", scheduler.empty())


main()
