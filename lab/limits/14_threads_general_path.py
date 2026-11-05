import threading


def work(n):
    print(n)


t = threading.Thread(target=work, args=(5,))
t.start()
t.join()
