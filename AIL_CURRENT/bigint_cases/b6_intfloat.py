class T:
    def __init__(self):
        self.n = 0
        self.done = True
        self.todo = False
def main():
    t = T()
    t.n = int(3.7)
    print(t.n)
    print(int(t.done))
    print(int(t.todo))
    print(t.done + 1)
    print(int(-3.7))
    print(int(True), int(False))
main()
