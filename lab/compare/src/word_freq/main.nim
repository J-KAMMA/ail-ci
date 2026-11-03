import std/[tables, algorithm, strutils, os, sequtils]

proc main() =
  let data = readAll(stdin)
  var counts = initTable[string, int64]()
  var word = ""
  for c in data:
    if c in {'A'..'Z'}:
      word.add chr(ord(c) + 32)
    elif c in {'a'..'z'}:
      word.add c
    elif word.len > 0:
      counts[word] = counts.getOrDefault(word, 0'i64) + 1
      word = ""
  if word.len > 0:
    counts[word] = counts.getOrDefault(word, 0'i64) + 1
  var ranked = toSeq(counts.keys)
  ranked.sort(proc(a, b: string): int =
    if counts[a] != counts[b]:
      return cmp(counts[b], counts[a])
    return cmp(a, b))
  let limit = min(20, ranked.len)
  for i in 0 ..< limit:
    stdout.write $counts[ranked[i]] & " " & ranked[i] & "\n"

main()
