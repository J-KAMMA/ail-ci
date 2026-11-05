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
queue.enterabs(2 ** 62, 1, report, argument=("large",))
queue.enterabs(2 ** 62 + 3, 2, report, argument=("later",))
print("next", queue.run(blocking=False))
print("empty", queue.empty())
queue.run()
print("now", clock.now)
print("empty", queue.empty())
