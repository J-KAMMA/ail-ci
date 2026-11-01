import heapq


class Task:
    def __init__(self, priority, name):
        self.priority = priority
        self.name = name

    def __lt__(self, other):
        return (self.priority, self.name) < (other.priority, other.name)


def describe(task):
    return str(task.priority) + ":" + task.name


def main():
    tasks = [
        Task(3, "write report"),
        Task(1, "answer mail"),
        Task(2, "review patch"),
        Task(1, "call back"),
    ]
    heapq.heapify(tasks)
    print("ready", describe(tasks[0]), len(tasks))
    while tasks:
        task = heapq.heappop(tasks)
        print("run", describe(task))
    try:
        heapq.heappop(tasks)
    except IndexError as exc:
        print("empty", type(exc).__name__, exc)


main()
