package main

import (
	"bufio"
	"io"
	"os"
	"strconv"
)

func weightCode(c byte) (int, bool) {
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

func parseRule(s string) ([13]bool, [13]bool, bool) {
	var born, survive [13]bool
	i := 0
	if i >= len(s) || s[i] != 'B' {
		return born, survive, false
	}
	i++
	prev := -1
	for i < len(s) && s[i] != '/' {
		c, ok := weightCode(s[i])
		if !ok || c <= prev {
			return born, survive, false
		}
		born[c] = true
		prev = c
		i++
	}
	if i >= len(s) || s[i] != '/' {
		return born, survive, false
	}
	i++
	if i >= len(s) || s[i] != 'S' {
		return born, survive, false
	}
	i++
	prev = -1
	for i < len(s) {
		c, ok := weightCode(s[i])
		if !ok || c <= prev {
			return born, survive, false
		}
		survive[c] = true
		prev = c
		i++
	}
	return born, survive, true
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

func parseDim(b []byte) (int, bool) {
	if len(b) == 0 {
		return 0, false
	}
	if len(b) > 1 && b[0] == '0' {
		return 0, false
	}
	v := 0
	for _, c := range b {
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

func parseHeader(line []byte) (int, int, bool) {
	sp := -1
	for i, c := range line {
		if c == ' ' {
			sp = i
			break
		}
	}
	if sp < 0 {
		return 0, 0, false
	}
	w, ok := parseDim(line[:sp])
	if !ok {
		return 0, 0, false
	}
	h, ok := parseDim(line[sp+1:])
	if !ok {
		return 0, 0, false
	}
	return w, h, true
}

func main() {
	if len(os.Args) != 3 {
		os.Exit(1)
	}
	born, survive, ok := parseRule(os.Args[1])
	if !ok {
		os.Exit(1)
	}
	gens, ok := parseGens(os.Args[2])
	if !ok {
		os.Exit(1)
	}

	data, err := io.ReadAll(os.Stdin)
	if err != nil {
		os.Exit(1)
	}
	nl := -1
	for i, c := range data {
		if c == '\n' {
			nl = i
			break
		}
	}
	if nl < 0 {
		os.Exit(1)
	}
	w, h, ok := parseHeader(data[:nl])
	if !ok {
		os.Exit(1)
	}

	pos := nl + 1
	n := w * h
	cur := make([]byte, n)
	for y := 0; y < h; y++ {
		if pos+w > len(data) {
			os.Exit(1)
		}
		base := y * w
		for x := 0; x < w; x++ {
			c := data[pos+x]
			switch c {
			case '.':
				cur[base+x] = 0
			case 'o':
				cur[base+x] = 1
			default:
				os.Exit(1)
			}
		}
		pos += w
		if y < h-1 {
			if pos >= len(data) || data[pos] != '\n' {
				os.Exit(1)
			}
			pos++
		} else {
			if pos == len(data) {
			} else if data[pos] == '\n' && pos+1 == len(data) {
				pos++
			} else {
				os.Exit(1)
			}
		}
	}
	if pos != len(data) {
		os.Exit(1)
	}

	next := make([]byte, n)
	out := bufio.NewWriterSize(os.Stdout, 1<<16)

	for g := 1; g <= gens; g++ {
		aliveCount := 0
		scarCount := 0
		for y := 0; y < h; y++ {
			yUp := y - 1
			if yUp < 0 {
				yUp = h - 1
			}
			yDown := y + 1
			if yDown >= h {
				yDown = 0
			}
			rowUp := yUp * w
			row := y * w
			rowDown := yDown * w
			for x := 0; x < w; x++ {
				xL := x - 1
				if xL < 0 {
					xL = w - 1
				}
				xR := x + 1
				if xR >= w {
					xR = 0
				}
				weight := 0
				if cur[rowUp+xL] == 1 {
					weight++
				}
				if cur[rowUp+x] == 1 {
					weight += 2
				}
				if cur[rowUp+xR] == 1 {
					weight++
				}
				if cur[row+xL] == 1 {
					weight += 2
				}
				if cur[row+xR] == 1 {
					weight += 2
				}
				if cur[rowDown+xL] == 1 {
					weight++
				}
				if cur[rowDown+x] == 1 {
					weight += 2
				}
				if cur[rowDown+xR] == 1 {
					weight++
				}

				idx := row + x
				state := cur[idx]
				var ns byte
				if state == 1 {
					if survive[weight] {
						ns = 1
						aliveCount++
					} else {
						ns = 2
						scarCount++
					}
				} else if state == 0 {
					if born[weight] {
						ns = 1
						aliveCount++
					}
				} else {
					ns = 0
				}
				next[idx] = ns
			}
		}
		cur, next = next, cur

		out.WriteString(strconv.Itoa(g))
		out.WriteByte(' ')
		out.WriteString(strconv.Itoa(aliveCount))
		out.WriteByte(' ')
		out.WriteString(strconv.Itoa(scarCount))
		out.WriteByte('\n')
	}

	for y := 0; y < h; y++ {
		base := y * w
		for x := 0; x < w; x++ {
			switch cur[base+x] {
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
