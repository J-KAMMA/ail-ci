def main():
    acc = {}
    for k in ['alice', 'bob']:
        acc[k] = [k, 100, True]
    r = acc['alice']
    r[1] -= 30
    acc['bob'][1] += 5
    print(acc['alice'][0], acc['alice'][1], acc['alice'][2])
    print(acc['bob'][0], acc['bob'][1], acc['bob'][2])
    print(acc['alice'])


main()
