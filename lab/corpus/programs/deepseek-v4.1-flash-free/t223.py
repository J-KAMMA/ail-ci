import sys
from collections import deque


def main() -> None:
    data = sys.stdin.buffer.read().split()
    if not data:
        return
    h = int(data[0])
    w = int(data[1])
    grid = [row.decode() for row in data[2:2 + h]]

    visited = bytearray(h * w)
    components = 0
    largest = 0

    for start in range(h * w):
        if visited[start]:
            continue
        r0, c0 = divmod(start, w)
        if grid[r0][c0] == "#":
            visited[start] = 1
            continue

        components += 1
        visited[start] = 1
        size = 0
        queue = deque([start])
        while queue:
            pos = queue.popleft()
            size += 1
            r, c = divmod(pos, w)
            if r > 0:
                n = pos - w
                if not visited[n] and grid[r - 1][c] != "#":
                    visited[n] = 1
                    queue.append(n)
            if r + 1 < h:
                n = pos + w
                if not visited[n] and grid[r + 1][c] != "#":
                    visited[n] = 1
                    queue.append(n)
            if c > 0:
                n = pos - 1
                if not visited[n] and grid[r][c - 1] != "#":
                    visited[n] = 1
                    queue.append(n)
            if c + 1 < w:
                n = pos + 1
                if not visited[n] and grid[r][c + 1] != "#":
                    visited[n] = 1
                    queue.append(n)

        if size > largest:
            largest = size

    print(components, largest)


if __name__ == "__main__":
    main()
