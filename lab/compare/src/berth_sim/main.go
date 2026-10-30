package main

import (
	"bufio"
	"io"
	"os"
	"slices"
	"strconv"
)

type wi struct {
	key uint64
	idx int32
}

type wheap []wi

func (h *wheap) push(x wi) {
	*h = append(*h, x)
	a := *h
	i := len(a) - 1
	for i > 0 {
		p := (i - 1) / 2
		if a[p].key <= x.key {
			break
		}
		a[i] = a[p]
		i = p
	}
	a[i] = x
}

func (h *wheap) pop() wi {
	a := *h
	top := a[0]
	n := len(a) - 1
	x := a[n]
	a = a[:n]
	*h = a
	if n > 0 {
		i := 0
		for {
			c := 2*i + 1
			if c >= n {
				break
			}
			if c+1 < n && a[c+1].key < a[c].key {
				c++
			}
			if a[c].key >= x.key {
				break
			}
			a[i] = a[c]
			i = c
		}
		a[i] = x
	}
	return top
}

// generic uint64 min-heap
type uheap []uint64

func (h *uheap) push(x uint64) {
	*h = append(*h, x)
	a := *h
	i := len(a) - 1
	for i > 0 {
		p := (i - 1) / 2
		if a[p] <= x {
			break
		}
		a[i] = a[p]
		i = p
	}
	a[i] = x
}

func (h *uheap) pop() uint64 {
	a := *h
	top := a[0]
	n := len(a) - 1
	x := a[n]
	a = a[:n]
	*h = a
	if n > 0 {
		i := 0
		for {
			c := 2*i + 1
			if c >= n {
				break
			}
			if c+1 < n && a[c+1] < a[c] {
				c++
			}
			if a[c] >= x {
				break
			}
			a[i] = a[c]
			i = c
		}
		a[i] = x
	}
	return top
}

func main() {
	data, _ := io.ReadAll(os.Stdin)
	pos := 0
	next := func() int64 {
		for pos < len(data) && (data[pos] < '0' || data[pos] > '9') {
			pos++
		}
		var v int64
		for pos < len(data) && data[pos] >= '0' && data[pos] <= '9' {
			v = v*10 + int64(data[pos]-'0')
			pos++
		}
		return v
	}
	B := int(next())
	S := int(next())
	class := make([]int, B)
	rate := make([]int64, B)
	for i := 0; i < B; i++ {
		class[i] = int(next())
		rate[i] = next()
	}
	id := make([]int64, S)
	arr := make([]int64, S)
	size := make([]int8, S)
	cargo := make([]int64, S)
	key := make([]uint64, S)
	op := make([]int32, S)
	order := make([]uint64, S)
	for i := 0; i < S; i++ {
		id[i] = next()
		arr[i] = next()
		size[i] = int8(next())
		cargo[i] = next()
		p := uint64(next())
		op[i] = int32(next())
		key[i] = p<<60 | uint64(arr[i])<<30 | uint64(id[i])
		order[i] = uint64(arr[i])<<22 | uint64(i)
	}
	slices.Sort(order)

	start := make([]int64, S)
	berthOf := make([]int32, S)
	var free [4]uheap
	for b := 0; b < B; b++ {
		free[class[b]].push(uint64(b))
	}
	var wait [4]wheap
	waitCnt := 0
	var dep uheap // time<<12 | berth
	last := make([]int32, B)
	for i := range last {
		last[i] = -1
	}
	cnt := make([]int64, B)
	busy := make([]int64, B)
	var makespan int64
	ai := 0
	for ai < S || len(dep) > 0 {
		var t int64 = -1
		if ai < S {
			t = int64(order[ai] >> 22)
		}
		if len(dep) > 0 {
			d := int64(dep[0] >> 12)
			if t < 0 || d < t {
				t = d
			}
		}
		for len(dep) > 0 && int64(dep[0]>>12) == t {
			x := dep.pop()
			b := int(x & 4095)
			free[class[b]].push(uint64(b))
		}
		for ai < S && int64(order[ai]>>22) == t {
			i := int32(order[ai] & (1<<22 - 1))
			wait[size[i]].push(wi{key[i], i})
			waitCnt++
			ai++
		}
		if waitCnt > 0 {
			for c := 1; c <= 3; c++ {
				for len(free[c]) > 0 {
					// best among sizes <= c
					bs := 0
					var bk uint64
					for s := 1; s <= c; s++ {
						if len(wait[s]) > 0 && (bs == 0 || wait[s][0].key < bk) {
							bs = s
							bk = wait[s][0].key
						}
					}
					if bs == 0 {
						break
					}
					w := wait[bs].pop()
					waitCnt--
					b := int(free[c].pop())
					i := w.idx
					setup := int64(4)
					if last[b] == op[i] {
						setup = 1
					}
					last[b] = op[i]
					svc := (cargo[i]+rate[b]-1)/rate[b] + setup
					start[i] = t
					berthOf[i] = int32(b)
					cnt[b]++
					busy[b] += svc
					end := t + svc
					if end > makespan {
						makespan = end
					}
					dep.push(uint64(end)<<12 | uint64(b))
				}
			}
		}
	}

	out := bufio.NewWriterSize(os.Stdout, 1<<16)
	defer out.Flush()
	out.WriteString("ships " + strconv.Itoa(S) + "\n")
	out.WriteString("makespan " + strconv.FormatInt(makespan, 10) + "\n")
	var W, X int64
	var XI int64 = -1
	for i := 0; i < S; i++ {
		w := start[i] - arr[i]
		W += w
		if w > X || (w == X && XI >= 0 && id[i] < XI) || XI < 0 {
			if XI < 0 || w > X || id[i] < XI {
				X = w
				XI = id[i]
			}
		}
	}
	out.WriteString("wait total " + strconv.FormatInt(W, 10) + " max " + strconv.FormatInt(X, 10) + " ship " + strconv.FormatInt(XI, 10) + "\n")
	for b := 0; b < B; b++ {
		out.WriteString("berth " + strconv.Itoa(b) + " ships " + strconv.FormatInt(cnt[b], 10) + " busy " + strconv.FormatInt(busy[b], 10) + "\n")
	}
	for i := 0; i < S; i++ {
		order[i] = uint64(id[i])<<22 | uint64(i)
	}
	slices.Sort(order)
	var g int64
	for _, o := range order {
		i := o & (1<<22 - 1)
		g = (g*1000003 + start[i]*31 + int64(berthOf[i])) % 1000000007
	}
	out.WriteString("digest " + strconv.FormatInt(g, 10) + "\n")
}
