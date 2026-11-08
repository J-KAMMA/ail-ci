d = {}
d['a'] = [1, 2]
for k in ['a']:
    v = d[k]
    v[0] = v[1]
    print(v)
