package main

import (
	"bufio"
	"fmt"
	"io"
	"os"
)

const (
	open = byte('.')
	wall = byte('#')
)

func nextLine(data []byte, pos *int) ([]byte, bool) {
	if *pos >= len(data) {
		return nil, false
	}
	start := *pos
	p := start
	for p < len(data) && data[p] != '\n' {
		p++
	}
	line := data[start:p]
	if p < len(data) {
		p++
	}
	*pos = p
	return line, true
}

func parseUint(s []byte, idx *int) (int64, bool) {
	n := len(s)
	i := *idx
	if i >= n || s[i] < '0' || s[i] > '9' {
		return 0, false
	}
	var v int64
	for i < n {
		c := s[i]
		if c < '0' || c > '9' {
			break
		}
		v = v*10 + int64(c-'0')
		if v > 100000000 {
			return 0, false
		}
		i++
	}
	*idx = i
	return v, true
}

func main() {
	data, _ := io.ReadAll(os.Stdin)
	pos := 0

	header, ok := nextLine(data, &pos)
	if !ok {
		os.Exit(2)
	}
	idx := 0
	h, ok := parseUint(header, &idx)
	if !ok || idx >= len(header) || header[idx] != ' ' {
		os.Exit(2)
	}
	idx++
	w, ok := parseUint(header, &idx)
	if !ok || idx >= len(header) || header[idx] != ' ' {
		os.Exit(2)
	}
	idx++
	q, ok := parseUint(header, &idx)
	if !ok || idx != len(header) {
		os.Exit(2)
	}
	if h < 1 || h > 2000 || w < 1 || w > 2000 || q < 0 || q > 20 {
		os.Exit(2)
	}
	H := int(h)
	W := int(w)
	Q := int(q)
	n := H * W

	grid := make([]byte, n)
	for r := 0; r < H; r++ {
		line, ok := nextLine(data, &pos)
		if !ok || len(line) != W {
			os.Exit(2)
		}
		for j := 0; j < W; j++ {
			if line[j] != open && line[j] != wall {
				os.Exit(2)
			}
			grid[r*W+j] = line[j]
		}
	}

	qs := make([]int, 0, Q)
	qt := make([]int, 0, Q)
	for k := 0; k < Q; k++ {
		line, ok := nextLine(data, &pos)
		if !ok {
			os.Exit(2)
		}
		i := 0
		r1, a := parseUint(line, &i)
		if !a || i >= len(line) || line[i] != ' ' {
			os.Exit(2)
		}
		i++
		c1, a := parseUint(line, &i)
		if !a || i >= len(line) || line[i] != ' ' {
			os.Exit(2)
		}
		i++
		r2, a := parseUint(line, &i)
		if !a || i >= len(line) || line[i] != ' ' {
			os.Exit(2)
		}
		i++
		c2, a := parseUint(line, &i)
		if !a || i != len(line) {
			os.Exit(2)
		}
		if r1 < 0 || r1 >= h || c1 < 0 || c1 >= w || r2 < 0 || r2 >= h || c2 < 0 || c2 >= w {
			os.Exit(2)
		}
		qs = append(qs, int(r1)*W+int(c1))
		qt = append(qt, int(r2)*W+int(c2))
	}
	if _, ok := nextLine(data, &pos); ok {
		os.Exit(2)
	}

	out := bufio.NewWriter(os.Stdout)
	defer out.Flush()
	dist := make([]int32, n)
	queue := make([]int32, n)
	var total int64
	for k := 0; k < Q; k++ {
		s := qs[k]
		t := qt[k]
		if grid[s] == wall || grid[t] == wall {
			fmt.Fprintln(out, "dist -1 seen 0")
			continue
		}
		for i := range dist {
			dist[i] = -1
		}
		head := 0
		tail := 1
		queue[0] = int32(s)
		dist[s] = 0
		seen := 0
		d := int32(-1)
		for head < tail {
			v := int(queue[head])
			head++
			seen++
			if v == t {
				d = dist[v]
				break
			}
			nd := dist[v] + 1
			rr := v / W
			cc := v - rr*W
			if rr > 0 {
				u := v - W
				if grid[u] == open && dist[u] == -1 {
					dist[u] = nd
					queue[tail] = int32(u)
					tail++
				}
			}
			if rr+1 < H {
				u := v + W
				if grid[u] == open && dist[u] == -1 {
					dist[u] = nd
					queue[tail] = int32(u)
					tail++
				}
			}
			if cc > 0 {
				u := v - 1
				if grid[u] == open && dist[u] == -1 {
					dist[u] = nd
					queue[tail] = int32(u)
					tail++
				}
			}
			if cc+1 < W {
				u := v + 1
				if grid[u] == open && dist[u] == -1 {
					dist[u] = nd
					queue[tail] = int32(u)
					tail++
				}
			}
		}
		fmt.Fprintf(out, "dist %d seen %d\n", d, seen)
		if d != -1 {
			total += int64(d)
		}
	}
	fmt.Fprintf(out, "total %d\n", total)
}
