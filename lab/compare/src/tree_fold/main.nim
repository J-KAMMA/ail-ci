import std/[algorithm, strutils]

var data = stdin.readAll()

proc fail() {.noreturn.} = quit(1)

var
  pool: string
  nOff, nLen, fc, ns, par: seq[int32]
  wt: seq[int64]
  root: int32 = 0
  outp = newStringOfCap(1 shl 16)

type Op = object
  kind: int  # 0 total,1 stats,2 level,3 find,4 print,5 prune,6 sort,7 mirror,8 fold,9 cut
  num: int64
  name: string

var ops: seq[Op]

proc parseNum(s: string, a: int, maxv: int64): int64 =
  let l = s.len - a
  if l < 1 or l > 16: fail()
  if l > 1 and s[a] == '0': fail()
  var v = 0'i64
  for i in a ..< s.len:
    if s[i] notin '0'..'9': fail()
    v = v * 10 + int64(ord(s[i]) - 48)
  if v > maxv: fail()
  v

proc validName(s: string, a: int): string =
  if s.len - a < 1: fail()
  for i in a ..< s.len:
    if s[i] notin {'a'..'z', '+'}: fail()
  s[a .. ^1]

proc main() =
  var e = data.len
  if e > 0 and data[e-1] == '\n': dec e
  if e == 0: fail()
  # split lines
  var lines: seq[(int, int)]
  var s = 0
  for i in 0 .. e:
    if i == e or data[i] == '\n':
      if i == s: fail()
      lines.add((s, i))
      s = i + 1
  let e1 = lines[0][1]
  var cnt = 1
  for i in 0 ..< e1:
    if data[i] == ':': inc cnt
  nOff = newSeq[int32](cnt); nLen = newSeq[int32](cnt)
  fc = newSeq[int32](cnt); ns = newSeq[int32](cnt); par = newSeq[int32](cnt)
  wt = newSeq[int64](cnt)
  var lc = newSeq[int32](cnt)
  pool = newStringOfCap(e1 + 64)
  var stack: seq[int32]
  var n = 0
  var p = 0
  while true:
    let s0 = p
    while p < e1 and data[p] in 'a'..'z': inc p
    let L = p - s0
    if L < 1 or L > 16 or p >= e1 or data[p] != ':': fail()
    inc p
    let ds = p
    while p < e1 and data[p] in '0'..'9': inc p
    let dl = p - ds
    if dl == 0 or dl > 7 or (dl > 1 and data[ds] == '0'): fail()
    var v = 0'i64
    for i in ds ..< p: v = v * 10 + int64(ord(data[i]) - 48)
    if v > 1000000: fail()
    let id = int32(n)
    inc n
    nOff[id] = int32(pool.len); nLen[id] = int32(L)
    for i in s0 ..< s0 + L: pool.add data[i]
    wt[id] = v
    fc[id] = -1; ns[id] = -1; lc[id] = -1
    if stack.len > 0:
      let q = stack[^1]
      par[id] = q
      if fc[q] < 0: fc[q] = id else: ns[lc[q]] = id
      lc[q] = id
    else:
      par[id] = -1
    if p < e1 and data[p] == '[':
      stack.add id
      inc p
      continue
    var done = false
    while true:
      if p < e1 and data[p] == ']' and stack.len > 0:
        discard stack.pop()
        inc p
      elif p < e1 and data[p] == ' ' and stack.len > 0:
        inc p
        break
      elif p == e1 and stack.len == 0:
        done = true
        break
      else: fail()
    if done: break
  # operations
  for li in 1 ..< lines.len:
    let (a, b) = lines[li]
    let ln = data[a ..< b]
    var op: Op
    case ln
    of "total": op.kind = 0
    of "stats": op.kind = 1
    of "print": op.kind = 4
    of "sort": op.kind = 6
    of "mirror": op.kind = 7
    of "fold": op.kind = 8
    else:
      if ln.len > 6 and ln.startsWith("level "):
        op.kind = 2; op.num = parseNum(ln, 6, 1_000_000_000_000_000'i64)
      elif ln.len > 6 and ln.startsWith("prune "):
        op.kind = 5; op.num = parseNum(ln, 6, 1_000_000_000_000_000'i64)
      elif ln.len > 5 and ln.startsWith("find "):
        op.kind = 3; op.name = validName(ln, 5)
      elif ln.len > 4 and ln.startsWith("cut "):
        op.kind = 9; op.name = validName(ln, 4)
      else: fail()
    ops.add op

  proc nextOf(v: int32): int32 =
    if fc[v] >= 0: return fc[v]
    var u = v
    while u != root and ns[u] < 0: u = par[u]
    if u == root: return -1
    ns[u]

  proc computeOrder(): seq[int32] =
    var r: seq[int32]
    var c = root
    while c >= 0:
      r.add c
      c = nextOf(c)
    r

  proc subWeights(order: seq[int32]): seq[int64] =
    var sub = wt
    for i in countdown(order.high, 1):
      let v = order[i]
      sub[par[v]] += sub[v]
    sub

  proc nameCmp(a, b: int32): int =
    let la = nLen[a]; let lb = nLen[b]
    let m = min(la, lb)
    let oa = nOff[a]; let ob = nOff[b]
    for i in 0 ..< m:
      let x = pool[oa + i]; let y = pool[ob + i]
      if x != y: return ord(x) - ord(y)
    int(la) - int(lb)

  proc nameIs(v: int32, s: string): bool =
    if int(nLen[v]) != s.len: return false
    let o = nOff[v]
    for i in 0 ..< s.len:
      if pool[o + i] != s[i]: return false
    true

  proc addName(v: int32) =
    let o = nOff[v]
    for i in 0 ..< nLen[v]: pool.add pool[o + i]

  proc findFirst(name: string): int32 =
    var c = root
    while c >= 0:
      if nameIs(c, name): return c
      c = nextOf(c)
    -1

  for op in ops:
    case op.kind
    of 0:
      var t = 0'i64
      var c = root
      while c >= 0:
        t += wt[c]
        c = nextOf(c)
      outp.add $t & "\n"
    of 1:
      var nodes, leaves, h, widest = 0
      var depth = 0
      var c = root
      while c >= 0:
        inc nodes
        if depth > h: h = depth
        if fc[c] < 0: inc leaves
        else:
          var k = 0
          var x = fc[c]
          while x >= 0:
            inc k
            x = ns[x]
          if k > widest: widest = k
        # advance
        if fc[c] >= 0:
          c = fc[c]; inc depth
        else:
          var u = c
          while u != root and ns[u] < 0:
            u = par[u]; dec depth
          if u == root: c = -1 else: c = ns[u]
      outp.add "nodes=" & $nodes & " leaves=" & $leaves & " height=" & $h & " widest=" & $widest & "\n"
    of 2:
      var count = 0'i64
      var sum = 0'i64
      var depth = 0'i64
      var c = root
      while c >= 0:
        if depth == op.num:
          inc count; sum += wt[c]
        if fc[c] >= 0 and depth < op.num:
          c = fc[c]; inc depth
        else:
          var u = c
          while u != root and ns[u] < 0:
            u = par[u]; dec depth
          if u == root: c = -1 else: c = ns[u]
      outp.add $count & " " & $sum & "\n"
    of 3:
      let f = findFirst(op.name)
      if f < 0: outp.add "none\n"
      else:
        var path: seq[int32]
        var u = f
        while u >= 0:
          path.add u
          u = par[u]
        for i in countdown(path.high, 0):
          let v = path[i]
          let o = nOff[v]
          for j in 0 ..< nLen[v]: outp.add pool[o + j]
          if i > 0: outp.add '/'
        outp.add '\n'
    of 4:
      var c = root
      while true:
        let o = nOff[c]
        for j in 0 ..< nLen[c]: outp.add pool[o + j]
        outp.add ':'
        outp.add $wt[c]
        if fc[c] >= 0:
          outp.add '['
          c = fc[c]
          continue
        while true:
          if c == root: break
          if ns[c] >= 0:
            outp.add ' '
            c = ns[c]
            break
          c = par[c]
          outp.add ']'
        if c == root: break
      outp.add '\n'
    of 5:
      let order = computeOrder()
      let sub = subWeights(order)
      for v in order:
        var prev = -1'i32
        var x = fc[v]
        fc[v] = -1
        while x >= 0:
          let nx = ns[x]
          if sub[x] >= op.num:
            if prev < 0: fc[v] = x else: ns[prev] = x
            prev = x
          x = nx
        if prev >= 0: ns[prev] = -1
    of 6:
      let order = computeOrder()
      let sub = subWeights(order)
      var kids: seq[int32]
      for v in order:
        if fc[v] >= 0 and ns[fc[v]] >= 0:
          kids.setLen(0)
          var x = fc[v]
          while x >= 0:
            kids.add x
            x = ns[x]
          kids.sort(proc (a, b: int32): int =
            if sub[a] != sub[b]: return (if sub[a] > sub[b]: -1 else: 1)
            nameCmp(a, b))
          fc[v] = kids[0]
          for i in 0 ..< kids.high: ns[kids[i]] = kids[i+1]
          ns[kids[^1]] = -1
    of 7:
      let order = computeOrder()
      for v in order:
        if fc[v] >= 0 and ns[fc[v]] >= 0:
          var prev = -1'i32
          var x = fc[v]
          while x >= 0:
            let nx = ns[x]
            ns[x] = prev
            prev = x
            x = nx
          fc[v] = prev
    of 8:
      var c = root
      while c >= 0:
        let v = c
        if v != root and fc[v] >= 0 and ns[fc[v]] < 0:
          let start = pool.len
          addName(v)
          var w = wt[v]
          while fc[v] >= 0 and ns[fc[v]] < 0:
            let ch = fc[v]
            pool.add '+'
            addName(ch)
            w += wt[ch]
            fc[v] = fc[ch]
            var x = fc[ch]
            while x >= 0:
              par[x] = v
              x = ns[x]
          nOff[v] = int32(start); nLen[v] = int32(pool.len - start)
          wt[v] = w
        c = nextOf(v)
    of 9:
      let v = findFirst(op.name)
      if v >= 0 and v != root:
        let p = par[v]
        var prev = -1'i32
        var x = fc[p]
        while x != v:
          prev = x
          x = ns[x]
        var first = fc[v]
        var last = -1'i32
        var y = first
        while y >= 0:
          par[y] = p
          last = y
          y = ns[y]
        if first < 0:
          first = ns[v]
        else:
          ns[last] = ns[v]
        if prev < 0: fc[p] = first else: ns[prev] = first
    else: discard
  stdout.write outp

main()
