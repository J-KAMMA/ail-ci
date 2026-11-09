package main

import (
	"bufio"
	"os"
	"slices"
	"strconv"
)

type item struct {
	t int64
	b int32
	n int32
}

func less(a, b item) bool {
	return a.t < b.t || (a.t == b.t && a.b < b.b)
}

type heapT struct {
	h []item
}

func (hp *heapT) push(it item) {
	hp.h = append(hp.h, it)
	i := len(hp.h) - 1
	for i > 0 {
		p := (i - 1) / 2
		if !less(hp.h[i], hp.h[p]) {
			break
		}
		hp.h[i], hp.h[p] = hp.h[p], hp.h[i]
		i = p
	}
}

func (hp *heapT) pop() item {
	top := hp.h[0]
	last := len(hp.h) - 1
	hp.h[0] = hp.h[last]
	hp.h = hp.h[:last]
	i := 0
	n := len(hp.h)
	for {
		l := 2*i + 1
		if l >= n {
			break
		}
		m := l
		if r := l + 1; r < n && less(hp.h[r], hp.h[l]) {
			m = r
		}
		if !less(hp.h[m], hp.h[i]) {
			break
		}
		hp.h[i], hp.h[m] = hp.h[m], hp.h[i]
		i = m
	}
	return top
}

func main() {
	rd := bufio.NewReaderSize(os.Stdin, 1<<20)
	w := bufio.NewWriterSize(os.Stdout, 1<<20)
	defer w.Flush()

	readInt := func() int {
		c, err := rd.ReadByte()
		for err == nil && (c < '0' || c > '9') {
			c, err = rd.ReadByte()
		}
		x := 0
		for err == nil && c >= '0' && c <= '9' {
			x = x*10 + int(c-'0')
			c, err = rd.ReadByte()
		}
		return x
	}

	N := readInt()
	M := readInt()
	Q := readInt()

	X := make([]int64, N)
	for i := 0; i < N; i++ {
		X[i] = int64(readInt())
	}

	E := 2 * M
	Tarr := make([]int64, M)
	keys := make([]uint64, E)
	for i := 0; i < M; i++ {
		u := readInt()
		v := readInt()
		l := readInt()
		t := readInt()
		Tarr[i] = int64(t)
		e0 := 2 * i
		e1 := 2*i + 1
		keys[e0] = uint64(u)<<38 | uint64(l)<<21 | uint64(e0)
		keys[e1] = uint64(v)<<38 | uint64(l)<<21 | uint64(e1)
	}
	slices.Sort(keys)

	const mask = (1 << 21) - 1
	rid := make([]int32, E)
	sortedE := make([]int32, E)
	grpStart := make([]int32, 0, E+1)
	rstation := make([]int32, 0)
	K := 0
	var prevGk uint64
	for p, k := range keys {
		e := k & mask
		gk := k >> 21
		if p == 0 || gk != prevGk {
			grpStart = append(grpStart, int32(p))
			rstation = append(rstation, int32(gk>>17))
			K++
			prevGk = gk
		}
		rid[e] = int32(K - 1)
		sortedE[p] = int32(e)
	}
	grpStart = append(grpStart, int32(E))

	adjTo := make([]int32, E)
	adjW := make([]int64, E)
	for p := 0; p < E; p++ {
		e := int(sortedE[p])
		adjTo[p] = rid[e^1]
		adjW[p] = Tarr[e>>1]
	}

	cnt := make([]int32, N)
	for r := 0; r < K; r++ {
		cnt[rstation[r]]++
	}
	stFirst := make([]int32, N+1)
	for v := 0; v < N; v++ {
		stFirst[v+1] = stFirst[v] + cnt[v]
	}

	total := K + N
	stamp := make([]int32, total)
	done := make([]int32, total)
	dt := make([]int64, total)
	db := make([]int32, total)
	hp := &heapT{}

	var cur int32 = 0
	outBuf := make([]byte, 0, 64)

	for q := 0; q < Q; q++ {
		S := readInt()
		D := readInt()
		if S == D {
			w.WriteString("0 0\n")
			continue
		}
		cur++
		hp.h = hp.h[:0]

		relax := func(n int, t int64, b int32) {
			if stamp[n] != cur || t < dt[n] || (t == dt[n] && b < db[n]) {
				stamp[n] = cur
				dt[n] = t
				db[n] = b
				hp.push(item{t, b, int32(n)})
			}
		}

		for r := int(stFirst[S]); r < int(stFirst[S+1]); r++ {
			relax(r, 0, 1)
		}

		target := K + D
		found := false
		var ansT int64
		var ansB int32
		for len(hp.h) > 0 {
			it := hp.pop()
			n := int(it.n)
			if stamp[n] != cur || it.t != dt[n] || it.b != db[n] {
				continue
			}
			if done[n] == cur {
				continue
			}
			done[n] = cur
			if n == target {
				found = true
				ansT = it.t
				ansB = it.b
				break
			}
			if n < K {
				for p := grpStart[n]; p < grpStart[n+1]; p++ {
					relax(int(adjTo[p]), it.t+adjW[p], it.b)
				}
				v := int(rstation[n])
				relax(K+v, it.t, it.b)
			} else {
				v := n - K
				for r := int(stFirst[v]); r < int(stFirst[v+1]); r++ {
					relax(r, it.t+X[v], it.b+1)
				}
			}
		}

		if found {
			outBuf = outBuf[:0]
			outBuf = strconv.AppendInt(outBuf, ansT, 10)
			outBuf = append(outBuf, ' ')
			outBuf = strconv.AppendInt(outBuf, int64(ansB), 10)
			outBuf = append(outBuf, '\n')
			w.Write(outBuf)
		} else {
			w.WriteString("none\n")
		}
	}
}
