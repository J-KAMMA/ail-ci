from array import array


def main():
    frames = array('h')
    frames.extend([100, -200, 300, -400])
    frames.append(500)
    print(frames, len(frames), frames.itemsize)
    print(frames[1:4], frames[::-2])
    print(min(frames), max(frames), sum(frames))
    frames.remove(-200)
    popped = frames.pop()
    frames.insert(0, 42)
    print(frames.tolist(), popped)
    swapped = array('h', frames)
    swapped.byteswap()
    print(swapped.tolist())
    swapped.byteswap()
    print(swapped == frames, swapped.tolist())
    print(frames.count(300), frames.index(300))


main()
