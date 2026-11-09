package main

import (
	"bufio"
	"bytes"
	"fmt"
	"io"
	"os"
)

func bad(msg string) {
	fmt.Fprintln(os.Stderr, msg)
	os.Exit(1)
}

func isCode(c byte) bool {
	return (c >= '0' && c <= '9') || c == 'A' || c == 'B' || c == 'C'
}

func codeVal(c byte) int {
	if c >= '0' && c <= '9' {
		return int(c - '0')
	}
	return int(c-'A') + 10
}

// parseList reads strictly increasing weight codes starting at index i.
func parseList(s string, i int, set *[13]bool) (int, bool) {
	prev := -1
	for i < len(s) && isCode(s[i]) {
		v := codeVal(s[i])
		if v <= prev {
			return i, false
		}
		set[v] = true
		prev = v
		i++
	}
	return i, true
}

func parseRule(s string) ([13]bool, [13]bool, bool) {
	var b, sv [13]bool
	n := len(s)
	if n == 0 || s[0] != 'B' {
		return b, sv, false
	}
	i, ok := parseList(s, 1, &b)
	if !ok || i >= n || s[i] != '/' {
		return b, sv, false
	}
	i++
	if i >= n || s[i] != 'S' {
		return b, sv, false
	}
	i++
	i, ok = parseList(s, i, &sv)
	if !ok || i != n {
		return b, sv, false
	}
	return b, sv, true
}

func parseGens(s string) (int, bool) {
	if len(s) == 0 {
		return 0, false
	}
	v := 0
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c < '0' || c > '9' {
			return 0, false
		}
		v = v*10 + int(c-'0')
		if v > 100000 {
			return 0, false
		}
	}
	return v, true
}

func parseDim(f string) (int, bool) {
	if len(f) == 0 {
		return 0, false
	}
	if len(f) > 1 && f[0] == '0' {
		return 0, false
	}
	v := 0
	for i := 0; i < len(f); i++ {
		c := f[i]
		if c < '0' || c > '9' {
			return 0, false
		}
		v = v*10 + int(c-'0')
		if v > 4096 {
			return 0, false
		}
	}
	if v < 1 {
		return 0, false
	}
	return v, true
}

func main() {
	args := os.Args[1:]
	if len(args) != 2 {
		bad("usage: prog RULE GENS")
	}
	bset, sset, ok := parseRule(args[0])
	if !ok {
		bad("invalid rule")
	}
	gens, ok := parseGens(args[1])
	if !ok {
		bad("invalid gens")
	}

	data, err := io.ReadAll(os.Stdin)
	if err != nil {
		bad("read error")
	}
	idx := bytes.IndexByte(data, '\n')
	if idx < 0 {
		bad("invalid header")
	}
	header := string(data[:idx])
	fields := bytes.Split([]byte(header), []byte(" "))
	if len(fields) != 2 {
		bad("invalid header")
	}
	W, ok1 := parseDim(string(fields[0]))
	H, ok2 := parseDim(string(fields[1]))
	if !ok1 || !ok2 {
		bad("invalid dimensions")
	}

	rest := data[idx+1:]
	n := H * (W + 1)
	if len(rest) != n && len(rest) != n-1 {
		bad("invalid grid size")
	}
	cur := make([]uint8, W*H)
	for y := 0; y < H; y++ {
		start := y * (W + 1)
		for x := 0; x < W; x++ {
			c := rest[start+x]
			switch c {
			case '.':
				cur[y*W+x] = 0
			case 'o':
				cur[y*W+x] = 1
			default:
				bad("invalid grid character")
			}
		}
		pos := start + W
		if pos >= len(rest) {
			if y != H-1 {
				bad("invalid grid newline")
			}
		} else if rest[pos] != '\n' {
			bad("invalid grid newline")
		}
	}

	xm := make([]int, W)
	xp := make([]int, W)
	for x := 0; x < W; x++ {
		xm[x] = (x - 1 + W) % W
		xp[x] = (x + 1) % W
	}
	ym := make([]int, H)
	yp := make([]int, H)
	for y := 0; y < H; y++ {
		ym[y] = (y - 1 + H) % H
		yp[y] = (y + 1) % H
	}

	out := bufio.NewWriterSize(os.Stdout, 1<<16)
	defer out.Flush()

	nxt := make([]uint8, W*H)

	alive := func(i int) int {
		if cur[i] == 1 {
			return 1
		}
		return 0
	}

	for g := 1; g <= gens; g++ {
		aliveCnt := 0
		scarCnt := 0
		for y := 0; y < H; y++ {
			a := ym[y] * W
			b := y * W
			c := yp[y] * W
			for x := 0; x < W; x++ {
				l := xm[x]
				r := xp[x]
				w := 2*(alive(a+x)+alive(c+x)+alive(b+l)+alive(b+r)) +
					alive(a+l) + alive(a+r) + alive(c+l) + alive(c+r)
				s := cur[b+x]
				var ns uint8
				if s == 1 {
					if sset[w] {
						ns = 1
					} else {
						ns = 2
					}
				} else if s == 2 {
					ns = 0
				} else {
					if bset[w] {
						ns = 1
					} else {
						ns = 0
					}
				}
				nxt[b+x] = ns
				if ns == 1 {
					aliveCnt++
				} else if ns == 2 {
					scarCnt++
				}
			}
		}
		cur, nxt = nxt, cur
		fmt.Fprintf(out, "%d %d %d\n", g, aliveCnt, scarCnt)
	}

	buf := make([]byte, W+1)
	for y := 0; y < H; y++ {
		for x := 0; x < W; x++ {
			switch cur[y*W+x] {
			case 0:
				buf[x] = '.'
			case 1:
				buf[x] = 'o'
			default:
				buf[x] = 'x'
			}
		}
		buf[W] = '\n'
		out.Write(buf)
	}
}
