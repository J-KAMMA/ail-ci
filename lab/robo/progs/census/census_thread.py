"""Census probe: threads. The link for bare metal should fail on pthread_*. """

import threading


def worker(x: int) -> None:
    print("worker", x)


def main() -> None:
    t = threading.Thread(target=worker, args=(1,))
    t.start()
    t.join()
    print("threads done")


main()
