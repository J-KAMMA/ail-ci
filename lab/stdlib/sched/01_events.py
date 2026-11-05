import sched

now = 0.0


def timefunc():
    return now


def delayfunc(delay):
    global now
    now += delay


def hello(name):
    print("hello", name, "at", now)


def main():
    scheduler = sched.scheduler(timefunc, delayfunc)
    scheduler.enter(5, 1, hello, ("world",))
    scheduler.enter(2, 1, hello, ("early",))
    scheduler.enter(8, 1, hello, ("late",))
    print("before", scheduler.empty())
    scheduler.run()
    print("after", scheduler.empty())
    print("clock", now)


main()
