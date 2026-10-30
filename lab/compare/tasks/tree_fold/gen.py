"""Cases for tree_fold (see spec.md). cases(rng) -> (public, hidden, perf). Input on standard input."""

STDIN = True

NAMES = ['a', 'b', 'root', 'left', 'right', 'mid', 'x', 'y', 'leaf', 'node', 'ab', 'abc', 'zz', 'qqqqqqqqqqqqqqqq']


def serialize(names, weights, kids):
    parts = []
    stack = [0]
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            parts.append(item)
            continue
        parts.append('%s:%d' % (names[item], weights[item]))
        ch = kids[item]
        if ch:
            parts.append('[')
            stack.append(']')
            for i in range(len(ch) - 1, -1, -1):
                stack.append(ch[i])
                if i > 0:
                    stack.append(' ')
    return ''.join(parts)


def random_tree(rng, n, names=NAMES, chain=0.3, maxw=1000, max_depth=4999):
    nm = [rng.choice(names)]
    wt = [rng.randrange(0, maxw + 1)]
    kids = [[]]
    depth = [0]
    for i in range(1, n):
        if rng.random() < chain:
            p = i - 1
        else:
            p = rng.randrange(0, i)
        if depth[p] >= max_depth:
            p = 0
        nm.append(rng.choice(names))
        wt.append(rng.randrange(0, maxw + 1) if rng.random() < 0.95 else rng.randrange(0, 1000001))
        kids.append([])
        depth.append(depth[p] + 1)
        kids[p].append(i)
    return serialize(nm, wt, kids)


def doc(tree, *ops, final=True):
    return ('\n'.join((tree,) + ops) + ('\n' if final else '')).encode()


def random_ops(rng, k):
    ops = []
    for _ in range(k):
        r = rng.randrange(10)
        if r == 0:
            ops.append('total')
        elif r == 1:
            ops.append('stats')
        elif r == 2:
            ops.append('level %d' % rng.randrange(0, 6))
        elif r == 3:
            ops.append('find %s' % rng.choice(NAMES + ['a+b', 'nope', 'x+y']))
        elif r == 4:
            ops.append('print')
        elif r == 5:
            ops.append('prune %d' % rng.randrange(0, 300))
        elif r == 6:
            ops.append('sort')
        elif r == 7:
            ops.append('mirror')
        elif r == 8:
            ops.append('fold')
        else:
            ops.append('cut %s' % rng.choice(NAMES))
    return ops


EX = 'top:5[left:3 mid:0[x:1 y:1] right:2[solo:4[deep:1]]]'
ALL = ['total', 'stats', 'level 1', 'level 2', 'find x', 'find deep', 'print']


