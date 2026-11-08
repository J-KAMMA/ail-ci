def main():
    d = {}
    d['a'] = set()
    d['a'].add(3)
    v = d['a']
    v.add(4)
    print(sorted(d['a']), len(v))
main()
