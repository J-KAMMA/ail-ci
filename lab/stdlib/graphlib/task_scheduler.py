from graphlib import TopologicalSorter


tasks = {
    "fetch": [],
    "parse": ["fetch"],
    "validate": ["parse"],
    "load": ["validate"],
    "report": ["load"],
    "archive": ["fetch"],
    "cleanup": ["report", "archive"],
}

sorter = TopologicalSorter(tasks)
sorter.prepare()
completed = []
rounds = 0

while sorter.is_active():
    batch = sorter.get_ready()
    rounds += 1
    print("round", rounds, "start:", batch)
    for task in batch:
        completed.append(task)
        sorter.done(task)

print("completed:", completed)
print("total:", len(completed))
print("rounds:", rounds)
print("unique:", len(set(completed)))
