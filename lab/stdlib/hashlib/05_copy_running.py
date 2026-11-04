import hashlib


def main() -> None:
    running = hashlib.sha256()
    running.update(b"header\n")
    snapshots = []
    running.update(b"alpha\n")
    snapshots.append(running.copy().hexdigest())
    running.update(b"beta\n")
    snapshots.append(running.copy().hexdigest())
    running.update(b"gamma\n")
    snapshots.append(running.copy().hexdigest())
    for item in snapshots:
        print(item)
    print("final", running.hexdigest())
    print("copy independent", snapshots[0] != running.hexdigest())


main()
