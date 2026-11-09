package main

import (
	"bufio"
	"fmt"
	"math/bits"
	"os"
	"slices"
)

type ship struct {
	id, arrival, cargo, op int32
	start                  int64
	berth                  int16
	size, prio             uint8
}

var ships []ship
var rd *bufio.Reader

func readInt() int64 {
	n := int64(0)
	c, err := rd.ReadByte()
	for err == nil && (c < '0' || c > '9') {
		c, err = rd.ReadByte()
	}
	for err == nil && c >= '0' && c <= '9' {
		n = n*10 + int64(c-'0')
		c, err = rd.ReadByte()
	}
	return n
}

func less(i, j int32) bool {
	a := &ships[i]
	b := &ships[j]
	if a.prio != b.prio {
		return a.prio < b.prio
	}
	if a.arrival != b.arrival {
		return a.arrival < b.arrival
	}
	return a.id < b.id
}

func hpush(h *[]int32, x int32) {
	*h = append(*h, x)
	a := *h
	k := len(a) - 1
	for k > 0 {
		p := (k - 1) / 2
		if !less(a[k], a[p]) {
			break
		}
		a[k], a[p] = a[p], a[k]
		k = p
	}
}

func hpop(h *[]int32) int32 {
	a := *h
	top := a[0]
	n := len(a) - 1
	a[0] = a[n]
	a = a[:n]
	k := 0
	for {
		l := 2*k + 1
		if l >= n {
			break
		}
		m := l
		if r := l + 1; r < n && less(a[r], a[l]) {
			m = r
		}
		if !less(a[m], a[k]) {
			break
		}
		a[k], a[m] = a[m], a[k]
		k = m
	}
	*h = a
	return top
}

type dep struct {
	t int64
	b int16
}

var depH []dep

func dpush(x dep) {
	depH = append(depH, x)
	k := len(depH) - 1
	for k > 0 {
		p := (k - 1) / 2
		if depH[p].t <= depH[k].t {
			break
		}
		depH[p], depH[k] = depH[k], depH[p]
		k = p
	}
}

func dpop() dep {
	top := depH[0]
	n := len(depH) - 1
	depH[0] = depH[n]
	depH = depH[:n]
	k := 0
	for {
		l := 2*k + 1
		if l >= n {
			break
		}
		m := l
		if r := l + 1; r < n && depH[r].t < depH[l].t {
			m = r
		}
		if depH[k].t <= depH[m].t {
			break
		}
		depH[k], depH[m] = depH[m], depH[k]
		k = m
	}
	return top
}

var wait [4][]int32

func fitCount(c int) int {
	f := 0
	for z := 1; z <= c; z++ {
		f += len(wait[z])
	}
	return f
}

func main() {
	rd = bufio.NewReaderSize(os.Stdin, 1<<20)
	B := int(readInt())
	S := int(readInt())
	classes := make([]int, B)
	rates := make([]int64, B)
	for i := 0; i < B; i++ {
		classes[i] = int(readInt())
		rates[i] = readInt()
	}
	ships = make([]ship, S)
	for i := 0; i < S; i++ {
		ships[i].id = int32(readInt())
		ships[i].arrival = int32(readInt())
		ships[i].size = uint8(readInt())
		ships[i].cargo = int32(readInt())
		ships[i].prio = uint8(readInt())
		ships[i].op = int32(readInt())
	}

	slices.SortFunc(ships, func(a, b ship) int {
		if a.arrival < b.arrival {
			return -1
		}
		if a.arrival > b.arrival {
			return 1
		}
		return 0
	})

	words := (B + 63) / 64
	var freeBits [4][]uint64
	for c := 1; c <= 3; c++ {
		freeBits[c] = make([]uint64, words)
	}
	for b := 0; b < B; b++ {
		freeBits[classes[b]][b>>6] |= uint64(1) << uint(b&63)
	}
	lastOp := make([]int64, B)
	for i := range lastOp {
		lastOp[i] = -1
	}
	busy := make([]int64, B)
	served := make([]int64, B)
	var makespan int64

	ai := 0
	total := 0
	for ai < S || len(depH) > 0 {
		var t int64 = -1
		if ai < S {
			t = int64(ships[ai].arrival)
		}
		if len(depH) > 0 && (t < 0 || depH[0].t < t) {
			t = depH[0].t
		}
		// departures
		for len(depH) > 0 && depH[0].t <= t {
			d := dpop()
			b := int(d.b)
			freeBits[classes[b]][b>>6] |= uint64(1) << uint(b&63)
		}
		// arrivals
		for ai < S && int64(ships[ai].arrival) == t {
			z := ships[ai].size
			hpush(&wait[z], int32(ai))
			total++
			ai++
		}
		// assignment
		if total > 0 {
			for c := 1; c <= 3 && total > 0; c++ {
				fb := freeBits[c]
				for w := 0; w < len(fb); w++ {
					for fitCount(c) > 0 && fb[w] != 0 {
						bit := bits.TrailingZeros64(fb[w])
						b := w*64 + bit
						bestIdx := int32(-1)
						bz := 0
						for z := 1; z <= c; z++ {
							if len(wait[z]) > 0 {
								cand := wait[z][0]
								if bestIdx < 0 || less(cand, bestIdx) {
									bestIdx = cand
									bz = z
								}
							}
						}
						fb[w] &^= uint64(1) << uint(bit)
						hpop(&wait[bz])
						total--
						p := &ships[bestIdx]
						var setup int64 = 4
						if lastOp[b] == int64(p.op) {
							setup = 1
						}
						lastOp[b] = int64(p.op)
						svc := (int64(p.cargo)+rates[b]-1)/rates[b] + setup
						p.start = t
						p.berth = int16(b)
						busy[b] += svc
						served[b]++
						end := t + svc
						if end > makespan {
							makespan = end
						}
						dpush(dep{end, int16(b)})
					}
				}
			}
		}
	}

	slices.SortFunc(ships, func(a, b ship) int {
		if a.id < b.id {
			return -1
		}
		if a.id > b.id {
			return 1
		}
		return 0
	})

	var W int64
	X := int64(-1)
	I := int64(-1)
	g := int64(0)
	for i := range ships {
		p := &ships[i]
		wt := p.start - int64(p.arrival)
		W += wt
		if wt > X {
			X = wt
			I = int64(p.id)
		}
		g = (g*1000003 + p.start*31 + int64(p.berth)) % 1000000007
	}
	if S == 0 {
		X = 0
		I = -1
	}

	out := bufio.NewWriter(os.Stdout)
	defer out.Flush()
	fmt.Fprintf(out, "ships %d\n", S)
	fmt.Fprintf(out, "makespan %d\n", makespan)
	fmt.Fprintf(out, "wait total %d max %d ship %d\n", W, X, I)
	for b := 0; b < B; b++ {
		fmt.Fprintf(out, "berth %d ships %d busy %d\n", b, served[b], busy[b])
	}
	fmt.Fprintf(out, "digest %d\n", g)
}
