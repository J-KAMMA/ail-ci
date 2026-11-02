from collections import OrderedDict


class LRU:
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.items: OrderedDict[str, int] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> int:
        if key in self.items:
            self.hits += 1
            value = self.items[key]
            self.items.move_to_end(key)
            return value
        self.misses += 1
        return -1

    def put(self, key: str, value: int) -> None:
        if key in self.items:
            self.items.move_to_end(key)
        self.items[key] = value
        if len(self.items) > self.capacity:
            old, _ = self.items.popitem(last=False)
            print("evict", old)

    def dump(self) -> None:
        for key in self.items:
            print(key, self.items[key])


def main() -> int:
    cache = LRU(3)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)
    print(cache.get("a"))
    cache.put("d", 4)
    cache.put("b", 20)
    cache.dump()
    print(cache.hits, cache.misses)
    print(cache.get("zz"), cache.get("b"))
    cache.put("e", 5)
    cache.dump()
    print(cache.items.pop("e"))
    print(len(cache.items))
    cache.items.setdefault("f", 6)
    cache.items.setdefault("a", 99)
    print(cache.items.get("f"), cache.items.get("q", -1))
    cache.items.move_to_end("a", last=False)
    cache.dump()
    last, value = cache.items.popitem()
    print(last, value)
    empty: OrderedDict[str, int] = OrderedDict()
    print(empty, len(empty))
    return 0


main()
