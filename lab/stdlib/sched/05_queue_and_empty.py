import sched


class Clock:
    def __init__(self):
        self.now = 0

    def time(self):
        return self.now

    def delay(self, d):
        print("delay", d)
        self.now += d


def alpha(value):
    print("alpha", value)


def beta():
    print("beta")


clock = Clock()
queue = sched.scheduler(clock.time, clock.delay)
queue.enterabs(2.5, 2, beta)
queue.enterabs(1, 1, alpha, argument=(7,))
for event in queue.queue:
    print(event.time, event.priority, event.action.__name__)
print("empty", queue.empty())
queue.run()
print("empty", queue.empty())
print("now", clock.now)
