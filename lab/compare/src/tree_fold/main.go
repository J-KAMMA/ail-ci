package main

import (
	"bufio"
	"io"
	"os"
	"slices"
	"strconv"
	"strings"
)

var (
	name  []string
	wt    []int64
	first []int32
	next  []int32

	valid bool
	order []int32
	par   []int32
	dep   []int32
	sub   []int64
	nodes, leaves, height, widest int
	lvCnt []int64
	lvSum []int64

	findMap   map[string]int32
	findCount int
)

func fail() {
	os.Exit(1)
}

func newNode(n string, w int64) int32 {
	name = append(name, n)
	wt = append(wt, w)
	first = append(first, -1)
	next = append(next, -1)
	return int32(len(name) - 1)
}

func parseTree(s string) bool {
	pos := 0
	var stack []int32
	last := []int32{} // last child of each stack level
	root := int32(-1)
	for {
		// parse a node
		st := pos
		for pos < len(s) && s[pos] >= 'a' && s[pos] <= 'z' {
			pos++
		}
		if pos == st || pos-st > 16 || pos >= len(s) || s[pos] != ':' {
			return false
		}
		nm := s[st:pos]
		pos++
		ws := pos
		for pos < len(s) && s[pos] >= '0' && s[pos] <= '9' {
			pos++
		}
		l := pos - ws
		if l == 0 || l > 7 || (l > 1 && s[ws] == '0') {
			return false
		}
		w, _ := strconv.ParseInt(s[ws:pos], 10, 64)
		if w > 1000000 {
			return false
		}
		v := newNode(nm, w)
		if len(stack) == 0 {
			if root != -1 {
				return false
			}
			root = v
		} else {
			p := stack[len(stack)-1]
			lc := last[len(last)-1]
			if lc == -1 {
				first[p] = v
			} else {
				next[lc] = v
			}
			last[len(last)-1] = v
		}
		if pos < len(s) && s[pos] == '[' {
			stack = append(stack, v)
			last = append(last, -1)
			pos++
			continue
		}
		for {
			if len(stack) == 0 {
				return pos == len(s)
			}
			if pos >= len(s) {
				return false
			}
			c := s[pos]
			if c == ' ' {
				pos++
				break
			}
			if c == ']' {
				stack = stack[:len(stack)-1]
				last = last[:len(last)-1]
				pos++
				continue
			}
			return false
		}
	}
}

func ensure() {
	if valid {
		return
	}
	valid = true
	findMap = nil
	findCount = 0
	total := len(name)
	if len(par) < total {
		par = make([]int32, total)
		dep = make([]int32, total)
		sub = make([]int64, total)
	}
	order = order[:0]
	st := []int32{0}
	par[0] = -1
	dep[0] = 0
	for len(st) > 0 {
		v := st[len(st)-1]
		st = st[:len(st)-1]
		order = append(order, v)
		sub[v] = wt[v]
		if s := next[v]; s != -1 {
			par[s] = par[v]
			dep[s] = dep[v]
			st = append(st, s)
		}
		if c := first[v]; c != -1 {
			par[c] = v
			dep[c] = dep[v] + 1
			st = append(st, c)
		}
	}
	nodes = len(order)
	leaves, height, widest = 0, 0, 0
	for i := len(order) - 1; i >= 0; i-- {
		v := order[i]
		if p := par[v]; p >= 0 {
			sub[p] += sub[v]
		}
	}
	for _, v := range order {
		if int(dep[v]) > height {
			height = int(dep[v])
		}
		if first[v] == -1 {
			leaves++
		} else {
			c := 0
			for x := first[v]; x != -1; x = next[x] {
				c++
			}
			if c > widest {
				widest = c
			}
		}
	}
	lvCnt = make([]int64, height+1)
	lvSum = make([]int64, height+1)
	for _, v := range order {
		lvCnt[dep[v]]++
		lvSum[dep[v]] += wt[v]
	}
}

func findFirst(nm string) int32 {
	ensure()
	findCount++
	if findCount > 3 {
		if findMap == nil {
			findMap = make(map[string]int32)
			for _, v := range order {
				if _, ok := findMap[name[v]]; !ok {
					findMap[name[v]] = v
				}
			}
		}
		if v, ok := findMap[nm]; ok {
			return v
		}
		return -1
	}
	for _, v := range order {
		if name[v] == nm {
			return v
		}
	}
	return -1
}

func isNum(s string) (int64, bool) {
	if len(s) == 0 || len(s) > 16 {
		return 0, false
	}
	if len(s) > 1 && s[0] == '0' {
		return 0, false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return 0, false
		}
	}
	n, _ := strconv.ParseInt(s, 10, 64)
	if n > 1000000000000000 {
		return 0, false
	}
	return n, true
}

func isName(s string) bool {
	if len(s) == 0 {
		return false
	}
	for i := 0; i < len(s); i++ {
		if !(s[i] >= 'a' && s[i] <= 'z' || s[i] == '+') {
			return false
		}
	}
	return true
}

type op struct {
	kind byte
	n    int64
	s    string
}

