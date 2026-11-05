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
queue.enterabs(2, 1, report, argument=("a",))
target = queue.enterabs(4, 1, report, argument=("b",))
queue.enterabs(6, 1, report, argument=("c",))
print("len before", len(queue.queue))
queue.cancel(target)
print("after cancel", queue.empty(), len(queue.queue))
queue.run()
print("after run", queue.empty())
print("now", clock.now)
