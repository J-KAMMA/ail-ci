import std/[os, tables, strutils]

type
  PErr = object of CatchableError
  RErr = object of CatchableError

  TK = enum tNum, tWord, tOp
  Tok = object
    k: TK
    s: string
    v: uint32

  Ex = ref object
    op: char       # 'n' num, 'v' var, 'M' max, 'm' min, '=' '!'(!=) '<' '>', + - * / %, '~', 'N' neg, '#', 'L' not
    val: uint32
    a, b: Ex
    line: int

  SK = enum sSet, sOut, sLoop, sWhen
  Stmt = ref object
    k: SK
    line: int
    v: int
    exs: seq[Ex]
    body, els: seq[Stmt]
    hasElse: bool
    isBreak: bool

const keywords = ["set", "out", "loop", "when", "else", "end", "break"]

var
  varIdx = initTable[string, int]()
  vals: seq[uint32]
  assigned: seq[bool]
  outBuf = ""

proc perr() {.noreturn.} = raise newException(PErr, "p")

proc tokenize(s: string): seq[Tok] =
  var i = 0
  let n = s.len
  while i < n:
    let c = s[i]
    if c in {' ', '\t', '\r'}:
      inc i
    elif c in {'0'..'9'}:
      var v: uint64 = 0
      while i < n and s[i] in {'0'..'9'}:
        v = v * 10 + uint64(ord(s[i]) - 48)
        if v > 4294967295'u64: perr()
        inc i
      if i < n and (s[i] in {'a'..'z'} or s[i] == '_'): perr()
      result.add Tok(k: tNum, v: uint32(v))
    elif c in {'a'..'z'} or c == '_':
      var j = i
      while j < n and (s[j] in {'a'..'z', '0'..'9'} or s[j] == '_'): inc j
      result.add Tok(k: tWord, s: s[i ..< j])
      i = j
    else:
      if i + 1 < n and s[i .. i+1] in ["<>", "><", "==", "!="]:
        result.add Tok(k: tOp, s: s[i .. i+1])
        i += 2
      elif c in {'<', '>', '+', '-', '*', '/', '%', '~', '#', '!', '(', ')', ',', '='}:
        result.add Tok(k: tOp, s: $c)
        inc i
      else:
        perr()

var toks: seq[Tok]
var pos = 0
var depth = 0

proc isOp(s: string): bool =
  pos < toks.len and toks[pos].k == tOp and toks[pos].s == s

proc isKw(w: string): bool =
  w in keywords

proc getVar(name: string): int =
  if name in varIdx: return varIdx[name]
  result = vals.len
  varIdx[name] = result
  vals.add 0
  assigned.add false

proc mk(op: char, a, b: Ex = nil): Ex = Ex(op: op, a: a, b: b)

proc pL1(): Ex

proc pPrimary(): Ex =
  if pos >= toks.len: perr()
  let t = toks[pos]
  case t.k
  of tNum:
    inc pos
    return Ex(op: 'n', val: t.v)
  of tWord:
    if isKw(t.s): perr()
    inc pos
    return Ex(op: 'v', val: uint32(getVar(t.s)))
  of tOp:
    if t.s == "(":
      inc pos
      inc depth
      if depth > 32: perr()
      let e = pL1()
      if not isOp(")"): perr()
      inc pos
      dec depth
      return e
    perr()

proc pL6(): Ex =
  if pos < toks.len and toks[pos].k == tOp:
    let s = toks[pos].s
    if s == "-" or s == "#" or s == "!":
      inc pos
      let e = pL6()
      return mk(if s == "-": 'N' elif s == "#": '#' else: 'L', e)
  return pPrimary()

proc pL5(): Ex =
  let a = pL6()
  if isOp("~"):
    inc pos
    let b = pL5()
    return mk('~', a, b)
  return a

proc pL4(): Ex =
  result = pL5()
  while pos < toks.len and toks[pos].k == tOp and toks[pos].s in ["*", "/", "%"]:
    let c = toks[pos].s[0]
    inc pos
    result = mk(c, result, pL5())

proc pL3(): Ex =
  result = pL4()
  while pos < toks.len and toks[pos].k == tOp and toks[pos].s in ["+", "-"]:
    let c = toks[pos].s[0]
    inc pos
    result = mk(c, result, pL4())

proc pL2(): Ex =
  result = pL3()
  if pos < toks.len and toks[pos].k == tOp and toks[pos].s in ["==", "!=", "<", ">"]:
    let s = toks[pos].s
    inc pos
    let c = if s == "==": '=' elif s == "!=": '!' else: s[0]
    result = mk(c, result, pL3())

proc pL1(): Ex =
  result = pL2()
  while pos < toks.len and toks[pos].k == tOp and toks[pos].s in ["<>", "><"]:
    let c = if toks[pos].s == "<>": 'M' else: 'm'
    inc pos
    result = mk(c, result, pL2())

proc rotl(a: uint32, b: uint32): uint32 =
  let r = b and 31
  if r == 0: a else: (a shl r) or (a shr (32 - r))

proc popc(x: uint32): uint32 =
  var v = x
  var c = 0'u32
  while v != 0:
    v = v and (v - 1)
    inc c
  c

