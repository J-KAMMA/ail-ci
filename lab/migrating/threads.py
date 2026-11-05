import threading

def work() -> None:
    print("thread ran")

t = threading.Thread(target=work)
t.start()
t.join()
