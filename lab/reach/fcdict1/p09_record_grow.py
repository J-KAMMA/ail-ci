def main():
    d = {}
    d['a'] = [1, 2]
    v = d['a']
    v.append(3)
    print(d['a'], len(v))
main()
