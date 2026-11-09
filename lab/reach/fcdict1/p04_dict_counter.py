def main():
    d = {'a': {'n': 0}, 'b': {'n': 0}}
    d['a']['n'] += 1
    d['b']['n'] += 2
    print(d['a']['n'], d['b']['n'])


main()
