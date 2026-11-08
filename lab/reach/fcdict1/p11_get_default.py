def main():
    d = {}
    d['a'] = [10, 20]
    x = d.get('zz', [0, 0])
    x[0] += 1
    print(x, len(d), 'zz' in d)
main()
