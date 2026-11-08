"""Stage 1 / stage 2 self-test for ailast: 40 fixed trees, built by hand.

    PYTHONPATH=selfhost/src python3 selfhost/drv/ast_selftest.py   (stage 1)
    AIL_PATH=selfhost/src python3 -B AIL_CURRENT/ail_chatgpt.py compile selfhost/drv/ast_selftest.py -o ast_selftest
    ./ast_selftest                                                  (stage 2)

For each tree it prints ``== N``, the default dump, the dump with attributes, the class names in
``walk`` order, and the class names in ``iter_child_nodes`` order.  Stage 2 must print exactly what
stage 1 prints.
"""
from ailast import (
    AST, Module,
    Expr, Constant, Name, Load, Store, Del, BinOp, UnaryOp, BoolOp, Compare, Call, Attribute,
    Subscript, Slice, List, Tuple, Set, Dict, ListComp, SetComp, DictComp, GeneratorExp,
    JoinedStr, FormattedValue, Starred, NamedExpr, IfExp, Lambda, Yield, YieldFrom,
    Add, Sub, Mult, Div, FloorDiv, Mod, Pow, LShift, RShift, BitOr, BitXor, BitAnd, MatMult,
    And, Or, Not, Invert, UAdd, USub,
    Eq, NotEq, Lt, LtE, Gt, GtE, Is, IsNot, In, NotIn,
    Assign, AugAssign, AnnAssign, Return, Delete, Pass, Break, Continue, Global, Nonlocal,
    If, While, For, With, withitem, Try, ExceptHandler, Raise, Assert, Import, ImportFrom,
    alias, FunctionDef, ClassDef, arg, arguments, keyword, comprehension,
    dump, walk, iter_child_nodes,
)


def nm(s, ctx, ln, col):
    return Name(s, ctx, ln, col, ln, col + 1)


def cs(v, ln, col):
    return Constant(v, None, ln, col, ln, col + 1)


def ex(v, ln, col):
    return Expr(v, ln, col, ln, col + 1)


def ld(s, ln, col):
    return nm(s, Load(), ln, col)


def st(s, ln, col):
    return nm(s, Store(), ln, col)


def bi(left, op, right, ln, col):
    return BinOp(left, op, right, ln, col, ln, col + 1)


def un(op, operand, ln, col):
    return UnaryOp(op, operand, ln, col, ln, col + 1)


def ca(func, args, kws, ln, col):
    return Call(func, args, kws, ln, col, ln, col + 1)


def kw(s, value, ln, col):
    return keyword(s, value, ln, col, ln, col + 1)


def al(s, asname, ln, col):
    return alias(s, asname, ln, col, ln, col + 1)


def ar(s, ann, ln, col):
    return arg(s, ann, None, ln, col, ln, col + 1)


def args(posonly, normal, vararg, kwonly, kwdefs, kwarg):
    return arguments(posonly, normal, vararg, kwonly, kwdefs, kwarg, [])


def comp(target, it, ifs, is_async):
    return comprehension(target, it, ifs, is_async)


def wi(ctxexpr, opt):
    return withitem(ctxexpr, opt)


def eh(t, s, body, ln, col):
    return ExceptHandler(t, s, body, ln, col, ln, col + 1)


def tree1():
    no_end = Expr(Name("n", Load(), 2, 0), 2, 0)
    return Module([ex(cs(1, 1, 0), 1, 0), no_end], [])


def tree2():
    return Module([ex(cs(0.1, 1, 0), 1, 0)], [])


def tree3():
    return Module([ex(cs(1e16, 1, 0), 1, 0)], [])


def tree4():
    return Module([ex(cs(1e-7, 1, 0), 1, 0)], [])


def tree5():
    return Module([ex(cs(float("inf"), 1, 0), 1, 0)], [])


def tree6():
    return Module([ex(cs(-float("inf"), 1, 0), 1, 0)], [])


def tree7():
    return Module([ex(cs(-0.0, 1, 0), 1, 0)], [])


def tree8():
    return Module([ex(cs("h\u00e9llo \u65e5\u672c", 1, 0), 1, 0)], [])


def tree9():
    return Module([ex(cs("a'b\"c\\n", 1, 0), 1, 0)], [])


def tree10():
    return Module([ex(cs(b"\x00b\xff", 1, 0), 1, 0)], [])


def tree11():
    return Module([ex(cs(True, 1, 0), 1, 0), ex(cs(False, 2, 0), 2, 0), ex(cs(None, 3, 0), 3, 0)], [])


def tree12():
    return Module([ex(bi(cs(1, 1, 0), Add(), cs(2, 1, 4), 1, 0), 1, 0)], [])


