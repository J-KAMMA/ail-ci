import sched

now = 0.0


def timefunc():
    return now


def delayfunc(delay):
    global now
    now += delay


def action(label):
    print("action", label)


def main():
    scheduler = sched.scheduler(timefunc, delayfunc)
    scheduler.enter(3, 2, action, ("c",))
    scheduler.enter(1, 5, action, ("a",))
    scheduler.enter(1, 1, action, ("b",))
    items = scheduler.queue
    print("count", len(items))
    for event in items:
        print(event.time, event.priority, event.sequence, event.argument)
    print("first", items[0].argument[0])
    print("last", items[-1].argument[0])


main()
