from array import array


def main():
    samples = array('f')
    samples.extend([1.5, -2.25, 0.0])
    samples.append(3.75)
    print(samples, samples.typecode, samples.itemsize)
    print(len(samples), sum(samples), min(samples), max(samples))
    print(samples[1:3])
    samples.reverse()
    print(samples.tolist())
    try:
        samples.append("wide")
    except TypeError as exc:
        print("TypeError", exc)


main()
