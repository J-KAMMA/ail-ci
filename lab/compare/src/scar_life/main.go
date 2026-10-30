package main

import (
	"bufio"
	"io"
	"os"
	"strconv"
	"strings"
)

func fail() {
	os.Exit(1)
}

func code(c byte) int {
	switch {
	case c >= '0' && c <= '9':
		return int(c - '0')
	case c >= 'A' && c <= 'C':
		return int(c-'A') + 10
	}
	return -1
}

func parseList(s string) (*[13]bool, bool) {
	var m [13]bool
	prev := -1
	for i := 0; i < len(s); i++ {
		v := code(s[i])
		if v < 0 || v <= prev {
			return nil, false
		}
		m[v] = true
		prev = v
	}
	return &m, true
}

func parseDim(s string) (int, bool) {
	if len(s) == 0 || len(s) > 4 || s[0] == '0' {
		return 0, false
	}
	n := 0
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return 0, false
		}
		n = n*10 + int(s[i]-'0')
	}
	if n < 1 || n > 4096 {
		return 0, false
	}
	return n, true
}

func main() {
	if len(os.Args) != 3 {
		fail()
	}
	rule := os.Args[1]
	if len(rule) < 3 || rule[0] != 'B' {
		fail()
	}
	sl := strings.IndexByte(rule, '/')
	if sl < 0 || sl+1 >= len(rule) || rule[sl+1] != 'S' {
		fail()
	}
	bm, ok1 := parseList(rule[1:sl])
	sm, ok2 := parseList(rule[sl+2:])
	if !ok1 || !ok2 {
		fail()
	}
	gs := os.Args[2]
	if len(gs) == 0 {
		fail()
	}
	gens := 0
	for i := 0; i < len(gs); i++ {
		if gs[i] < '0' || gs[i] > '9' {
			fail()
		}
		if gens <= 1000000 {
			gens = gens*10 + int(gs[i]-'0')
		}
	}
	if gens > 100000 {
		fail()
	}

	data, err := io.ReadAll(bufio.NewReaderSize(os.Stdin, 1<<20))
	if err != nil {
		fail()
	}
	s := string(data)
	if strings.HasSuffix(s, "\n") {
		s = s[:len(s)-1]
	}
	lines := strings.Split(s, "\n")
	hp := strings.Split(lines[0], " ")
	if len(hp) != 2 {
		fail()
	}
	W, ok := parseDim(hp[0])
	if !ok {
		fail()
	}
	H, ok := parseDim(hp[1])
	if !ok {
		fail()
	}
	if len(lines) != H+1 {
		fail()
	}
	cur := make([]uint8, W*H)
	for y := 0; y < H; y++ {
		ln := lines[y+1]
		if len(ln) != W {
			fail()
		}
		for x := 0; x < W; x++ {
			switch ln[x] {
			case 'o':
				cur[y*W+x] = 1
			case '.':
			default:
				fail()
			}
		}
	}

	nxt := make([]uint8, W*H)
	xl := make([]int, W)
	xr := make([]int, W)
	for x := 0; x < W; x++ {
		xl[x] = (x + W - 1) % W
		xr[x] = (x + 1) % W
	}
	out := bufio.NewWriterSize(os.Stdout, 1<<20)
	defer out.Flush()
	// alive indicator rows
	for g := 1; g <= gens; g++ {
		na, ns := 0, 0
		for y := 0; y < H; y++ {
			up := ((y + H - 1) % H) * W
			mid := y * W
			dn := ((y + 1) % H) * W
			for x := 0; x < W; x++ {
				c := cur[mid+x]
				if c == 2 {
					nxt[mid+x] = 0
					continue
				}
				l, r := xl[x], xr[x]
				w := 2*int(cur[up+x]&1+cur[dn+x]&1+cur[mid+l]&1+cur[mid+r]&1) +
					int(cur[up+l]&1+cur[up+r]&1+cur[dn+l]&1+cur[dn+r]&1)
				if c == 1 {
					if sm[w] {
						nxt[mid+x] = 1
						na++
					} else {
						nxt[mid+x] = 2
						ns++
					}
				} else if bm[w] {
					nxt[mid+x] = 1
					na++
				} else {
					nxt[mid+x] = 0
				}
			}
		}
		cur, nxt = nxt, cur
		out.WriteString(strconv.Itoa(g))
		out.WriteByte(' ')
		out.WriteString(strconv.Itoa(na))
		out.WriteByte(' ')
		out.WriteString(strconv.Itoa(ns))
		out.WriteByte('\n')
	}
	chars := [3]byte{'.', 'o', 'x'}
	line := make([]byte, W+1)
	line[W] = '\n'
	for y := 0; y < H; y++ {
		for x := 0; x < W; x++ {
			line[x] = chars[cur[y*W+x]]
		}
		out.Write(line)
	}
}
