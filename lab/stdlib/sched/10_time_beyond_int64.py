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
queue.enterabs(2 ** 62, 1, report, argument=("two62",))
print("next", queue.run(blocking=False))
queue.run()
print("now", clock.now)
queue.enterabs(2 ** 63, 1, report, argument=("two63",))
print("next", queue.run(blocking=False))
queue.run()
print("now", clock.now)
