def main():
    d = {}
    d['a'] = [1, 2]
    v = d['a']
    v[0] = v[1]
    print(v)
main()
