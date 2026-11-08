def main():
    d = {}
    d.setdefault('a', {}).setdefault('x', 0)
    d['a']['x'] += 1
    d['a']['y'] = 5
    d.setdefault('b', {})['z'] = 7
    print(d['a']['x'], d['a']['y'], d['b']['z'], len(d))
main()
