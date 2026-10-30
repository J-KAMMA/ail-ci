import std/[os, strutils, tables, sets, algorithm]

proc fail(n: int, cat: string, code: int) =
  stdout.write "line " & $n & ": " & cat & "\n"
  quit(code)

proc isDig(c: char): bool = c in '0'..'9'
proc isUp(c: char): bool = c in 'A'..'Z'
proc allDig(s: string): bool =
  for c in s:
    if not isDig(c): return false
  true

proc synVenue(s: string): bool =
  s.len == 3 and s[0].isUp and s[1].isUp and s[2].isUp
proc synName(s: string): bool =
  if s.len < 1 or s.len > 40: return false
  for c in s:
    if c < ' ' or c > '~' or c == '|': return false
  s[0] != ' ' and s[^1] != ' '
proc synCap(s: string): bool = s.len in 1..6 and allDig(s)
proc synEvent(s: string): bool = s.len == 6 and allDig(s)
proc synDate(s: string): bool =
  if s.len != 10 or s[4] != '-' or s[7] != '-': return false
  allDig(s[0..3]) and allDig(s[5..6]) and allDig(s[8..9])
proc synTime(s: string): bool =
  s.len == 5 and s[2] == ':' and allDig(s[0..1]) and allDig(s[3..4])
proc synPrice(s: string): bool =
  let p = s.find('.')
  if p < 1 or p > 4: return false
  s.len - p - 1 == 2 and allDig(s[0..p-1]) and allDig(s[p+1..^1])
proc synSeat(s: string): bool =
  s.len in 2..4 and s[0].isUp and allDig(s[1..^1])
proc synBuyer(s: string): bool =
  if s.len < 4 or s.len > 12: return false
  if not (s[0] in 'a'..'z'): return false
  for c in s:
    if not (c in 'a'..'z' or isDig(c)): return false
  true
proc synCount(s: string): bool = s.len in 1..9 and allDig(s)
proc synCents(s: string): bool = s.len in 1..12 and allDig(s)

proc num(s: string): int =
  for c in s: result = result * 10 + (ord(c) - 48)

proc valCap(s: string): bool =
  s[0] != '0' and num(s) in 1..100000
proc valEvent(s: string): bool =
  let d = proc(i: int): int = ord(s[i]) - 48
  (3*d(0) + d(1) + 3*d(2) + d(3) + 3*d(4) + d(5)) mod 10 == 0
proc valDate(s: string): bool =
  let y = num(s[0..3]); let m = num(s[5..6]); let d = num(s[8..9])
  if y < 2000 or y > 2099 or m < 1 or m > 12 or d < 1: return false
  var dm = [31,28,31,30,31,30,31,31,30,31,30,31]
  if y mod 4 == 0: dm[1] = 29
  d <= dm[m-1]
proc valTime(s: string): bool =
  num(s[0..1]) <= 23 and num(s[3..4]) <= 59
proc priceCents(s: string): int =
  let p = s.find('.')
  num(s[0..p-1]) * 100 + num(s[p+1..^1])
proc valPrice(s: string): bool =
  let p = s.find('.')
  if p > 1 and s[0] == '0': return false
  priceCents(s) mod 5 == 0
proc valSeat(s: string): bool = s[1] != '0'
proc valZ(s: string): bool = s == "0" or s[0] != '0'

proc money(c: int): string =
  $(c div 100) & "." & align($(c mod 100), 2, '0')

