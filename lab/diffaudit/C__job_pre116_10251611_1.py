# C?-job-pre116-10251611-1: an allowed saved generator is eager when its body calls next().
def main():
    g = None
    try:
        g = (next(iter([])) for _ in range(1))
        print("made")
    except Exception as e:
        print("early", type(e).__name__)
    if g is not None:
        try:
            next(g)
        except Exception as e:
            print("late", type(e).__name__)

main()
