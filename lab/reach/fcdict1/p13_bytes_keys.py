def main():
    d = {}
    d[b'a'] = [1, 2, True]
    v = d[b'a']
    v[1] = 5
    print(d[b'a'])
    print(len(d))


main()
