import heapq


class MedianFinder:
    def __init__(self):
        self.lower = []
        self.upper = []

    def add(self, value):
        if not self.lower or value <= -self.lower[0]:
            heapq.heappush(self.lower, -value)
        else:
            heapq.heappush(self.upper, value)
        if len(self.lower) > len(self.upper) + 1:
            heapq.heappush(self.upper, -heapq.heappop(self.lower))
        elif len(self.upper) > len(self.lower):
            heapq.heappush(self.lower, -heapq.heappop(self.upper))

    def median(self):
        if len(self.lower) == len(self.upper):
            return (-self.lower[0] + self.upper[0]) / 2
        return float(-self.lower[0])


def main():
    finder = MedianFinder()
    for value in [5, 15, 1, 3, 8, 7, 9, 10, 2]:
        finder.add(value)
        print(value, finder.median())
    print("sizes", len(finder.lower), len(finder.upper))
    print("roots", -finder.lower[0], finder.upper[0])


main()
