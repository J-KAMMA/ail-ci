import std/os

proc readAllStdin(): string =
  result = newStringOfCap(1 shl 16)
  var buf = newString(65536)
  while true:
    let k = stdin.readBuffer(addr buf[0], buf.len)
    if k <= 0: break
    let old = result.len
    result.setLen(old + k)
    copyMem(addr result[old], addr buf[0], k)

proc hashOf(s: string): uint32 =
  var h: uint32 = 0
  for c in s:
    h = h * 257'u32 + uint32(ord(c)) + 1'u32
  h

proc le32(x: uint32): string =
  result = newString(4)
  for k in 0..3: result[k] = char((x shr (8*k)) and 0xFF)

proc pack() =
  let d = readAllStdin()
  let n = d.len
  var o = newStringOfCap(n + n div 100 + 32)
  o.add "EP1"
  o.add le32(uint32(n))
  const HB = 22
  var head = newSeq[int32](1 shl HB)
  for x in head.mitems: x = -1
  var prev = newSeq[int32](n + 1)
  var lit = newStringOfCap(128)
  var inserted = 0 # positions < inserted are inserted
  template key(p: int): uint32 =
    uint32(ord(d[p])) or (uint32(ord(d[p+1])) shl 8) or
      (uint32(ord(d[p+2])) shl 16) or (uint32(ord(d[p+3])) shl 24)
  template hsh(p: int): int =
    int((key(p) * 2654435761'u32) shr (32 - HB))
  proc flush() =
    if lit.len > 0:
      o.add char(lit.len - 1)
      o.add lit
      lit.setLen(0)
  var i = 0
  while i < n:
    while inserted < i:
      if inserted + 4 <= n:
        let h = hsh(inserted)
        prev[inserted] = head[h]
        head[h] = int32(inserted)
      inc inserted
    var bestM = 0
    var bestP = -1
    if i + 4 <= n:
      var cnt = 0
      var p = int(head[hsh(i)])
      let k0 = key(i)
      let lim = min(131, n - i)
      while p >= 0 and i - p <= 65535 and cnt < 8:
        if key(p) == k0:
          inc cnt
          var m = 4
          while m < lim and d[p+m] == d[i+m]: inc m
          if m > bestM:
            bestM = m
            bestP = p
        p = int(prev[p])
    if bestP >= 0:
      flush()
      o.add char(0x80 + (bestM - 4))
      let dist = i - bestP
      o.add char(dist shr 8)
      o.add char(dist and 0xFF)
      i += bestM
    else:
      lit.add d[i]
      if lit.len == 128: flush()
      inc i
  flush()
  o.add le32(hashOf(d))
  discard stdout.writeBuffer(addr o[0], o.len)

proc fail() =
  quit(2)

proc unpack() =
  let s = readAllStdin()
  if s.len < 7 or s[0] != 'E' or s[1] != 'P' or s[2] != '1': fail()
  var n = 0'u64
  for k in 0..3: n = n or (uint64(ord(s[3+k])) shl (8*k))
  var o = newStringOfCap(int(min(n, 1'u64 shl 24)))
  var pos = 7
  while uint64(o.len) < n:
    if pos >= s.len: fail()
    let c = ord(s[pos]); inc pos
    if c < 0x80:
      let k = c + 1
      if pos + k > s.len: fail()
      if uint64(o.len + k) > n: fail()
      o.add s[pos ..< pos+k]
      pos += k
    else:
      if pos + 2 > s.len: fail()
      let dist = (ord(s[pos]) shl 8) or ord(s[pos+1])
      pos += 2
      let ln = (c - 0x80) + 4
      if dist == 0 or dist > o.len: fail()
      if uint64(o.len + ln) > n: fail()
      for _ in 0 ..< ln:
        o.add o[o.len - dist]
  if pos + 4 != s.len: fail()
  var h = 0'u32
  for k in 0..3: h = h or (uint32(ord(s[pos+k])) shl (8*k))
  if h != hashOf(o): fail()
  if o.len > 0:
    discard stdout.writeBuffer(addr o[0], o.len)

let args = commandLineParams()
if args.len != 1: quit(1)
case args[0]
of "pack": pack()
of "unpack": unpack()
else: quit(1)
