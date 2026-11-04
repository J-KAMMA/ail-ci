"""Richards: the classic scheduling benchmark built from task control blocks.

A scheduler keeps a circular run queue ordered by priority.  One idle task, one
worker, two handlers and four device tasks communicate through packets: a
device queues a packet at a handler, a handler consumes it and holds itself,
and the idle task releases a device after every fixed number of dispatches.
The program prints the handler dispatch count, the packet count and the hold
count for the whole run.
"""
import sys

ID_IDLE = 0
ID_WORKER = 1
ID_HANDLER_A = 2
ID_HANDLER_B = 3
ID_DEVICE_A = 4
ID_DEVICE_B = 5
ID_DEVICE_C = 6
ID_DEVICE_D = 7

PRIORITY_IDLE = 1000
PRIORITY_WORKER = 2000
PRIORITY_HANDLER = 3000
PRIORITY_DEVICE = 4000


class Packet:
    def __init__(self, link, ident, kind):
        self.link = link
        self.ident = ident
        self.kind = kind


class TaskState:
    def __init__(self):
        self.packet_pending = False
        self.task_waiting = False
        self.task_holding = False


class TaskControlBlock:
    def __init__(self, ident, priority):
        self.link = None
        self.ident = ident
        self.priority = priority
        self.queue = None
        self.queue_tail = None
        self.state = TaskState()
        self.scheduler = None
        self.scheduled = False
        self.handled = 0
        self.checksum = 0

    def add_input(self, packet):
        packet.link = None
        if self.queue is None:
            self.queue = packet
            self.queue_tail = packet
            self.state.packet_pending = True
            self.scheduler.check_priority_add(self)
        else:
            self.queue_tail.link = packet
            self.queue_tail = packet

    def take_input(self):
        packet = self.queue
        self.queue = packet.link
        if self.queue is None:
            self.queue_tail = None
            self.state.packet_pending = False
        packet.link = None
        return packet

    def run(self):
        if self.ident == ID_IDLE:
            return self.idle_run()
        if self.ident == ID_WORKER:
            return self.worker_run()
        if self.ident >= ID_DEVICE_A:
            return self.device_run()
        return self.handler_run()

    def idle_run(self):
        self.scheduler.idle_count += 1
        if not self.scheduler.work_left():
            self.scheduler.queue = []
            return
        self.scheduler.release(self.scheduler.devices[self.scheduler.idle_count % 4])
        self.scheduler.hold_self()

    def worker_run(self):
        if self.queue is None:
            self.state.task_waiting = True
            return
        packet = self.take_input()
        self.scheduler.checksum += packet.ident
        target = self.scheduler.handlers[packet.ident & 1]
        packet.kind = 1
        target.add_input(packet)
        self.scheduler.hold_self()

    def device_run(self):
        if self.queue is None:
            self.state.task_waiting = True
            return
        packet = self.take_input()
        self.scheduler.checksum += packet.ident * 3
        target = self.scheduler.handlers[(self.ident - ID_DEVICE_A) & 1]
        target.add_input(packet)
        self.scheduler.hold_self()

    def handler_run(self):
        if self.queue is None:
            self.state.task_waiting = True
            return
        packet = self.take_input()
        self.handled += 1
        self.checksum += packet.ident
        self.scheduler.checksum += packet.ident * 2
        if self.handled % 8 == 0:
            self.scheduler.hold_self()
        else:
            self.scheduler.queue_task(self)


class Scheduler:
    def __init__(self, limit, packets):
        self.queue = []
        self.current = None
        self.idle_count = 0
        self.limit = limit
        self.queue_count = 0
        self.hold_count = 0
        self.checksum = 0
        self.tasks = []
        self.handlers = []
        self.devices = []
        self.worker = None
        self._build(packets)

    def _build(self, packets):
        self.tasks.append(TaskControlBlock(ID_IDLE, PRIORITY_IDLE))
        self.worker = TaskControlBlock(ID_WORKER, PRIORITY_WORKER)
        self.tasks.append(self.worker)
        i = 0
        while i < 2:
            task = TaskControlBlock(ID_HANDLER_A + i, PRIORITY_HANDLER)
            self.handlers.append(task)
            self.tasks.append(task)
            i += 1
        i = 0
        while i < 4:
            task = TaskControlBlock(ID_DEVICE_A + i, PRIORITY_DEVICE)
            self.devices.append(task)
            self.tasks.append(task)
            i += 1
        i = 0
        while i < len(self.tasks):
            self.tasks[i].scheduler = self
            i += 1
        i = 0
        while i < len(self.devices):
            j = 0
            while j < packets:
                self.devices[i].add_input(Packet(None, (i * packets + j) & 255, 0))
                j += 1
            i += 1
        tail = None
        i = 0
        while i < packets:
            packet = Packet(None, i & 255, 0)
            if tail is None:
                self.worker.queue = packet
            else:
                tail.link = packet
            tail = packet
            i += 1
        self.worker.queue_tail = tail
        self.worker.state.packet_pending = True

    def add_running(self, task):
        if task.scheduled:
            return
        task.scheduled = True
        self.queue_count += 1
        i = 0
        while i < len(self.queue) and self.queue[i].priority >= task.priority:
            i += 1
        self.queue.insert(i, task)

    def check_priority_add(self, task):
        task.state.task_waiting = False
        self.add_running(task)

    def work_left(self):
        if self.worker.queue is not None:
            return True
        i = 0
        while i < len(self.devices):
            if self.devices[i].queue is not None:
                return True
            i += 1
        i = 0
        while i < len(self.handlers):
            if self.handlers[i].queue is not None:
                return True
            i += 1
        return False

    def queue_task(self, task):
        if task.state.packet_pending:
            self.add_running(task)

    def release(self, task):
        task.state.task_holding = False
        self.add_running(task)

    def hold_self(self):
        self.hold_count += 1
        self.add_running(self.current)

    def run(self):
        while self.queue:
            task = self.queue.pop(0)
            task.scheduled = False
            self.current = task
            task.run()


def run_once(limit, packets):
    scheduler = Scheduler(limit, packets)
    i = 0
    while i < len(scheduler.tasks):
        scheduler.release(scheduler.tasks[i])
        i += 1
    scheduler.run()
    handled = 0
    i = 0
    while i < len(scheduler.handlers):
        handled += scheduler.handlers[i].handled
        i += 1
    return handled, scheduler.queue_count, scheduler.hold_count, scheduler.checksum


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 250000
    handled, queued, held, checksum = run_once(1 << 60, n)
    print("richards %d %d %d %d" % (handled, queued, held, checksum))


main()