func main() {
	data, _ := io.ReadAll(os.Stdin)
	s := string(data)
	if strings.IndexByte(s, '\r') >= 0 {
		fail()
	}
	if len(s) > 0 && s[len(s)-1] == '\n' {
		s = s[:len(s)-1]
	}
	lines := strings.Split(s, "\n")
	if !parseTree(lines[0]) {
		fail()
	}
	var ops []op
	for _, ln := range lines[1:] {
		if ln == "" {
			fail()
		}
		kw, arg, has := strings.Cut(ln, " ")
		switch kw {
		case "total", "stats", "print", "sort", "mirror", "fold":
			if has {
				fail()
			}
			ops = append(ops, op{kind: kw[0] + map[string]byte{"total": 0, "stats": 1, "print": 2, "sort": 3, "mirror": 4, "fold": 5}[kw]*0, s: kw})
		case "level", "prune":
			if !has {
				fail()
			}
			n, ok := isNum(arg)
			if !ok {
				fail()
			}
			ops = append(ops, op{n: n, s: kw})
		case "find", "cut":
			if !has || !isName(arg) {
				fail()
			}
			ops = append(ops, op{s: kw + " " + arg})
		default:
			fail()
		}
	}
	out := bufio.NewWriterSize(os.Stdout, 1<<20)
	defer out.Flush()
	for _, o := range ops {
		switch {
		case o.s == "total":
			ensure()
			out.WriteString(strconv.FormatInt(sub[0], 10))
			out.WriteByte('\n')
		case o.s == "stats":
			ensure()
			out.WriteString("nodes=" + strconv.Itoa(nodes) + " leaves=" + strconv.Itoa(leaves) +
				" height=" + strconv.Itoa(height) + " widest=" + strconv.Itoa(widest) + "\n")
		case o.s == "level":
			ensure()
			if o.n <= int64(height) {
				out.WriteString(strconv.FormatInt(lvCnt[o.n], 10) + " " + strconv.FormatInt(lvSum[o.n], 10) + "\n")
			} else {
				out.WriteString("0 0\n")
			}
		case strings.HasPrefix(o.s, "find "):
			v := findFirst(o.s[5:])
			if v == -1 {
				out.WriteString("none\n")
			} else {
				var parts []string
				for x := v; x != -1; x = par[x] {
					parts = append(parts, name[x])
				}
				slices.Reverse(parts)
				out.WriteString(strings.Join(parts, "/"))
				out.WriteByte('\n')
			}
		case o.s == "print":
			ensure()
			for i, v := range order {
				if i > 0 {
					pv := order[i-1]
					if dep[v] == dep[pv]+1 {
						out.WriteByte('[')
					} else {
						for k := dep[pv] - dep[v]; k > 0; k-- {
							out.WriteByte(']')
						}
						out.WriteByte(' ')
					}
				}
				out.WriteString(name[v])
				out.WriteByte(':')
				out.WriteString(strconv.FormatInt(wt[v], 10))
			}
			for k := dep[order[len(order)-1]]; k > 0; k-- {
				out.WriteByte(']')
			}
			out.WriteByte('\n')
		case o.s == "prune":
			ensure()
			for _, v := range order {
				if first[v] == -1 {
					continue
				}
				head, tail := int32(-1), int32(-1)
				for c := first[v]; c != -1; {
					nx := next[c]
					if sub[c] >= o.n {
						if tail == -1 {
							head = c
						} else {
							next[tail] = c
						}
						tail = c
					}
					c = nx
				}
				if tail != -1 {
					next[tail] = -1
				}
				first[v] = head
			}
			valid = false
		case o.s == "sort":
			ensure()
			var tmp []int32
			for _, v := range order {
				c := first[v]
				if c == -1 || next[c] == -1 {
					continue
				}
				tmp = tmp[:0]
				for ; c != -1; c = next[c] {
					tmp = append(tmp, c)
				}
				slices.SortStableFunc(tmp, func(a, b int32) int {
					if sub[a] != sub[b] {
						if sub[a] > sub[b] {
							return -1
						}
						return 1
					}
					return strings.Compare(name[a], name[b])
				})
				first[v] = tmp[0]
				for i := 0; i+1 < len(tmp); i++ {
					next[tmp[i]] = tmp[i+1]
				}
				next[tmp[len(tmp)-1]] = -1
			}
			valid = false
		case o.s == "mirror":
			ensure()
			for _, v := range order {
				c := first[v]
				if c == -1 || next[c] == -1 {
					continue
				}
				prev := int32(-1)
				for c != -1 {
					nx := next[c]
					next[c] = prev
					prev = c
					c = nx
				}
				first[v] = prev
			}
			valid = false
		case o.s == "fold":
			ensure()
			absorbed := make([]bool, len(name))
			var parts []string
			for _, v := range order {
				if v == 0 || absorbed[v] {
					continue
				}
				c := first[v]
				if c == -1 || next[c] != -1 {
					continue
				}
				parts = parts[:0]
				parts = append(parts, name[v])
				w := wt[v]
				cur := v
				for {
					c := first[cur]
					if c == -1 || next[c] != -1 {
						break
					}
					absorbed[c] = true
					parts = append(parts, name[c])
					w += wt[c]
					cur = c
				}
				name[v] = strings.Join(parts, "+")
				wt[v] = w
				first[v] = first[cur]
			}
			valid = false
		default: // cut
			nm := o.s[4:]
			v := findFirst(nm)
			if v > 0 {
				p := par[v]
				var prev int32 = -1
				for x := first[p]; x != v; x = next[x] {
					prev = x
				}
				c := first[v]
				repl := next[v]
				if c != -1 {
					l := c
					for next[l] != -1 {
						l = next[l]
					}
					next[l] = next[v]
					repl = c
				}
				if prev == -1 {
					first[p] = repl
				} else {
					next[prev] = repl
				}
				valid = false
			}
		}
	}
}