proc ev(e: Ex): uint32 =
  case e.op
  of 'n': e.val
  of 'v':
    if not assigned[int(e.val)]: raise newException(RErr, "r")
    vals[int(e.val)]
  of 'N': 0'u32 - ev(e.a)
  of '#': popc(ev(e.a))
  of 'L': (if ev(e.a) == 0: 1'u32 else: 0'u32)
  else:
    let a = ev(e.a)
    let b = ev(e.b)
    case e.op
    of 'M': (if a > b: a else: b)
    of 'm': (if a < b: a else: b)
    of '=': (if a == b: 1'u32 else: 0'u32)
    of '!': (if a != b: 1'u32 else: 0'u32)
    of '<': (if a < b: 1'u32 else: 0'u32)
    of '>': (if a > b: 1'u32 else: 0'u32)
    of '+': a + b
    of '-': a - b
    of '*': a * b
    of '/':
      if b == 0: raise newException(RErr, "r")
      a div b
    of '%':
      if b == 0: raise newException(RErr, "r")
      a mod b
    of '~': rotl(a, b)
    else: 0'u32

var broke = false
var curLine = 0

proc run(ss: seq[Stmt]) =
  for s in ss:
    curLine = s.line
    case s.k
    of sSet:
      let v = ev(s.exs[0])
      vals[s.v] = v
      assigned[s.v] = true
    of sOut:
      var parts: seq[string]
      for e in s.exs: parts.add $ev(e)
      outBuf.add parts.join(" ")
      outBuf.add '\n'
      if outBuf.len > 60000:
        stdout.write outBuf
        outBuf.setLen 0
    of sLoop:
      var n = ev(s.exs[0])
      while n > 0:
        run(s.body)
        if broke:
          broke = false
          break
        dec n
    of sWhen:
      if s.isBreak: broke = true
      elif ev(s.exs[0]) != 0: run(s.body)
      else: run(s.els)
    if broke: return

proc main() =
  if paramCount() != 1: quit(1)
  var data: string
  try:
    data = readFile(paramStr(1))
  except CatchableError:
    quit(1)
  var lines = data.split('\n')
  if lines.len > 0 and lines[^1] == "": lines.setLen(lines.len - 1)
  var root: seq[Stmt]
  # stack of open blocks
  var stack: seq[Stmt]
  var inElse: seq[bool]
  var errLine = 0
  proc addS(x: Stmt) =
    if stack.len == 0: root.add x
    elif inElse[^1]: stack[^1].els.add x
    else: stack[^1].body.add x
  var loopDepth = 0
  for li in 0 ..< lines.len:
    let ln = li + 1
    var line = lines[li]
    try:
      if line.len > 1000: perr()
      for ch in line:
        if not (ch == '\t' or ch == '\r' or (ch >= ' ' and ch <= '~')): perr()
      let sc = line.find(';')
      if sc >= 0: line = line[0 ..< sc]
      toks = tokenize(line)
      pos = 0
      depth = 0
      if toks.len == 0: continue
      let t = toks[0]
      if t.k != tWord or not isKw(t.s): perr()
      pos = 1
      case t.s
      of "set":
        if pos >= toks.len or toks[pos].k != tWord or isKw(toks[pos].s): perr()
        let vi = getVar(toks[pos].s)
        inc pos
        if not isOp("="): perr()
        inc pos
        let e = pL1()
        if pos != toks.len: perr()
        addS(Stmt(k: sSet, line: ln, v: vi, exs: @[e]))
      of "out":
        var es: seq[Ex]
        es.add pL1()
        while isOp(","):
          inc pos
          es.add pL1()
        if pos != toks.len: perr()
        addS(Stmt(k: sOut, line: ln, exs: es))
      of "loop", "when":
        let e = pL1()
        if pos != toks.len: perr()
        if stack.len >= 16: perr()
        let s = Stmt(k: if t.s == "loop": sLoop else: sWhen, line: ln, exs: @[e])
        addS(s)
        stack.add s
        inElse.add false
        if t.s == "loop": inc loopDepth
      of "else":
        if pos != toks.len: perr()
        if stack.len == 0 or stack[^1].k != sWhen or inElse[^1]: perr()
        inElse[^1] = true
      of "end":
        if pos != toks.len: perr()
        if stack.len == 0: perr()
        if stack[^1].k == sLoop: dec loopDepth
        stack.setLen(stack.len - 1)
        inElse.setLen(inElse.len - 1)
      of "break":
        if pos != toks.len: perr()
        if loopDepth == 0: perr()
        # represent break as a when-less marker: use sWhen with constant 1? use special stmt
        addS(Stmt(k: sWhen, line: ln, exs: @[Ex(op: 'n', val: 1)], isBreak: true))
      else: perr()
    except PErr:
      errLine = ln
      break
  if errLine == 0 and stack.len > 0:
    errLine = stack[^1].line
  if errLine != 0:
    stdout.write "parse error line " & $errLine & "\n"
    quit(2)
  try:
    run(root)
  except RErr:
    stdout.write outBuf
    stdout.write "runtime error line " & $curLine & "\n"
    quit(3)
  stdout.write outBuf

main()
