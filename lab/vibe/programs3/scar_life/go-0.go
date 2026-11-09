package main

import (
	"bufio"
	"fmt"
	"io"
	"os"
)

var birth [13]bool
var survive [13]bool

func codeValue(c byte) (int, bool) {
	switch {
	case c >= '0' && c <= '9':
		return int(c - '0'), true
	case c == 'A':
		return 10, true
	case c == 'B':
		return 11, true
	case c == 'C':
		return 12, true
	}
	return 0, false
}

func parseList(s string, dst *[13]bool) bool {
	prev := -1
	for i := 0; i < len(s); i++ {
		v, ok := codeValue(s[i])
		if !ok || v <= prev {
			return false
		}
		prev = v
		dst[v] = true
	}
	return true
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

func parseDim(s []byte) (int, bool) {
	if len(s) == 0 || len(s) > 4 || s[0] == '0' {
		return 0, false
	}
	v := 0
	for _, c := range s {
		if c < '0' || c > '9' {
			return 0, false
		}
		v = v*10 + int(c-'0')
	}
	if v < 1 || v > 4096 {
		return 0, false
	}
	return v, true
}

func parseGrid(data []byte) (int, int, []byte, bool) {
	nl := -1
	for i := 0; i < len(data); i++ {
		if data[i] == '\n' {
			nl = i
			break
		}
	}
	if nl < 0 {
		return 0, 0, nil, false
	}
	header := data[:nl]
	sp := -1
	for i := 0; i < len(header); i++ {
		if header[i] == ' ' {
			sp = i
			break
		}
	}
	if sp < 0 {
		return 0, 0, nil, false
	}
	W, ok := parseDim(header[:sp])
	if !ok {
		return 0, 0, nil, false
	}
	H, ok := parseDim(header[sp+1:])
	if !ok {
		return 0, 0, nil, false
	}

	grid := make([]byte, W*H)
	pos := nl + 1
	for r := 0; r < H; r++ {
		for c := 0; c < W; c++ {
			if pos >= len(data) {
				return 0, 0, nil, false
			}
			switch data[pos] {
			case 'o':
				grid[r*W+c] = 1
			case '.':
				grid[r*W+c] = 0
			default:
				return 0, 0, nil, false
			}
			pos++
		}
		if r < H-1 {
			if pos >= len(data) || data[pos] != '\n' {
				return 0, 0, nil, false
			}
			pos++
		} else if pos < len(data) {
			if data[pos] != '\n' {
				return 0, 0, nil, false
			}
			pos++
			if pos != len(data) {
				return 0, 0, nil, false
			}
		}
	}
	return W, H, grid, true
}

func main() {
	args := os.Args[1:]
	if len(args) != 2 {
		os.Exit(1)
	}

	rule := args[0]
	if len(rule) < 2 || rule[0] != 'B' {
		os.Exit(1)
	}
	slash := -1
	for i := 1; i < len(rule); i++ {
		if rule[i] == '/' {
			slash = i
			break
		}
	}
	if slash < 0 || slash+1 >= len(rule) || rule[slash+1] != 'S' {
		os.Exit(1)
	}
	if !parseList(rule[1:slash], &birth) {
		os.Exit(1)
	}
	if !parseList(rule[slash+2:], &survive) {
		os.Exit(1)
	}

	gens, ok := parseGens(args[1])
	if !ok {
		os.Exit(1)
	}

	data, err := io.ReadAll(os.Stdin)
	if err != nil {
		os.Exit(1)
	}
	W, H, cur, ok := parseGrid(data)
	if !ok {
		os.Exit(1)
	}

	prevR := make([]int, H)
	nextR := make([]int, H)
	for r := 0; r < H; r++ {
		p := r - 1
		if p < 0 {
			p = H - 1
		}
		n := r + 1
		if n >= H {
			n = 0
		}
		prevR[r] = p
		nextR[r] = n
	}
	prevC := make([]int, W)
	nextC := make([]int, W)
	for c := 0; c < W; c++ {
		p := c - 1
		if p < 0 {
			p = W - 1
		}
		n := c + 1
		if n >= W {
			n = 0
		}
		prevC[c] = p
		nextC[c] = n
	}

	nxt := make([]byte, W*H)
	out := bufio.NewWriterSize(os.Stdout, 1<<16)

	for g := 1; g <= gens; g++ {
		aliveN, scarN := 0, 0
		for r := 0; r < H; r++ {
			rb := r * W
			ru := prevR[r] * W
			rd := nextR[r] * W
			for c := 0; c < W; c++ {
				lf := prevC[c]
				rt := nextC[c]
				wt := 0
				if cur[ru+c] == 1 {
					wt += 2
				}
				if cur[rd+c] == 1 {
					wt += 2
				}
				if cur[rb+lf] == 1 {
					wt += 2
				}
				if cur[rb+rt] == 1 {
					wt += 2
				}
				if cur[ru+lf] == 1 {
					wt++
				}
				if cur[ru+rt] == 1 {
					wt++
				}
				if cur[rd+lf] == 1 {
					wt++
				}
				if cur[rd+rt] == 1 {
					wt++
				}

				i := rb + c
				switch cur[i] {
				case 1:
					if survive[wt] {
						nxt[i] = 1
						aliveN++
					} else {
						nxt[i] = 2
						scarN++
					}
				case 0:
					if birth[wt] {
						nxt[i] = 1
						aliveN++
					} else {
						nxt[i] = 0
					}
				default:
					nxt[i] = 0
				}
			}
		}
		fmt.Fprintf(out, "%d %d %d\n", g, aliveN, scarN)
		cur, nxt = nxt, cur
	}

	for r := 0; r < H; r++ {
		for c := 0; c < W; c++ {
			switch cur[r*W+c] {
			case 1:
				out.WriteByte('o')
			case 2:
				out.WriteByte('x')
			default:
				out.WriteByte('.')
			}
		}
		out.WriteByte('\n')
	}
	out.Flush()
}
