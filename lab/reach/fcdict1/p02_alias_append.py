def main():
    d = {}
    d['a'] = [1]
    v = d['a']
    v.append(9)
    print(d['a'])
    print(v)


main()
