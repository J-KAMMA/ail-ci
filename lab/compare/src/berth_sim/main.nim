import std/algorithm

type Heap = object
  a: seq[int64]

proc push(h: var Heap, v: int64) =
  h.a.add v
  var i = h.a.len - 1
  while i > 0:
    let p = (i - 1) shr 1
    if h.a[p] > v:
      h.a[i] = h.a[p]
      i = p
    else: break
  h.a[i] = v

proc top(h: Heap): int64 {.inline.} = h.a[0]
proc empty(h: Heap): bool {.inline.} = h.a.len == 0

proc pop(h: var Heap) =
  let v = h.a[h.a.len - 1]
  h.a.setLen(h.a.len - 1)
  let n = h.a.len
  if n == 0: return
  var i = 0
  while true:
    var c = 2 * i + 1
    if c >= n: break
    if c + 1 < n and h.a[c + 1] < h.a[c]: inc c
    if h.a[c] < v:
      h.a[i] = h.a[c]
      i = c
    else: break
  h.a[i] = v

var data = stdin.readAll()
var pos = 0
proc readInt(): int =
  while pos < data.len and (data[pos] < '0' or data[pos] > '9'): inc pos
  var r = 0
  while pos < data.len and data[pos] >= '0' and data[pos] <= '9':
    r = r * 10 + (ord(data[pos]) - 48)
    inc pos
  r

proc main() =
  let B = readInt()
  let S = readInt()
  var cls = newSeq[int](B)
  var rate = newSeq[int](B)
  for i in 0 ..< B:
    cls[i] = readInt()
    rate[i] = readInt()
  var iid = newSeq[int32](S)
  var iarr = newSeq[int32](S)
  var isz = newSeq[int8](S)
  var icg = newSeq[int32](S)
  var ipr = newSeq[int8](S)
  var iop = newSeq[int32](S)
  for i in 0 ..< S:
    iid[i] = int32(readInt())
    iarr[i] = int32(readInt())
    isz[i] = int8(readInt())
    icg[i] = int32(readInt())
    ipr[i] = int8(readInt())
    iop[i] = int32(readInt())
  data = ""
  # sort by (arrival, id)
  var keys = newSeq[(int64, int32)](S)
  for i in 0 ..< S:
    keys[i] = ((int64(iarr[i]) shl 30) or int64(iid[i]), int32(i))
  keys.sort(proc (x, y: (int64, int32)): int = cmp(x[0], y[0]))
  var rid = newSeq[int32](S)
  var arr = newSeq[int32](S)
  var sz = newSeq[int8](S)
  var cg = newSeq[int32](S)
  var pr = newSeq[int8](S)
  var op = newSeq[int32](S)
  for r in 0 ..< S:
    let i = keys[r][1]
    rid[r] = iid[i]; arr[r] = iarr[i]; sz[r] = isz[i]
    cg[r] = icg[i]; pr[r] = ipr[i]; op[r] = iop[i]
  keys = @[]
  iid = @[]; iarr = @[]; isz = @[]; icg = @[]; ipr = @[]; iop = @[]
  var startT = newSeq[int64](S)
  var startB = newSeq[int32](S)
  var bn = newSeq[int64](B)
  var bu = newSeq[int64](B)
  var lastOp = newSeq[int](B)
  for i in 0 ..< B: lastOp[i] = -1
  var waiting: array[1..3, Heap]
  var freeH: array[1..3, Heap]
  for b in 0 ..< B: freeH[cls[b]].push(int64(b))
  var dep: Heap
  var nxt = 0
  var makespan = 0'i64
  while nxt < S or not dep.empty:
    var t = high(int64)
    if nxt < S: t = int64(arr[nxt])
    if not dep.empty and (dep.top shr 11) < t: t = dep.top shr 11
    while not dep.empty and (dep.top shr 11) == t:
      let b = int(dep.top and 2047)
      dep.pop
      freeH[cls[b]].push(int64(b))
    while nxt < S and int64(arr[nxt]) == t:
      waiting[int(sz[nxt])].push((int64(pr[nxt]) shl 22) or int64(nxt))
      inc nxt
    for c in 1..3:
      while not freeH[c].empty:
        var best = high(int64)
        var bs = 0
        for s in 1..c:
          if not waiting[s].empty and waiting[s].top < best:
            best = waiting[s].top; bs = s
        if bs == 0: break
        waiting[bs].pop
        let r = int(best and ((1 shl 22) - 1))
        let b = int(freeH[c].top)
        freeH[c].pop
        let setup = if lastOp[b] == int(op[r]): 1 else: 4
        lastOp[b] = int(op[r])
        let svc = int64((int(cg[r]) + rate[b] - 1) div rate[b] + setup)
        startT[r] = t
        startB[r] = int32(b)
        bn[b] += 1
        bu[b] += svc
        let e = t + svc
        if e > makespan: makespan = e
        dep.push((e shl 11) or int64(b))
  var total = 0'i64
  var mx = 0'i64
  var mxid = -1'i64
  for r in 0 ..< S:
    let w = startT[r] - int64(arr[r])
    total += w
    if S > 0 and (mxid == -1 or w > mx or (w == mx and int64(rid[r]) < mxid)):
      mx = w; mxid = int64(rid[r])
  var o = newStringOfCap(1 shl 16)
  o.add "ships " & $S & "\n"
  o.add "makespan " & $makespan & "\n"
  o.add "wait total " & $total & " max " & $mx & " ship " & $mxid & "\n"
  for b in 0 ..< B:
    o.add "berth " & $b & " ships " & $bn[b] & " busy " & $bu[b] & "\n"
  var ord2 = newSeq[(int32, int32)](S)
  for r in 0 ..< S: ord2[r] = (rid[r], int32(r))
  ord2.sort(proc (x, y: (int32, int32)): int = cmp(x[0], y[0]))
  var g = 0'i64
  for k in 0 ..< S:
    let r = int(ord2[k][1])
    g = (g * 1000003 + startT[r] * 31 + int64(startB[r])) mod 1000000007
  o.add "digest " & $g & "\n"
  stdout.write o

main()
