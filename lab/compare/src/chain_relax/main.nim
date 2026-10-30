import std/[math, strutils, os]

proc parseU(s: string, maxv: uint64, res: var uint64): bool =
  if s.len == 0: return false
  var v: uint64 = 0
  for ch in s:
    if ch < '0' or ch > '9': return false
    let d = uint64(ord(ch) - 48)
    if v > (high(uint64) - d) div 10: return false
    v = v * 10 + d
    if v > maxv: return false
  res = v
  true

proc fmt(v: float64): string =
  var s = formatFloat(v, ffDecimal, 9)
  if s.startsWith("-"):
    var allz = true
    for ch in s:
      if ch in {'1'..'9'}: allz = false
    if allz: s = s[1..^1]
  s

proc main() =
  if paramCount() != 3: quit(1)
  var n, t, seed: uint64
  if not parseU(paramStr(1), 10000000'u64, n) or n < 1: quit(1)
  if not parseU(paramStr(2), 1000000'u64, t): quit(1)
  if not parseU(paramStr(3), high(uint64), seed): quit(1)
  let N = int(n)
  var h = newSeq[float64](N)
  var x = seed
  for i in 0 ..< N:
    x = x * 6364136223846793005'u64 + 1442695040888963407'u64
    h[i] = float64(int64((x shr 33) mod 2001'u64) - 1000) / 64.0
  let hp = cast[ptr UncheckedArray[float64]](addr h[0])
  for s in 1'u64 .. t:
    if (s and 1) == 1:
      for i in 0 ..< N:
        let l = hp[if i == 0: N - 1 else: i - 1]
        let r = hp[if i == N - 1: 0 else: i + 1]
        let c = hp[i]
        let d = (l + r) - (c + c)
        let g = d / (1.0 + sqrt(d * d + 0.0625))
        hp[i] = c + 0.375 * g
    else:
      for i in countdown(N - 1, 0):
        let l = hp[if i == 0: N - 1 else: i - 1]
        let r = hp[if i == N - 1: 0 else: i + 1]
        let c = hp[i]
        let d = (l + r) - (c + c)
        let g = d / (1.0 + sqrt(d * d + 0.0625))
        hp[i] = c + 0.375 * g
  var sum = 0.0
  var energy = 0.0
  var mn = h[0]
  var mx = h[0]
  for i in 0 ..< N:
    sum = sum + h[i]
    let tt = h[if i == N - 1: 0 else: i + 1] - h[i]
    energy = energy + tt * tt
    if h[i] < mn: mn = h[i]
    if h[i] > mx: mx = h[i]
  var o = ""
  o.add "sum " & fmt(sum) & "\n"
  o.add "energy " & fmt(energy) & "\n"
  o.add "min " & fmt(mn) & "\n"
  o.add "max " & fmt(mx) & "\n"
  o.add "first " & fmt(h[0]) & "\n"
  o.add "middle " & fmt(h[N div 2]) & "\n"
  o.add "last " & fmt(h[N - 1]) & "\n"
  stdout.write o

main()