def tree13():
    return Module([ex(bi(bi(cs(2, 1, 0), Mult(), cs(3, 1, 4), 1, 0), Sub(), cs(4, 1, 10), 1, 0), 1, 0)], [])


def tree14():
    return Module([ex(un(USub(), cs(5, 1, 1), 1, 0), 1, 0)], [])


def tree15():
    return Module([ex(BoolOp(And(), [ld("a", 1, 0), ld("b", 1, 5), ld("c", 1, 10)], 1, 0), 1, 0)], [])


def tree16():
    return Module([ex(Compare(ld("a", 1, 0), [Lt(), NotEq()], [cs(1, 1, 4), cs(2, 1, 9)], 1, 0), 1, 0)], [])


def tree17():
    return Module([ex(ca(ld("f", 1, 0), [cs(1, 1, 2), ld("x", 1, 5)], [kw("k", cs(2, 1, 10), 1, 9)], 1, 0), 1, 0)], [])


def tree18():
    return Module([ex(Attribute(ld("x", 1, 0), "y", Load(), 1, 0, 1, 3), 1, 0)], [])


def tree19():
    sl = Slice(cs(1, 1, 4), cs(5, 1, 6), cs(2, 1, 8), 1, 4, 1, 10)
    return Module([ex(Subscript(ld("a", 1, 0), sl, Load(), 1, 0, 1, 11), 1, 0)], [])


def tree20():
    return Module([Assign([st("a", 1, 0)], List([cs(1, 1, 4), cs(2, 1, 7)], Store(), 1, 3, 1, 9), None, 1, 0, 1, 9)], [])


def tree21():
    return Module([ex(Tuple([cs(1, 1, 1), ld("x", 1, 4)], Load(), 1, 0, 1, 6), 1, 0)], [])


def tree22():
    return Module([ex(Set([cs(1, 1, 1), cs(2, 1, 4)], 1, 0, 1, 6), 1, 0)], [])


def tree23():
    return Module([ex(Dict([cs("a", 1, 1), None], [cs(1, 1, 6), cs(2, 1, 9)], 1, 0, 1, 11), 1, 0)], [])


def tree24():
    return Module([Assign([st("x", 1, 0)], cs(1, 1, 4), "int", 1, 0, 1, 5)], [])


def tree25():
    return Module([AugAssign(st("x", 1, 0), Add(), cs(1, 1, 5), 1, 0, 1, 6)], [])


def tree26():
    return Module([AnnAssign(st("x", 1, 0), ld("int", 1, 3), None, 1, 1, 0, 1, 6)], [])


def tree27():
    return Module([If(ld("a", 1, 0), [ex(cs(1, 2, 4), 2, 4), Continue(3, 4, 3, 12)], [Pass(4, 0, 4, 8)], 1, 0, 4, 8)], [])


def tree28():
    return Module([While(ld("a", 1, 0), [Break(2, 4, 2, 9)], [ex(cs(0, 3, 4), 3, 4)], 1, 0, 3, 8)], [])


def tree29():
    return Module([For(st("i", 1, 0), ca(ld("range", 1, 9), [cs(3, 1, 15)], [], 1, 9), [ex(ld("i", 2, 4), 2, 4)], [Pass(3, 0, 3, 8)], "int", 1, 0, 3, 8)], [])


def tree30():
    a = args([], [ar("x", ld("int", 1, 7), 1, 6), ar("y", None, 1, 12)], ar("rest", None, 1, 17),
             [ar("k", None, 1, 25)], [cs(1, 1, 30), None], ar("kw", None, 1, 35))
    return Module([FunctionDef("f", a, [Return(ld("x", 2, 4), 2, 4, 2, 11)], [ld("deco", 1, 0)], ld("int", 1, 50), "c", [], 1, 0, 2, 11)], [])


def tree31():
    a = args([], [ar("z", None, 1, 6)], None, [], [], None)
    return Module([Assign([st("g", 1, 0)], Lambda(a, bi(ld("z", 1, 13), Add(), cs(1, 1, 17), 1, 13), 1, 9, 1, 18), None, 1, 0, 1, 18)], [])


def tree32():
    return Module([FunctionDef("f", args([], [], None, [], [], None), [Return(None, 2, 4, 2, 10), Yield(None, 3, 4, 3, 9), YieldFrom(ld("it", 4, 4), 4, 4, 4, 13)], [], None, None, [], 1, 0, 4, 13)], [])


def tree33():
    return Module([ClassDef("C", [ld("Base", 1, 9)], [kw("metaclass", ld("M", 1, 20), 1, 18)], [Pass(2, 4, 2, 8)], [], [], 1, 0, 2, 8)], [])


