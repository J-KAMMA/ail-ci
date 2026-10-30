import std/[os, tables, algorithm]

type
  Rec = object
    off: int
    op: int
    a, b, c: int64
    name: string
  Acc = object
    name: string
    bal: int64
    shut: bool

proc fail(kind: string, off: int) =
  stdout.write "error at offset " & $off & ": " & kind & "\n"
  quit(2)

proc main() =
  if paramCount() != 1: quit(1)
  var data: string
  try:
    data = readFile(paramStr(1))
  except CatchableError:
    quit(1)
  let n = data.len
  if n < 6 or data[0] != '\xC7' or data[1] != 'L' or data[2] != 'X' or data[3] != 'F' or
     data[4] != '\x02' or (ord(data[5]) and 0xFE) != 0:
    fail("header", 0)
  let strict = (ord(data[5]) and 1) == 1
  var pos = 6
  var recs: seq[Rec]
  while pos < n:
    let start = pos
    var r: Rec
    r.off = start
    var chk = 0
    template take(): int =
      let bv = ord(data[pos])
      chk = (chk * 31 + bv) mod 251
      inc pos
      bv
    proc dummy() = discard
    # read var
    template readVar(dst: var int64) =
      block:
        var v: int64 = 0
        var shift = 0
        var cnt = 0
        var lastb = 0
        while true:
          if pos >= n: fail("truncated", start)
          let bv = take()
          inc cnt
          lastb = bv
          v = v or (int64(bv and 0x7F) shl shift)
          shift += 7
          if (bv and 0x80) != 0:
            if cnt == 5: fail("varint", start)
          else:
            break
        if (cnt >= 2 and lastb == 0) or v > 4294967295'i64: fail("varint", start)
        dst = v
    let op = take()
    r.op = op
    case op
    of 1:
      readVar(r.a)
      if pos >= n: fail("truncated", start)
      let nl = take()
      if nl < 1 or nl > 32: fail("name", start)
      for i in 0 ..< nl:
        if pos >= n: fail("truncated", start)
        let bv = take()
        if bv < 0x21 or bv > 0x7E: fail("name", start)
        r.name.add char(bv)
      readVar(r.b)
    of 2:
      readVar(r.a); readVar(r.b); readVar(r.c)
    of 3:
      readVar(r.a)
    of 4:
      readVar(r.a); readVar(r.b)
    of 5:
      readVar(r.a)
      if int64(n - pos) < r.a: fail("truncated", start)
      for i in 0 ..< int(r.a):
        discard take()
    else:
      fail("opcode", start)
    if pos >= n: fail("truncated", start)
    if ord(data[pos]) != chk: fail("check", start)
    inc pos
    recs.add r

  var accs = initTable[int64, Acc]()
  var rd, ru, rh, rs, rf = 0
  for r in recs:
    var reason = ""
    case r.op
    of 1:
      if accs.hasKey(r.a): reason = "dup"
      else: accs[r.a] = Acc(name: r.name, bal: r.b)
    of 2:
      if not accs.hasKey(r.a) or not accs.hasKey(r.b): reason = "unknown"
      elif accs[r.a].shut or accs[r.b].shut: reason = "shut"
      elif r.a == r.b: reason = "self"
      elif r.c > accs[r.a].bal: reason = "funds"
      else:
        accs[r.a].bal -= r.c
        accs[r.b].bal += r.c
    of 3:
      if not accs.hasKey(r.a): reason = "unknown"
      elif accs[r.a].shut: reason = "shut"
      else: accs[r.a].shut = true
    of 4:
      if not accs.hasKey(r.a): reason = "unknown"
      elif accs[r.a].shut: reason = "shut"
      else: accs[r.a].bal += r.b
    else: discard
    if reason != "":
      if strict:
        stdout.write "rejected at offset " & $r.off & ": " & reason & "\n"
        quit(3)
      case reason
      of "dup": inc rd
      of "unknown": inc ru
      of "shut": inc rh
      of "self": inc rs
      else: inc rf
  var ids: seq[int64]
  for k in accs.keys: ids.add k
  ids.sort()
  var openN, shutN = 0
  var total: int64 = 0
  var g: int64 = 0
  const P = 1000000007'i64
  var opens: seq[(int64, int64)]
  for id in ids:
    let a = accs[id]
    if a.shut: inc shutN else:
      inc openN
      opens.add (id, a.bal)
    total += a.bal
    g = (g * 1000003 + id * 7 + (a.bal mod P)) mod P
  opens.sort(proc (x, y: (int64, int64)): int =
    if x[1] != y[1]: (if x[1] > y[1]: -1 else: 1) else: cmp(x[0], y[0]))
  var o = "records: " & $recs.len & "\n"
  o &= "accounts: " & $openN & " open, " & $shutN & " shut\n"
  o &= "rejected: dup=" & $rd & " unknown=" & $ru & " shut=" & $rh & " self=" & $rs & " funds=" & $rf & "\n"
  o &= "total: " & $total & "\n"
  for i in 0 ..< min(5, opens.len):
    o &= "top: " & $opens[i][0] & " " & accs[opens[i][0]].name & " " & $opens[i][1] & "\n"
  o &= "digest: " & $g & "\n"
  stdout.write o

main()
