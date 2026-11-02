from array import array


def mean(values):
    return sum(values) / len(values)


def main():
    readings = array('d')
    for x in (12.5, 13.0, 11.5, 14.25, 15.0):
        readings.append(x)
    readings.extend([9.5, 10.0])
    print(readings)
    print(len(readings), readings.typecode, readings.itemsize)
    print(readings[0], readings[-1], readings[2:5])
    print(round(mean(readings), 4), min(readings), max(readings))
    readings.reverse()
    print(readings.tolist())
    print(sum(readings[:3]))


main()