def tree34():
    body = [ex(ca(ld("f", 2, 4), [], [], 2, 4), 2, 4)]
    return Module([Try(body, [eh(None, None, [Pass(3, 4, 3, 8)], 3, 0), eh(ld("E", 4, 0), "e", [Raise(None, None, 5, 4, 5, 9)], 4, 0)], [Pass(6, 0, 6, 8)], [Pass(7, 0, 7, 8)], 1, 0, 7, 8)], [])


def tree35():
    return Module([With([wi(ca(ld("open", 1, 5), [cs("f", 1, 10)], [], 1, 5), None),
                         wi(ld("lock", 1, 20), st("l", 1, 26))],
                        [Pass(2, 4, 2, 8)], None, 1, 0, 2, 8)], [])


def tree36():
    return Module([Import([al("os", None, 1, 0), al("sys", "s", 1, 0)], 1, 0),
                   ImportFrom("os.path", [al("join", None, 2, 0), al("sep", "sp", 2, 0)], 0, 1, 0, 2, 15)], [])


def tree37():
    return Module([Global(["a", "b"], 1, 0), Nonlocal(["c"], 2, 0), Delete([st("a", 3, 0), Subscript(ld("d", 3, 4), cs("k", 3, 6), Del(), 3, 4, 3, 9)], 3, 0, 3, 10)], [])


def tree38():
    g1 = comp(st("x", 1, 12), ld("xs", 1, 17), [Compare(ld("x", 1, 24), [Gt()], [cs(0, 1, 26)], 1, 24)], 0)
    g2 = comp(st("y", 1, 40), ca(ld("f", 1, 45), [ld("x", 1, 47)], [], 1, 45), [], 1)
    g3 = comp(st("k", 1, 60), ld("d", 1, 65), [], 0)
    return Module([ex(ListComp(bi(ld("x", 2, 4), Mult(), cs(2, 2, 8), 2, 4), [g1], 1, 0, 2, 9), 1, 0),
                   ex(SetComp(ld("y", 2, 4), [g2], 1, 0, 2, 5), 1, 0),
                   ex(DictComp(ld("k", 2, 4), ld("v", 2, 9), [g3], 1, 0, 2, 10), 1, 0),
                   ex(GeneratorExp(ld("x", 2, 4), [g1], 1, 0, 2, 5), 1, 0)], [])


def tree39():
    fv1 = FormattedValue(ld("x", 1, 3), -1, None, 1, 3, 1, 4)
    fv2 = FormattedValue(ld("y", 1, 8), 114, cs(">5", 1, 12), 1, 8, 1, 18)
    js = JoinedStr([cs("v=", 1, 2), fv1, cs(" ", 1, 6), fv2], 1, 1, 1, 19)
    return Module([ex(js, 1, 0), ex(IfExp(ld("a", 2, 0), cs(1, 2, 5), cs(2, 2, 10), 2, 0), 2, 0),
                   ex(NamedExpr(st("n", 3, 1), cs(1, 3, 6), 3, 0), 3, 0),
                   ex(Starred(ld("ys", 4, 1), Load(), 4, 0, 4, 3), 4, 0)], [])


def tree40():
    a = args([], [ar("x", None, 1, 6)], None, [ar("k", None, 1, 12)], [cs(3, 1, 16), None], ar("kw", None, 1, 20))
    inner = Lambda(args([], [], None, [], [], None), bi(ld("x", 2, 18), Add(), cs(1, 2, 22), 2, 18), 1, 14, 2, 23)
    body = [Return(IfExp(ld("c", 2, 11), inner, cs(0, 2, 30), 2, 11), 2, 4, 2, 31)]
    return Module([FunctionDef("f", a, body, [ld("wrap", 1, 0)], ld("int", 1, 40), "t", [], 1, 0, 2, 31)], [])


def build():
    return [tree1(), tree2(), tree3(), tree4(), tree5(), tree6(), tree7(), tree8(), tree9(),
            tree10(), tree11(), tree12(), tree13(), tree14(), tree15(), tree16(), tree17(),
            tree18(), tree19(), tree20(), tree21(), tree22(), tree23(), tree24(), tree25(),
            tree26(), tree27(), tree28(), tree29(), tree30(), tree31(), tree32(), tree33(),
            tree34(), tree35(), tree36(), tree37(), tree38(), tree39(), tree40()]


def names(nodes):
    text = ""
    for n in nodes:
        text = text + n._typename + " "
    return text


def main():
    trees = build()
    i = 0
    while i < len(trees):
        t = trees[i]
        print("== " + str(i))
        print(dump(t))
        print(dump(t, True, True))
        print("walk " + names(walk(t)))
        print("child " + names(iter_child_nodes(t)))
        i += 1


main()
