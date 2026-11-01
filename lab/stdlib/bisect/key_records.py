import bisect


def main():
    tasks = [(3, "write"), (1, "plan"), (2, "test"), (2, "review")]
    tasks.sort()
    keys = [task[0] for task in tasks]
    print("keys", keys)
    print(bisect.bisect_left(keys, 2), bisect.bisect_right(keys, 2))
    print("keyed", bisect.bisect_left(tasks, 2, key=lambda task: task[0]))
    print("keyed", bisect.bisect_right(tasks, 2, key=lambda task: task[0]))
    tasks.append((2, "deploy"))
    tasks.sort()
    print(tasks)
    bisect.insort(tasks, (2, "build"), key=lambda task: task[0])
    print(tasks)
    print(bisect.bisect_left(tasks, (2, "deploy")))
    print(bisect.bisect_right(tasks, (2, "z")))


main()
