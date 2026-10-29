import std/[os, strutils]

proc fail() =
  quit(1)

proc code(c: char): int =
  case c
  of '0'..'9': ord(c) - ord('0')
  of 'A'..'C': ord(c) - ord('A') + 10
  else: -1

proc parseList(s: string, t: var array[13, bool]) =
  var last = -1
  for c in s:
    let v = code(c)
    if v < 0 or v <= last: fail()
    last = v
    t[v] = true

proc main() =
  if paramCount() != 2: fail()
  let rule = paramStr(1)
  let g = paramStr(2)
  if rule.len < 3 or rule[0] != 'B': fail()
  let sl = rule.find('/')
  if sl < 0 or sl + 1 >= rule.len or rule[sl + 1] != 'S': fail()
  var bt, st: array[13, bool]
  parseList(rule[1 ..< sl], bt)
  parseList(rule[sl + 2 .. ^1], st)
  if g.len == 0: fail()
  var gens = 0
  for c in g:
    if c notin {'0'..'9'}: fail()
    gens = gens * 10 + (ord(c) - 48)
    if gens > 100000: fail()

  let inp = stdin.readAll()
  var p = 0
  proc readNum(): int =
    let s = p
    var v = 0
    while p < inp.len and inp[p] in {'0'..'9'}:
      v = v * 10 + (ord(inp[p]) - 48)
      inc p
      if p - s > 5: fail()
    if p == s: fail()
    if inp[s] == '0': fail()
    if v < 1 or v > 4096: fail()
    v
  let W = readNum()
  if p >= inp.len or inp[p] != ' ': fail()
  inc p
  let H = readNum()
  if p >= inp.len or inp[p] != '\n': fail()
  inc p
  var cur = newSeq[uint8](W * H)
  for y in 0 ..< H:
    if p + W > inp.len: fail()
    for x in 0 ..< W:
      let c = inp[p + x]
      if c == 'o': cur[y * W + x] = 1
      elif c != '.': fail()
    p += W
    if y < H - 1:
      if p >= inp.len or inp[p] != '\n': fail()
      inc p
    else:
      if p < inp.len:
        if inp[p] != '\n': fail()
        inc p
        if p != inp.len: fail()

  var nxt = newSeq[uint8](W * H)
  var xl = newSeq[int](W)
  var xr = newSeq[int](W)
  for x in 0 ..< W:
    xl[x] = if x == 0: W - 1 else: x - 1
    xr[x] = if x == W - 1: 0 else: x + 1
  var outp = newStringOfCap(gens * 14 + W * H + H + 16)
  for gi in 1 .. gens:
    var na, ns = 0
    for y in 0 ..< H:
      let ru = (if y == 0: H - 1 else: y - 1) * W
      let rd = (if y == H - 1: 0 else: y + 1) * W
      let rc = y * W
      for x in 0 ..< W:
        let l = xl[x]
        let r = xr[x]
        let w = 2 * (int(cur[ru + x] and 1) + int(cur[rd + x] and 1) +
                     int(cur[rc + l] and 1) + int(cur[rc + r] and 1)) +
                int(cur[ru + l] and 1) + int(cur[ru + r] and 1) +
                int(cur[rd + l] and 1) + int(cur[rd + r] and 1)
        let s = cur[rc + x]
        var n: uint8 = 0
        if s == 1:
          if st[w]: n = 1 else: n = 2
        elif s == 0:
          if bt[w]: n = 1
        nxt[rc + x] = n
        if n == 1: inc na
        elif n == 2: inc ns
    swap(cur, nxt)
    outp.add($gi); outp.add(' '); outp.add($na); outp.add(' '); outp.add($ns); outp.add('\n')
  for y in 0 ..< H:
    for x in 0 ..< W:
      outp.add(case cur[y * W + x]
        of 0: '.'
        of 1: 'o'
        else: 'x')
    outp.add('\n')
  stdout.write(outp)

main()
