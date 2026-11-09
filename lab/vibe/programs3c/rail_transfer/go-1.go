package main

import (
	"bufio"
	"math"
	"os"
	"slices"
	"strconv"
)

var rd *bufio.Reader

func readInt() int {
	n := 0
	c, _ := rd.ReadByte()
	for c == ' ' || c == '\n' || c == '\r' {
		c, _ = rd.ReadByte()
	}
	for c >= '0' && c <= '9' {
		n = n*10 + int(c-'0')
		c, _ = rd.ReadByte()
	}
	return n
}

type item struct {
	k int64
	n int32
}

var hp []item

func hpush(it item) {
	hp = append(hp, it)
	i := len(hp) - 1
	for i > 0 {
		p := (i - 1) / 2
		if hp[p].k <= hp[i].k {
			break
		}
		hp[p], hp[i] = hp[i], hp[p]
		i = p
	}
}

func hpop() item {
	top := hp[0]
	last := len(hp) - 1
	hp[0] = hp[last]
	hp = hp[:last]
	i := 0
	n := len(hp)
	for {
		l := 2*i + 1
		if l >= n {
			break
		}
		m := l
		if r := l + 1; r < n && hp[r].k < hp[l].k {
			m = r
		}
		if hp[i].k <= hp[m].k {
			break
		}
		hp[i], hp[m] = hp[m], hp[i]
		i = m
	}
	return top
}

func main() {
	rd = bufio.NewReaderSize(os.Stdin, 1<<20)
	w := bufio.NewWriterSize(os.Stdout, 1<<16)
	defer w.Flush()

	N := readInt()
	M := readInt()
	Q := readInt()

	X := make([]int64, N)
	for i := 0; i < N; i++ {
		X[i] = int64(readInt())
	}

	H := 2 * M
	hFrom := make([]int32, H)
	hTo := make([]int32, H)
	hLine := make([]int32, H)
	hCost := make([]int32, H)
	for i := 0; i < M; i++ {
		u := readInt()
		v := readInt()
		l := readInt()
		t := readInt()
		h := 2 * i
		hFrom[h] = int32(u)
		hTo[h] = int32(v)
		hLine[h] = int32(l)
		hCost[h] = int32(t)
		hFrom[h+1] = int32(v)
		hTo[h+1] = int32(u)
		hLine[h+1] = int32(l)
		hCost[h+1] = int32(t)
	}

	keys := make([]uint64, H)
	for h := 0; h < H; h++ {
		keys[h] = ((uint64(hFrom[h])<<17 | uint64(hLine[h])) << 21) | uint64(h)
	}
	slices.Sort(keys)

	order := make([]int32, H)
	var gFrom, gLine, gHalf []int32
	prev := uint64(math.MaxUint64)
	for i, kv := range keys {
		h := kv & (1<<21 - 1)
		k := kv >> 21
		order[i] = int32(h)
		if k != prev {
			gFrom = append(gFrom, hFrom[h])
			gLine = append(gLine, hLine[h])
			gHalf = append(gHalf, int32(i))
			prev = k
		}
	}
	G := len(gFrom)
	gHalf = append(gHalf, int32(H))
	keys = nil

	// station -> group range
	stGStart := make([]int32, N+1)
	for g := 0; g < G; g++ {
		stGStart[gFrom[g]+1]++
	}
	for v := 0; v < N; v++ {
		stGStart[v+1] += stGStart[v]
	}

	// target group for each half-edge
	tg := make([]int32, H)
	for h := 0; h < H; h++ {
		wv := int(hTo[h])
		l := hLine[h]
		lo := int(stGStart[wv])
		hi := int(stGStart[wv+1])
		for lo < hi {
			mid := (lo + hi) / 2
			if gLine[mid] < l {
				lo = mid + 1
			} else {
				hi = mid
			}
		}
		tg[h] = int32(lo)
	}

	adjTo := make([]int32, H)
	adjCost := make([]int32, H)
	for i := 0; i < H; i++ {
		h := order[i]
		adjTo[i] = tg[h]
		adjCost[i] = hCost[h]
	}
	order = nil
	tg = nil

	NN := N + G
	dist := make([]int64, NN)
	stamp := make([]int32, NN)
	var cur int32 = 0

	relax := func(v int, nk int64) {
		if stamp[v] != cur || nk < dist[v] {
			stamp[v] = cur
			dist[v] = nk
			hpush(item{nk, int32(v)})
		}
	}

	solve := func(S, D int) (int64, bool) {
		cur++
		hp = hp[:0]
		for g := int(stGStart[S]); g < int(stGStart[S+1]); g++ {
			relax(N+g, 1)
		}
		for len(hp) > 0 {
			it := hpop()
			n := int(it.n)
			k := it.k
			if stamp[n] != cur || k > dist[n] {
				continue
			}
			if n < N {
				if n == D {
					return k, true
				}
				x := (X[n] << 22) + 1
				for g := int(stGStart[n]); g < int(stGStart[n+1]); g++ {
					relax(N+g, k+x)
				}
			} else {
				g := n - N
				for i := int(gHalf[g]); i < int(gHalf[g+1]); i++ {
					relax(N+int(adjTo[i]), k+(int64(adjCost[i])<<22))
				}
				relax(int(gFrom[g]), k)
			}
		}
		return 0, false
	}

	mask := int64(1<<22 - 1)
	for q := 0; q < Q; q++ {
		S := readInt()
		D := readInt()
		if S == D {
			w.WriteString("0 0\n")
			continue
		}
		key, ok := solve(S, D)
		if !ok {
			w.WriteString("none\n")
			continue
		}
		w.WriteString(strconv.FormatInt(key>>22, 10))
		w.WriteByte(' ')
		w.WriteString(strconv.FormatInt(key&mask, 10))
		w.WriteByte('\n')
	}
}
