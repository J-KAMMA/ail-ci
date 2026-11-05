import sched


class Clock:
    def __init__(self):
        self.now = 0

    def time(self):
        return self.now

    def delay(self, d):
        print("delay", d)
        self.now += d


def later(queue, clock):
    print("later", clock.now)
    queue.enter(2, 1, finish, argument=(clock,))


def finish(clock):
    print("finish", clock.now)


clock = Clock()
queue = sched.scheduler(clock.time, clock.delay)
queue.enter(1, 1, later, argument=(queue, clock))
queue.run()
print("now", clock.now)
print("empty", queue.empty())
