import sched


class Clock:
    def __init__(self):
        self.now = 0

    def time(self):
        return self.now

    def delay(self, d):
        print("delay", d)
        self.now += d


def say(label, extra="", flag=False):
    print("action", label, extra, flag)


clock = Clock()
queue = sched.scheduler(clock.time, clock.delay)
queue.enter(5, 1, say, argument=("five",), kwargs={"extra": "x"})
queue.enterabs(3, 2, say, argument=("three",), kwargs={"flag": True})
queue.enter(1, 3, say, argument=("one",))
print("empty", queue.empty())
queue.run()
print("empty", queue.empty())
print("now", clock.now)
