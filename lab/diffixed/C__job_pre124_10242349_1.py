# C?-job-pre124-10242349-1: module-scope annotations are evaluated
events = []

def ann():
    events.append("ann")
    return "ann"

class Box:
    def __init__(self):
        self.x = 0

b = Box()
b.x: ann()
print(b.x, events)
xs = [0]
state = [0]

def touch(n):
    state[0] = n
    return n

xs[touch(0)]: ann()
print(state[0], events)
y: ann() = 5
print(y, events)
z = []
z.append(1)
print(z, events)
