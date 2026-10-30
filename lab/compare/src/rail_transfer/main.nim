import std/[algorithm]

type HE = object
  t: int64
  b: int32
  n: int32

var heap: seq[HE]
var hn = 0

proc less(a, b: HE): bool {.inline.} =
  a.t < b.t or (a.t == b.t and a.b < b.b)

proc hpush(e: HE) =
  if hn >= heap.len: heap.setLen(max(16, heap.len * 2))
  var i = hn
  inc hn
  while i > 0:
    let p = (i - 1) shr 1
    if less(e, heap[p]):
      heap[i] = heap[p]
      i = p
    else: break
  heap[i] = e

proc hpop(): HE =
  result = heap[0]
  dec hn
  if hn > 0:
    let e = heap[hn]
    var i = 0
    while true:
      var c = 2 * i + 1
      if c >= hn: break
      if c + 1 < hn and less(heap[c + 1], heap[c]): inc c
      if less(heap[c], e):
        heap[i] = heap[c]
        i = c
      else: break
    heap[i] = e

proc main() =
  let data = stdin.readAll()
  var pos = 0
  proc nextInt(): int =
    while pos < data.len and (data[pos] < '0' or data[pos] > '9'): inc pos
    var r = 0
    while pos < data.len and data[pos] >= '0' and data[pos] <= '9':
      r = r * 10 + (ord(data[pos]) - 48)
      inc pos
    r
  let n = nextInt()
  let m = nextInt()
  let q = nextInt()
  var X = newSeq[int64](n)
  for i in 0 ..< n: X[i] = nextInt()
  var su = newSeq[int32](m)
  var sv = newSeq[int32](m)
  var sl = newSeq[int32](m)
  var st = newSeq[int32](m)
  var keys = newSeqOfCap[int64](2 * m)
  for i in 0 ..< m:
    let u = nextInt()
    let v = nextInt()
    let l = nextInt()
    let t = nextInt()
    su[i] = int32(u); sv[i] = int32(v); sl[i] = int32(l); st[i] = int32(t)
    if u != v:
      keys.add(int64(u) * 100000 + l)
      keys.add(int64(v) * 100000 + l)
  keys.sort()
  var uk = newSeqOfCap[int64](keys.len)
  for k in keys:
    if uk.len == 0 or uk[^1] != k: uk.add(k)
  keys = @[]
  let rn = uk.len
  # station offsets
  var sOff = newSeq[int32](n + 1)
  for k in uk: inc sOff[int(k div 100000) + 1]
  for i in 0 ..< n: sOff[i + 1] += sOff[i]
  proc findNode(k: int64): int =
    var lo = 0
    var hi = rn - 1
    while lo < hi:
      let mid = (lo + hi) shr 1
      if uk[mid] < k: lo = mid + 1 else: hi = mid
    lo
  var eOff = newSeq[int32](rn + 1)
  var ea = newSeq[int32](m)
  var eb = newSeq[int32](m)
  for i in 0 ..< m:
    if su[i] != sv[i]:
      let a = findNode(int64(su[i]) * 100000 + sl[i])
      let b = findNode(int64(sv[i]) * 100000 + sl[i])
      ea[i] = int32(a); eb[i] = int32(b)
      inc eOff[a + 1]; inc eOff[b + 1]
    else:
      ea[i] = -1
  for i in 0 ..< rn: eOff[i + 1] += eOff[i]
  let tot = int(eOff[rn])
  var eTo = newSeq[int32](tot)
  var eT = newSeq[int32](tot)
  var fill = newSeq[int32](rn)
  for i in 0 ..< m:
    if ea[i] >= 0:
      let a = int(ea[i])
      let b = int(eb[i])
      let pa = int(eOff[a]) + int(fill[a]); inc fill[a]
      eTo[pa] = int32(b); eT[pa] = st[i]
      let pb = int(eOff[b]) + int(fill[b]); inc fill[b]
      eTo[pb] = int32(a); eT[pb] = st[i]
  su = @[]; sv = @[]; sl = @[]; st = @[]; ea = @[]; eb = @[]; fill = @[]
  var nodeSt = newSeq[int32](rn)
  for i in 0 ..< rn: nodeSt[i] = int32(uk[i] div 100000)

  var qs = newSeq[int](q)
  var qd = newSeq[int](q)
  for i in 0 ..< q:
    qs[i] = nextInt()
    qd[i] = nextInt()
  var resT = newSeq[int64](q)
  var resB = newSeq[int32](q)
  var resOk = newSeq[bool](q)
  var order = newSeq[int](q)
  for i in 0 ..< q: order[i] = i
  order.sort(proc (a, b: int): int = cmp(qs[a], qs[b]))

  type ND = object
    t: int64
    b: int32
    stamp: int32
  var nds = newSeq[ND](rn + n)
  # pair components (2 stations): replace by station edges
  var isPair = newSeq[bool](rn)
  var pOff = newSeq[int32](n + 1)
  var pLst: seq[(int32, int32, int32)]
  for u in 0 ..< rn:
    let lo = int(eOff[u]); let hi = int(eOff[u + 1])
    let w = eTo[lo]
    let w2 = int(w)
    var ok = true
    var mn = int32(high(int32))
    for k in lo ..< hi:
      if eTo[k] != w: ok = false; break
      if eT[k] < mn: mn = eT[k]
    if ok:
      for k in int(eOff[w2]) ..< int(eOff[w2 + 1]):
        if int(eTo[k]) != u: ok = false; break
    if ok:
      isPair[u] = true
      pLst.add((nodeSt[u], nodeSt[w2], mn))
      inc pOff[int(nodeSt[u]) + 1]
  for i in 0 ..< n: pOff[i + 1] += pOff[i]
  var pTo = newSeq[int32](pLst.len)
  var pT = newSeq[int32](pLst.len)
  block:
    var f = newSeq[int32](n)
    for (a, b, t) in pLst:
      let p = int(pOff[a]) + int(f[a]); inc f[a]
      pTo[p] = b; pT[p] = t
  pLst = @[]
  # union-find for reachability
  var par = newSeq[int32](n)
  for i in 0 ..< n: par[i] = int32(i)
  proc find(x: int): int =
    var r = x
    while par[r] != int32(r): r = int(par[r])
    var y = x
    while par[y] != int32(r):
      let nx = int(par[y]); par[y] = int32(r); y = nx
    r
  for u in 0 ..< rn:
    let a = find(int(nodeSt[u]))
    for k in int(eOff[u]) ..< int(eOff[u + 1]):
      let b = find(int(nodeSt[eTo[k]]))
      if a != b: par[b] = int32(a)
  var sdone = newSeq[int32](n)   # stamp when expanded
  var stimeA = newSeq[int64](n)
  var sboardA = newSeq[int32](n)
  var cur: int32 = 0
  var wanted = newSeq[int32](n)  # stamp marking wanted destinations

  var idx = 0
  while idx < q:
    let s = qs[order[idx]]
    var j = idx
    while j < q and qs[order[j]] == s: inc j
    inc cur
    var remaining = 0
    for k in idx ..< j:
      let d = qd[order[k]]
      if d == s:
        resOk[order[k]] = true; resT[order[k]] = 0; resB[order[k]] = 0
      elif find(d) != find(s): discard
      elif wanted[d] != cur:
        wanted[d] = cur
        inc remaining
    if remaining > 0:
      hn = 0
      for nd in int(sOff[s]) ..< int(sOff[s + 1]):
        if isPair[nd]: continue
        nds[nd] = ND(t: 0, b: 1, stamp: cur)
        hpush(HE(t: 0, b: 1, n: int32(nd)))
      for k in int(pOff[s]) ..< int(pOff[s + 1]):
        let w = rn + int(pTo[k])
        let nt = int64(pT[k])
        if nds[w].stamp != cur or nt < nds[w].t or (nt == nds[w].t and 1 < nds[w].b):
          nds[w] = ND(t: nt, b: 1, stamp: cur)
          hpush(HE(t: nt, b: 1, n: int32(w)))
      while hn > 0:
        let e = hpop()
        let u = int(e.n)
        if nds[u].t != e.t or nds[u].b != e.b: continue
        let v = if u >= rn: u - rn else: int(nodeSt[u])
        if sdone[v] != cur:
          sdone[v] = cur
          stimeA[v] = e.t; sboardA[v] = e.b
          if wanted[v] == cur:
            dec remaining
            if remaining == 0: break
          let nt = e.t + X[v]
          let nb = e.b + 1
          for k in int(pOff[v]) ..< int(pOff[v + 1]):
            let w = rn + int(pTo[k])
            let t2 = nt + pT[k]
            if nds[w].stamp != cur or t2 < nds[w].t or (t2 == nds[w].t and nb < nds[w].b):
              nds[w] = ND(t: t2, b: nb, stamp: cur)
              hpush(HE(t: t2, b: nb, n: int32(w)))
          for w in int(sOff[v]) ..< int(sOff[v + 1]):
            if isPair[w]: continue
            if nds[w].stamp != cur or nt < nds[w].t or (nt == nds[w].t and nb < nds[w].b):
              nds[w] = ND(t: nt, b: nb, stamp: cur)
              hpush(HE(t: nt, b: nb, n: int32(w)))
        if u < rn:
         for k in int(eOff[u]) ..< int(eOff[u + 1]):
          let w = int(eTo[k])
          let nt = e.t + eT[k]
          if nds[w].stamp != cur or nt < nds[w].t or (nt == nds[w].t and e.b < nds[w].b):
            nds[w] = ND(t: nt, b: e.b, stamp: cur)
            hpush(HE(t: nt, b: e.b, n: int32(w)))
      for k in idx ..< j:
        let d = qd[order[k]]
        if d != s and sdone[d] == cur:
          resOk[order[k]] = true; resT[order[k]] = stimeA[d]; resB[order[k]] = sboardA[d]
    idx = j

  var outp = newStringOfCap(q * 16)
  for i in 0 ..< q:
    if resOk[i]:
      outp.add($resT[i]); outp.add(' '); outp.add($resB[i]); outp.add('\n')
    else:
      outp.add("none\n")
  stdout.write(outp)

main()
