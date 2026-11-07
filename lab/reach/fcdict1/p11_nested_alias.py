def main():
    d = {}
    d['a'] = [1, 2]
    e = {}
    e['x'] = d
    v = e['x']['a']
    v.append(3)
    print(d['a'])
    e['x']['a'].append(4)
    print(v)


main()
