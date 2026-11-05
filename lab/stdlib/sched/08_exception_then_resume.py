import sched


class Clock:
    def __init__(self):
        self.now = 0

    def time(self):
        return self.now

    def delay(self, d):
        print("delay", d)
        self.now += d


def ok(label):
    print("ok", label)


def boom():
    print("boom")
    raise RuntimeError("kaboom")


clock = Clock()
queue = sched.scheduler(clock.time, clock.delay)
queue.enterabs(1, 1, ok, argument=("one",))
queue.enterabs(2, 1, boom)
queue.enterabs(3, 1, ok, argument=("three",))
try:
    queue.run()
except RuntimeError as exc:
    print("caught", exc)
print("empty after error", queue.empty())
queue.run()
print("empty", queue.empty())
print("now", clock.now)
