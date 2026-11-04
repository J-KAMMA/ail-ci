"""Richards: the classic scheduling benchmark built from task control blocks.

A priority-ordered run queue holds one idle task, one worker, two handlers and
four device tasks.  Devices and the worker queue packets at the handlers, a
handler consumes one and holds itself every eighth time, and the idle task
releases a device on every dispatch and stops when no queue is left.  The
program prints the handler dispatch count, the queue and hold counts and a
checksum.
"""
import sys

ID_IDLE, ID_WORKER, ID_HANDLER_A, ID_HANDLER_B = 0, 1, 2, 3
ID_DEVICE_A, ID_DEVICE_B, ID_DEVICE_C, ID_DEVICE_D = 4, 5, 6, 7
PRIORITY_IDLE, PRIORITY_WORKER = 1000, 2000
PRIORITY_HANDLER, PRIORITY_DEVICE = 3000, 4000


class Packet:
    def __init__(self, ident, kind):
        self.link = None
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
        self.scheduler.handlers[packet.ident & 1].add_input(packet)
        self.scheduler.hold_self()

    def device_run(self):
        if self.queue is None:
            self.state.task_waiting = True
            return
        packet = self.take_input()
        self.scheduler.checksum += packet.ident * 3
        self.scheduler.handlers[(self.ident - ID_DEVICE_A) & 1].add_input(packet)
        self.scheduler.hold_self()

    def handler_run(self):
        if self.queue is None:
            self.state.task_waiting = True
            return
        packet = self.take_input()
        self.handled += 1
        self.scheduler.checksum += packet.ident * 2
        if self.handled % 8 == 0:
            self.scheduler.hold_self()
        else:
            self.scheduler.queue_task(self)


class Scheduler:
    def __init__(self, packets):
        self.queue = []
        self.current = None
        self.idle_count = 0
        self.queue_count = 0
        self.hold_count = 0
        self.checksum = 0
        self.tasks = [TaskControlBlock(ID_IDLE, PRIORITY_IDLE)]
        self.worker = TaskControlBlock(ID_WORKER, PRIORITY_WORKER)
        self.tasks.append(self.worker)
        self.handlers = [TaskControlBlock(ID_HANDLER_A + i, PRIORITY_HANDLER)
                         for i in range(2)]
        self.devices = [TaskControlBlock(ID_DEVICE_A + i, PRIORITY_DEVICE)
                        for i in range(4)]
        self.tasks += self.handlers + self.devices
        for task in self.tasks:
            task.scheduler = self
        for i, device in enumerate(self.devices):
            for j in range(packets):
                device.add_input(Packet((i * packets + j) & 255, 0))
        tail = None
        for i in range(packets):
            packet = Packet(i & 255, 0)
            if tail is None:
                self.worker.queue = packet
            else:
                tail.link = packet
            tail = packet
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
        for task in self.devices + self.handlers:
            if task.queue is not None:
                return True
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


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 250000
    scheduler = Scheduler(n)
    for task in scheduler.tasks:
        scheduler.release(task)
    scheduler.run()
    handled = 0
    for handler in scheduler.handlers:
        handled += handler.handled
    print("richards %d %d %d %d" % (handled, scheduler.queue_count,
                                    scheduler.hold_count, scheduler.checksum))


main()