def cases(rng):
    public = [
        ('example', doc(EX, *ALL, 'sort', 'print', 'fold', 'print', 'find solo+deep', 'stats'), []),
        ('prune_cut', doc(EX, 'prune 3', 'print', 'cut mid', 'print', 'mirror', 'print', 'total'), []),
        ('malformed', doc('top:5[left:3 mid:0[]]', 'total'), []),
    ]
    chain = 'a:1[b:2[c:3[d:4]]]'
    hidden = [
        ('tree_only', doc(EX), []),
        ('single_node', doc('solo:7', 'total', 'stats', 'level 0', 'level 1', 'fold', 'prune 100', 'cut solo', 'print',
                            'find solo', 'find x', 'sort', 'mirror', 'print'), []),
        ('root_chain_fold', doc(chain, 'fold', 'print', 'stats'), []),
        ('fold_two_chains', doc('r:0[a:1[b:1[c:1[d:1 e:1]]] f:2[g:2] h:3]', 'fold', 'print', 'fold', 'print', 'find a+b+c'), []),
        ('fold_root_single_child', doc('r:1[a:1]', 'fold', 'print', 'cut a', 'print'), []),
        ('fold_then_cut_then_fold', doc('r:0[a:1[b:2[c:3 d:4]] e:5]', 'cut c', 'print', 'fold', 'print', 'cut a+b+d', 'print',
                                         'fold', 'print'), []),
        ('fold_names_with_plus', doc('r:0[a:1[b:1] c:1[d:1[e:1]] f:0]', 'fold', 'print', 'cut f', 'fold', 'print', 'stats'), []),
        ('sort_ties', doc('r:0[b:5 a:5 ab:5 a:5[x:0] c:6 aa:4[z:1] a:5]', 'sort', 'print', 'mirror', 'sort', 'print'), []),
        ('sort_prefix_names', doc('r:0[abc:1 ab:1 abcd:1 a:1 b:0[c:1]]', 'sort', 'print'), []),
        ('prune_boundary', doc('r:1[a:2 b:3[c:0] d:1[e:1 f:1] g:0]', 'prune 3', 'print', 'prune 4', 'print', 'prune 0', 'print'), []),
        ('prune_root_kept', doc('r:0[a:1]', 'prune 1000000000000000', 'print', 'stats', 'total'), []),
        ('prune_uses_old_sums', doc('r:0[a:0[b:5 c:1] d:2]', 'prune 2', 'print'), []),
        ('cut_root', doc('r:1[r:2 x:3]', 'cut r', 'print', 'cut r', 'print', 'cut r', 'print'), []),
        ('cut_missing', doc(EX, 'cut nothere', 'print'), []),
        ('cut_leaf_and_inner', doc(EX, 'cut y', 'print', 'cut solo', 'print', 'cut right', 'print', 'stats'), []),
        ('find_preorder_first', doc('r:0[a:0[k:1] k:2[k:3]]', 'find k', 'mirror', 'find k', 'find r', 'find kk'), []),
        ('levels', doc(EX, 'level 0', 'level 1', 'level 2', 'level 3', 'level 4', 'level 1000000000000000'), []),
        ('big_weights', doc('r:1000000[a:1000000 b:1000000[c:1000000]]', 'total', 'level 1', 'fold', 'print'), []),
        ('max_name', doc('qqqqqqqqqqqqqqqq:1[aaaaaaaaaaaaaaaa:2]', 'print', 'find qqqqqqqqqqqqqqqq'), []),
        ('no_final_newline', doc(EX, 'total', 'stats', final=False), []),
        ('deep_chain', doc('n:1[' * 4999 + 'n:1' + ']' * 4999, 'stats', 'total', 'level 4999', 'fold', 'stats', 'level 1'), []),
        ('wide', doc('r:0[' + ' '.join('k:%d' % i for i in range(5000)) + ']', 'stats', 'sort', 'level 1', 'prune 4990', 'print'), []),
        # malformed
        ('empty_input', b'', []),
        ('empty_line_op', doc(EX, 'total', '', 'stats'), []),
        ('trailing_blank_line', doc(EX, 'total') + b'\n', []),
        ('crlf', doc(EX, 'total').replace(b'\n', b'\r\n'), []),
        ('name_too_long', doc('aaaaaaaaaaaaaaaaa:1', 'total'), []),
        ('name_uppercase', doc('Top:1', 'total'), []),
        ('weight_leading_zero', doc('a:01', 'total'), []),
        ('weight_too_big', doc('a:1000001', 'total'), []),
        ('weight_missing', doc('a:', 'total'), []),
        ('two_spaces', doc('a:1[b:1  c:1]', 'total'), []),
        ('space_after_bracket', doc('a:1[ b:1]', 'total'), []),
        ('unclosed', doc('a:1[b:1', 'total'), []),
        ('extra_close', doc('a:1[b:1]]', 'total'), []),
        ('two_roots', doc('a:1 b:1', 'total'), []),
        ('unknown_op', doc(EX, 'sum'), []),
        ('op_missing_arg', doc(EX, 'level'), []),
        ('op_extra_arg', doc(EX, 'total 1'), []),
        ('op_bad_number', doc(EX, 'prune 07'), []),
        ('op_number_too_big', doc(EX, 'level 1000000000000001'), []),
        ('op_trailing_space', doc(EX, 'stats '), []),
        ('find_bad_name', doc(EX, 'find X'), []),
        ('error_after_output_ops', doc(EX, 'total', 'print', 'bogus'), []),
    ]
    for k in range(8):
        tree = random_tree(rng, rng.randrange(1, 60), chain=rng.choice([0.2, 0.5, 0.8]), maxw=rng.choice([5, 100]))
        hidden.append(('random%d' % k, doc(tree, *random_ops(rng, rng.randrange(1, 14))), []))
    big = random_tree(rng, 3000000, chain=0.35)
    perf_ops = ['stats', 'total', 'level 6', 'find leaf', 'sort', 'find qqqqqqqqqqqqqqqq', 'prune 40', 'stats', 'fold', 'stats',
                'cut mid', 'mirror', 'level 3', 'find x+y', 'sort', 'stats', 'print']
    perf = ('perf', doc(big, *perf_ops), [])
    return public, hidden, perf
