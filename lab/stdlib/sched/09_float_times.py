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
    print("event", name)


clock = Clock()
queue = sched.scheduler(clock.time, clock.delay)
queue.enter(0.5, 1, report, argument=("half",))
queue.enterabs(1.25, 1, report, argument=("quarter",))
queue.enter(0.1, 1, report, argument=("tenth",))
print("next", queue.run(blocking=False))
queue.run()
print("now", clock.now)
