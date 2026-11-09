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

func parseCodes(s string, mask *[13]bool) bool {
	prev := -1
	for i := 0; i < len(s); i++ {
		c := s[i]
		var v int
		switch {
		case c >= '0' && c <= '9':
			v = int(c - '0')
		case c >= 'A' && c <= 'C':
			v = int(c-'A') + 10
		default:
			return false
		}
		if v <= prev {
			return false
		}
		prev = v
		mask[v] = true
	}
	return true
}

func al(v byte) int {
	return int(v & 1)
}

func parseNum(s string, lo, hi int) (int, bool) {
	if len(s) == 0 {
		return 0, false
	}
	if len(s) > 1 && s[0] == '0' {
		return 0, false
	}
	v := 0
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c < '0' || c > '9' {
			return 0, false
		}
		v = v*10 + int(c-'0')
		if v > hi {
			return 0, false
		}
	}
	if v < lo {
		return 0, false
	}
	return v, true
}

func main() {
	if len(os.Args) != 3 {
		fail()
	}
	rule := os.Args[1]
	gensStr := os.Args[2]

	if !strings.HasPrefix(rule, "B") {
		fail()
	}
	idx := strings.IndexByte(rule, '/')
	if idx < 0 {
		fail()
	}
	bpart := rule[1:idx]
	rest := rule[idx+1:]
	if !strings.HasPrefix(rest, "S") {
		fail()
	}
	spart := rest[1:]
	var born, surv [13]bool
	if !parseCodes(bpart, &born) {
		fail()
	}
	if !parseCodes(spart, &surv) {
		fail()
	}

	if len(gensStr) == 0 {
		fail()
	}
	gens := 0
	for i := 0; i < len(gensStr); i++ {
		c := gensStr[i]
		if c < '0' || c > '9' {
			fail()
		}
		gens = gens*10 + int(c-'0')
		if gens > 100000 {
			fail()
		}
	}

	data, err := io.ReadAll(os.Stdin)
	if err != nil {
		fail()
	}
	hi := strings.IndexByte(string(data), '\n')
	if hi < 0 {
		fail()
	}
	header := string(data[:hi])
	parts := strings.Split(header, " ")
	if len(parts) != 2 {
		fail()
	}
	W, ok := parseNum(parts[0], 1, 4096)
	if !ok {
		fail()
	}
	H, ok := parseNum(parts[1], 1, 4096)
	if !ok {
		fail()
	}

	N := W * H
	cur := make([]byte, N)
	nxt := make([]byte, N)
	pos := hi + 1
	for y := 0; y < H; y++ {
		if pos+W > len(data) {
			fail()
		}
		for x := 0; x < W; x++ {
			c := data[pos+x]
			switch c {
			case '.':
				cur[y*W+x] = 0
			case 'o':
				cur[y*W+x] = 1
			default:
				fail()
			}
		}
		pos += W
		if y < H-1 {
			if pos >= len(data) || data[pos] != '\n' {
				fail()
			}
			pos++
		} else {
			if pos < len(data) && data[pos] == '\n' {
				pos++
			}
			if pos != len(data) {
				fail()
			}
		}
	}

	xl := make([]int, W)
	xr := make([]int, W)
	for x := 0; x < W; x++ {
		xl[x] = (x - 1 + W) % W
		xr[x] = (x + 1) % W
	}
	yu := make([]int, H)
	yd := make([]int, H)
	for y := 0; y < H; y++ {
		yu[y] = (y - 1 + H) % H
		yd[y] = (y + 1) % H
	}

	out := bufio.NewWriterSize(os.Stdout, 1<<16)
	defer out.Flush()

	for g := 1; g <= gens; g++ {
		alive, scars := 0, 0
		for y := 0; y < H; y++ {
			rowU := yu[y] * W
			rowD := yd[y] * W
			rowC := y * W
			for x := 0; x < W; x++ {
				l := xl[x]
				r := xr[x]
				w := 2*(al(cur[rowC+l])+al(cur[rowC+r])+al(cur[rowU+x])+al(cur[rowD+x])) +
					al(cur[rowU+l]) + al(cur[rowU+r]) + al(cur[rowD+l]) + al(cur[rowD+r])
				s := cur[rowC+x]
				var ns byte
				switch s {
				case 1:
					if surv[w] {
						ns = 1
					} else {
						ns = 2
					}
				case 0:
					if born[w] {
						ns = 1
					}
				case 2:
					ns = 0
				}
				nxt[rowC+x] = ns
				if ns == 1 {
					alive++
				} else if ns == 2 {
					scars++
				}
			}
		}
		cur, nxt = nxt, cur
		out.WriteString(strconv.Itoa(g))
		out.WriteByte(' ')
		out.WriteString(strconv.Itoa(alive))
		out.WriteByte(' ')
		out.WriteString(strconv.Itoa(scars))
		out.WriteByte('\n')
	}

	line := make([]byte, W+1)
	line[W] = '\n'
	for y := 0; y < H; y++ {
		for x := 0; x < W; x++ {
			switch cur[y*W+x] {
			case 0:
				line[x] = '.'
			case 1:
				line[x] = 'o'
			default:
				line[x] = 'x'
			}
		}
		out.Write(line)
	}
}
