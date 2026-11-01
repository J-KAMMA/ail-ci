import heapq


class PriorityQueue:
    def __init__(self):
        self.items = []

    def push(self, item):
        heapq.heappush(self.items, item)

    def pop(self):
        return heapq.heappop(self.items)

    def peek(self):
        if not self.items:
            return None
        return self.items[0]

    def replace(self, item):
        return heapq.heapreplace(self.items, item)

    def pushpop(self, item):
        return heapq.heappushpop(self.items, item)

    def __len__(self):
        return len(self.items)


def main():
    queue = PriorityQueue()
    for value in [7, 2, 9, 4]:
        queue.push(value)
    print("size", len(queue), "first", queue.peek())
    print("pop", queue.pop(), queue.pop())
    print("pushpop", queue.pushpop(1), "first", queue.peek())
    print("replace", queue.replace(0), "first", queue.peek())
    print("rest", queue.pop(), queue.pop())
    try:
        queue.replace(5)
    except IndexError as exc:
        print("empty", type(exc).__name__, exc)
    print("pushpop", queue.pushpop(8), queue.items)


main()
