def main():
    d = {}
    d['a'] = {}
    d['a']['x'] = 1
    v = d['a']
    v['y'] = 2
    print(d['a']['x'], d['a']['y'], len(v))
main()
