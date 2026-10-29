package main

import (
	"bufio"
	"io"
	"os"
	"runtime"
	"slices"
	"strconv"
	"sync"
	"sync/atomic"
)

type item struct {
	t  int64
	b  int32
	id int32
}

func less(a, b item) bool {
	return a.t < b.t || (a.t == b.t && a.b < b.b)
}

type heap struct{ a []item }

func (h *heap) push(x item) {
	h.a = append(h.a, x)
	i := len(h.a) - 1
	for i > 0 {
		p := (i - 1) >> 1
		if !less(x, h.a[p]) {
			break
		}
		h.a[i] = h.a[p]
		i = p
	}
	h.a[i] = x
}

func (h *heap) pop() item {
	top := h.a[0]
	n := len(h.a) - 1
	x := h.a[n]
	h.a = h.a[:n]
	if n > 0 {
		i := 0
		for {
			c := 2*i + 1
			if c >= n {
				break
			}
			if c+1 < n && less(h.a[c+1], h.a[c]) {
				c++
			}
			if !less(h.a[c], x) {
				break
			}
			h.a[i] = h.a[c]
			i = c
		}
		h.a[i] = x
	}
	return top
}

const INF = int64(1<<63 - 1)

func main() {
	data, _ := io.ReadAll(os.Stdin)
	pos := 0
	next := func() int {
		for pos < len(data) && (data[pos] < '0' || data[pos] > '9') {
			pos++
		}
		v := 0
		for pos < len(data) && data[pos] >= '0' && data[pos] <= '9' {
			v = v*10 + int(data[pos]-'0')
			pos++
		}
		return v
	}
	N := next()
	M := next()
	Q := next()
	X := make([]int32, N)
	for i := range X {
		X[i] = int32(next())
	}
	eu := make([]int32, 0, M)
	ev := make([]int32, 0, M)
	el := make([]int32, 0, M)
	et := make([]int32, 0, M)
	for i := 0; i < M; i++ {
		u, v, l, t := next(), next(), next(), next()
		if u == v {
			continue
		}
		eu = append(eu, int32(u))
		ev = append(ev, int32(v))
		el = append(el, int32(l))
		et = append(et, int32(t))
	}
	M = len(eu)
	keys := make([]uint64, 2*M)
	for e := 0; e < M; e++ {
		keys[2*e] = (uint64(eu[e])<<17|uint64(el[e]))<<22 | uint64(2*e)
		keys[2*e+1] = (uint64(ev[e])<<17|uint64(el[e]))<<22 | uint64(2*e+1)
	}
	slices.Sort(keys)
	nodeOf := make([]int32, 2*M)
	hs := make([]int32, N+1)
	var stn []int32
	K := int32(0)
	var prev uint64 = ^uint64(0)
	for _, k := range keys {
		kk := k >> 22
		if kk != prev {
			prev = kk
			stn = append(stn, int32(kk>>17))
			K++
		}
		nodeOf[k&(1<<22-1)] = K - 1
	}
	keys = nil
	// hub ranges
	{
		cnt := make([]int32, N+1)
		for _, s := range stn {
			cnt[s+1]++
		}
		for i := 0; i < N; i++ {
			cnt[i+1] += cnt[i]
		}
		copy(hs, cnt)
	}
	// CSR adjacency
	adjStart := make([]int32, K+1)
	for e := 0; e < M; e++ {
		adjStart[nodeOf[2*e]+1]++
		adjStart[nodeOf[2*e+1]+1]++
	}
	for i := int32(0); i < K; i++ {
		adjStart[i+1] += adjStart[i]
	}
	fill := make([]int32, K)
	adjTo := make([]int32, 2*M)
	adjT := make([]int32, 2*M)
	for e := 0; e < M; e++ {
		a, b := nodeOf[2*e], nodeOf[2*e+1]
		p := adjStart[a] + fill[a]
		fill[a]++
		adjTo[p] = b
		adjT[p] = et[e]
		p = adjStart[b] + fill[b]
		fill[b]++
		adjTo[p] = a
		adjT[p] = et[e]
	}
	fill = nil
	nodeOf = nil
	eu, ev, el, et = nil, nil, nil, nil

	qs := make([]int32, Q)
	qd := make([]int32, Q)
	for i := 0; i < Q; i++ {
		qs[i] = int32(next())
		qd[i] = int32(next())
	}
	resT := make([]int64, Q)
	resB := make([]int32, Q)
	const NONE = int64(-1)

	var ctr int64
	var wg sync.WaitGroup
	workers := runtime.NumCPU()
	if workers > 8 {
		workers = 8
	}
	if workers > Q {
		workers = Q
	}
	total := int(K) + N
	for w := 0; w < workers; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			type side struct {
				dt      []int64 // stored t+1, 0 = unset
				db      []int32
				h       heap
				touched []int32
			}
			var sd [2]side
			for i := range sd {
				sd[i].dt = make([]int64, total)
				sd[i].db = make([]int32, total)
			}
			var bestT int64
			var bestB int32
			var haveBest bool
			relax := func(s int, id int32, t int64, b int32) {
				x := &sd[s]
				c := x.dt[id]
				if c == 0 || t+1 < c || (t+1 == c && b < x.db[id]) {
					if c == 0 {
						x.touched = append(x.touched, id)
					}
					x.dt[id] = t + 1
					x.db[id] = b
					x.h.push(item{t, b, id})
					o := &sd[1-s]
					if oc := o.dt[id]; oc != 0 {
						ct := t + oc - 1
						cb := b + o.db[id]
						if !haveBest || ct < bestT || (ct == bestT && cb < bestB) {
							haveBest = true
							bestT = ct
							bestB = cb
						}
					}
				}
			}
			// top returns the valid top of heap s, or false if empty.
			top := func(s int) (item, bool) {
				x := &sd[s]
				for len(x.h.a) > 0 {
					it := x.h.a[0]
					c := x.dt[it.id]
					if it.t+1 == c && it.b == x.db[it.id] {
						return it, true
					}
					x.h.pop()
				}
				return item{}, false
			}
			for {
				qi := int(atomic.AddInt64(&ctr, 1)) - 1
				if qi >= Q {
					return
				}
				S, D := qs[qi], qd[qi]
				if S == D {
					resT[qi] = 0
					resB[qi] = 0
					continue
				}
				haveBest = false
				for j := hs[S]; j < hs[S+1]; j++ {
					relax(0, j, 0, 1)
				}
				relax(1, K+D, 0, 0)
				for {
					tf, okf := top(0)
					tr, okr := top(1)
					if !okf || !okr {
						break
					}
					if haveBest {
						st := tf.t + tr.t
						sb := tf.b + tr.b
						if st > bestT || (st == bestT && sb >= bestB) {
							break
						}
					}
					if less(tf, tr) {
						// expand forward
						sd[0].h.pop()
						id := tf.id
						if id < K {
							for p := adjStart[id]; p < adjStart[id+1]; p++ {
								relax(0, adjTo[p], tf.t+int64(adjT[p]), tf.b)
							}
							relax(0, K+stn[id], tf.t, tf.b)
						} else {
							v := id - K
							nt := tf.t + int64(X[v])
							for j := hs[v]; j < hs[v+1]; j++ {
								relax(0, j, nt, tf.b+1)
							}
						}
					} else {
						sd[1].h.pop()
						id := tr.id
						if id < K {
							for p := adjStart[id]; p < adjStart[id+1]; p++ {
								relax(1, adjTo[p], tr.t+int64(adjT[p]), tr.b)
							}
							v := stn[id]
							relax(1, K+v, tr.t+int64(X[v]), tr.b+1)
						} else {
							v := id - K
							for j := hs[v]; j < hs[v+1]; j++ {
								relax(1, j, tr.t, tr.b)
							}
						}
					}
				}
				if haveBest {
					resT[qi] = bestT
					resB[qi] = bestB
				} else {
					resT[qi] = NONE
				}
				for s := 0; s < 2; s++ {
					x := &sd[s]
					for _, id := range x.touched {
						x.dt[id] = 0
					}
					x.touched = x.touched[:0]
					x.h.a = x.h.a[:0]
				}
			}
		}()
	}
	wg.Wait()
	out := bufio.NewWriterSize(os.Stdout, 1<<16)
	for i := 0; i < Q; i++ {
		if resT[i] == NONE {
			out.WriteString("none\n")
		} else {
			out.WriteString(strconv.FormatInt(resT[i], 10))
			out.WriteByte(' ')
			out.WriteString(strconv.Itoa(int(resB[i])))
			out.WriteByte('\n')
		}
	}
	out.Flush()
}