proc main() =
  if paramCount() != 1: quit(1)
  var data: string
  try:
    data = readFile(paramStr(1))
  except:
    quit(1)
  var lines = data.split('\n')
  if data.len > 0 and data[^1] == '\n': lines.setLen(lines.len - 1)
  if data.len == 0 or lines[0] != "TKT/1": fail(1, "header", 2)

  var venues = initTable[string, int]()           # code -> capacity
  var evVenue = initTable[string, string]()
  var evPrice = initTable[string, int]()
  var evOrder: seq[string]
  var sold = initTable[string, HashSet[string]]()
  var nV, nE, nS, nR, records, revenue = 0
  var ended = false

  for i in 1 ..< lines.len:
    let n = i + 1
    if ended: fail(n, "summary", 8)
    let f = lines[i].split('|')
    let t = f[0]
    var syn = false
    var val = false
    case t
    of "V":
      if f.len != 4: fail(n, "syntax", 3)
      if not (synVenue(f[1]) and synName(f[2]) and synCap(f[3])): fail(n, "syntax", 3)
      if not valCap(f[3]): fail(n, "value", 4)
      if f[1] in venues: fail(n, "duplicate", 6)
      venues[f[1]] = num(f[3]); inc nV
    of "E":
      if f.len != 6: fail(n, "syntax", 3)
      if not (synEvent(f[1]) and synVenue(f[2]) and synDate(f[3]) and synTime(f[4]) and synPrice(f[5])): fail(n, "syntax", 3)
      if not (valEvent(f[1]) and valDate(f[3]) and valTime(f[4]) and valPrice(f[5])): fail(n, "value", 4)
      if f[2] notin venues: fail(n, "reference", 5)
      if f[1] in evVenue: fail(n, "duplicate", 6)
      evVenue[f[1]] = f[2]; evPrice[f[1]] = priceCents(f[5]); evOrder.add f[1]
      sold[f[1]] = initHashSet[string](); inc nE
    of "S":
      if f.len != 4: fail(n, "syntax", 3)
      if not (synEvent(f[1]) and synSeat(f[2]) and synBuyer(f[3])): fail(n, "syntax", 3)
      if not (valEvent(f[1]) and valSeat(f[2])): fail(n, "value", 4)
      if f[1] notin evVenue: fail(n, "reference", 5)
      if f[2] in sold[f[1]]: fail(n, "duplicate", 6)
      if sold[f[1]].len >= venues[evVenue[f[1]]]: fail(n, "capacity", 7)
      sold[f[1]].incl f[2]; revenue += evPrice[f[1]]; inc nS
    of "R":
      if f.len != 3: fail(n, "syntax", 3)
      if not (synEvent(f[1]) and synSeat(f[2])): fail(n, "syntax", 3)
      if not (valEvent(f[1]) and valSeat(f[2])): fail(n, "value", 4)
      if f[1] notin evVenue: fail(n, "reference", 5)
      if f[2] notin sold[f[1]]: fail(n, "reference", 5)
      sold[f[1]].excl f[2]; revenue -= evPrice[f[1]]; inc nR
    of "END":
      if f.len != 3: fail(n, "syntax", 3)
      if not (synCount(f[1]) and synCents(f[2])): fail(n, "syntax", 3)
      if not (valZ(f[1]) and valZ(f[2])): fail(n, "value", 4)
      if num(f[1]) != records or num(f[2]) != revenue: fail(n, "summary", 8)
      ended = true
    else:
      fail(n, "syntax", 3)
    if t != "END": inc records
    discard syn; discard val

  if not ended: fail(lines.len + 1, "summary", 8)

  var o = "venues " & $nV & " events " & $nE & " sold " & $nS & " refunds " & $nR & "\n"
  o &= "revenue " & money(revenue) & "\n"
  var vc = initTable[string, (int, int, int)]()
  for c in venues.keys: vc[c] = (0, 0, 0)
  for e in evOrder:
    let v = evVenue[e]
    let k = sold[e].len
    let (a, b, c) = vc[v]
    vc[v] = (a + 1, b + k, c + k * evPrice[e])
  var codes: seq[string]
  for c in venues.keys: codes.add c
  codes.sort()
  for c in codes:
    let (a, b, r) = vc[c]
    o &= c & " events=" & $a & " tickets=" & $b & " revenue=" & money(r) & "\n"
  var evs = evOrder
  evs.sort(proc(x, y: string): int =
    let kx = sold[x].len; let ky = sold[y].len
    if kx != ky: return cmp(ky, kx)
    cmp(x, y))
  for j in 0 ..< min(3, evs.len):
    o &= "top " & evs[j] & " " & $sold[evs[j]].len & "\n"
  stdout.write o

main()
