from array import array


def main():
    size = 5
    buf = array('i', [0]) * size
    print(buf, len(buf))
    for i in range(8):
        buf[i % size] = (i + 1) * 10
        print(i, buf.tolist())
    print(sum(buf), max(buf))
    print(2 * buf)
    print(buf * 2)
    buf += array('i', [1, 2])
    print(buf, len(buf))
    buf *= 2
    print(len(buf), buf[:4])
    snapshot = buf[:]
    snapshot[0] = -1
    print(buf[0], snapshot[0])


main()
