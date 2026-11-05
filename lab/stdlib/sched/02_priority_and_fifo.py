import sched


class Clock:
    def __init__(self):
        self.now = 0

    def time(self):
        return self.now

    def delay(self, d):
        print("delay", d)
        self.now += d


def report(name):
    print(name)


clock = Clock()
queue = sched.scheduler(clock.time, clock.delay)
queue.enterabs(10, 2, report, argument=("late-priority",))
queue.enterabs(10, 1, report, argument=("early-priority",))
queue.enterabs(10, 1, report, argument=("same-first",))
queue.enterabs(10, 1, report, argument=("same-second",))
queue.enterabs(5, 5, report, argument=("sooner",))
queue.run()
print("now", clock.now)
