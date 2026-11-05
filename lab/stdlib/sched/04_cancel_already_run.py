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
first = queue.enter(1, 1, report, argument=("first",))
queue.enter(2, 1, report, argument=("second",))
queue.run()
try:
    queue.cancel(first)
except ValueError as exc:
    print("ValueError", exc)
print("empty", queue.empty())
print("now", clock.now)
