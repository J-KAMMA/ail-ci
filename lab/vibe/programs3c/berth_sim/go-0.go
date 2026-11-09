package main

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"slices"
)

const MOD = 1000000007
const mask22 = 1<<22 - 1

type reader struct {
	r      io.Reader
	buf    []byte
	pos, n int
	eof    bool
}

func (rd *reader) next() (byte, bool) {
	for rd.pos == rd.n {
		if rd.eof {
			return 0, false
		}
		n, err := rd.r.Read(rd.buf)
		rd.pos, rd.n = 0, n
		if err != nil {
			rd.eof = true
		}
	}
	b := rd.buf[rd.pos]
	rd.pos++
	return b, true
}

func (rd *reader) readInt() int64 {
	var c byte
	var ok bool
	for {
		c, ok = rd.next()
		if !ok {
			return 0
		}
		if c >= '0' && c <= '9' {
			break
		}
	}
	v := int64(c - '0')
	for {
		c, ok = rd.next()
		if !ok || c < '0' || c > '9' {
			break
		}
		v = v*10 + int64(c-'0')
	}
	return v
}

var id, arr, cargo, op []int32
var size, pri []uint8

func keyOf(i int32) uint64 {
	return uint64(pri[i])<<60 | uint64(arr[i])<<30 | uint64(id[i])
}

func qpush(h *[]int32, x int32) {
	a := append(*h, x)
	k := len(a) - 1
	for k > 0 {
		p := (k - 1) / 2
		if keyOf(a[p]) <= keyOf(a[k]) {
			break
		}
		a[p], a[k] = a[k], a[p]
		k = p
	}
	*h = a
}

func qpop(h *[]int32) int32 {
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
		if r := l + 1; r < n && keyOf(a[r]) < keyOf(a[l]) {
			m = r
		}
		if keyOf(a[k]) <= keyOf(a[m]) {
			break
		}
		a[k], a[m] = a[m], a[k]
		k = m
	}
	*h = a
	return top
}

func hpush(h *[]uint64, x uint64) {
	a := append(*h, x)
	k := len(a) - 1
	for k > 0 {
		p := (k - 1) / 2
		if a[p] <= a[k] {
			break
		}
		a[p], a[k] = a[k], a[p]
		k = p
	}
	*h = a
}

func hpop(h *[]uint64) uint64 {
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
		if r := l + 1; r < n && a[r] < a[l] {
			m = r
		}
		if a[k] <= a[m] {
			break
		}
		a[k], a[m] = a[m], a[k]
		k = m
	}
	*h = a
	return top
}

func main() {
	rd := &reader{r: os.Stdin, buf: make([]byte, 1<<16)}
	B := int(rd.readInt())
	S := int(rd.readInt())
	class := make([]int, B)
	rate := make([]int64, B)
	for b := 0; b < B; b++ {
		class[b] = int(rd.readInt())
		rate[b] = rd.readInt()
	}
	id = make([]int32, S)
	arr = make([]int32, S)
	cargo = make([]int32, S)
	op = make([]int32, S)
	size = make([]uint8, S)
	pri = make([]uint8, S)
	for i := 0; i < S; i++ {
		id[i] = int32(rd.readInt())
		arr[i] = int32(rd.readInt())
		size[i] = uint8(rd.readInt())
		cargo[i] = int32(rd.readInt())
		pri[i] = uint8(rd.readInt())
		op[i] = int32(rd.readInt())
	}

	ord := make([]uint64, S)
	for i := 0; i < S; i++ {
		ord[i] = uint64(arr[i])<<22 | uint64(i)
	}
	slices.Sort(ord)

	start := make([]int64, S)
	berthOf := make([]int16, S)
	lastOp := make([]int64, B)
	for b := range lastOp {
		lastOp[b] = -1
	}
	busy := make([]int64, B)
	cnt := make([]int64, B)

	var q [4][]int32
	var freeH [4][]uint64
	for b := 0; b < B; b++ {
		hpush(&freeH[class[b]], uint64(b))
	}
	var dep []uint64
	var makespan int64

	ai := 0
	for ai < S || len(dep) > 0 {
		var t int64 = -1
		if ai < S {
			t = int64(ord[ai] >> 22)
		}
		if len(dep) > 0 {
			dt := int64(dep[0] >> 11)
			if t < 0 || dt < t {
				t = dt
			}
		}
		// departures
		for len(dep) > 0 && int64(dep[0]>>11) == t {
			x := hpop(&dep)
			b := x & 2047
			hpush(&freeH[class[b]], b)
		}
		// arrivals
		for ai < S && int64(ord[ai]>>22) == t {
			idx := int32(ord[ai] & mask22)
			qpush(&q[size[idx]], idx)
			ai++
		}
		// assignment
		for c := 1; c <= 3; c++ {
			for len(freeH[c]) > 0 {
				best := 0
				var bk uint64
				for z := 1; z <= c; z++ {
					if len(q[z]) > 0 {
						k := keyOf(q[z][0])
						if best == 0 || k < bk {
							best = z
							bk = k
						}
					}
				}
				if best == 0 {
					break
				}
				idx := qpop(&q[best])
				b := int(hpop(&freeH[c]))
				r := rate[b]
				svc := (int64(cargo[idx]) + r - 1) / r
				var setup int64 = 4
				if lastOp[b] == int64(op[idx]) {
					setup = 1
				}
				lastOp[b] = int64(op[idx])
				svc += setup
				start[idx] = t
				berthOf[idx] = int16(b)
				end := t + svc
				busy[b] += svc
				cnt[b]++
				hpush(&dep, uint64(end)<<11|uint64(b))
				if end > makespan {
					makespan = end
				}
			}
		}
	}

	var W uint64
	var X int64 = -1
	var I int64 = -1
	for i := 0; i < S; i++ {
		w := start[i] - int64(arr[i])
		W += uint64(w)
		if w > X || (w == X && int64(id[i]) < I) {
			X = w
			I = int64(id[i])
		}
	}
	if S == 0 {
		X = 0
		I = -1
	}

	for i := 0; i < S; i++ {
		ord[i] = uint64(id[i])<<22 | uint64(i)
	}
	slices.Sort(ord)
	var g int64
	for _, v := range ord {
		i := v & mask22
		g = (g*1000003 + start[i]*31 + int64(berthOf[i])) % MOD
	}

	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()
	fmt.Fprintf(w, "ships %d\n", S)
	fmt.Fprintf(w, "makespan %d\n", makespan)
	fmt.Fprintf(w, "wait total %d max %d ship %d\n", W, X, I)
	for b := 0; b < B; b++ {
		fmt.Fprintf(w, "berth %d ships %d busy %d\n", b, cnt[b], busy[b])
	}
	fmt.Fprintf(w, "digest %d\n", g)
}
