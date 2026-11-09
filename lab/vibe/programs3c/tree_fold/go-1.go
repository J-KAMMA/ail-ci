package main

import (
	"bufio"
	"io"
	"os"
	"sort"
	"strconv"
	"strings"
)

type Node struct {
	name     string
	weight   int64
	children []*Node
	sw       int64
}

func parseNum(s string, limit int64) (int64, bool) {
	if len(s) == 0 || len(s) > 16 {
		return 0, false
	}
	if len(s) > 1 && s[0] == '0' {
		return 0, false
	}
	var v int64
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c < '0' || c > '9' {
			return 0, false
		}
		v = v*10 + int64(c-'0')
	}
	if v > limit {
		return 0, false
	}
	return v, true
}

func parseNode(s string, pos int) (*Node, int, bool) {
	start := pos
	for pos < len(s) && s[pos] >= 'a' && s[pos] <= 'z' {
		pos++
	}
	if pos-start < 1 || pos-start > 16 {
		return nil, 0, false
	}
	n := &Node{name: s[start:pos]}
	if pos >= len(s) || s[pos] != ':' {
		return nil, 0, false
	}
	pos++
	start = pos
	for pos < len(s) && s[pos] >= '0' && s[pos] <= '9' {
		pos++
	}
	w, ok := parseNum(s[start:pos], 1000000)
	if !ok {
		return nil, 0, false
	}
	n.weight = w
	if pos < len(s) && s[pos] == '[' {
		pos++
		for {
			c, p, ok := parseNode(s, pos)
			if !ok {
				return nil, 0, false
			}
			n.children = append(n.children, c)
			pos = p
			if pos < len(s) && s[pos] == ' ' {
				pos++
				continue
			}
			break
		}
		if pos >= len(s) || s[pos] != ']' {
			return nil, 0, false
		}
		pos++
	}
	return n, pos, true
}

func validName(s string) bool {
	if len(s) == 0 {
		return false
	}
	for i := 0; i < len(s); i++ {
		c := s[i]
		if !((c >= 'a' && c <= 'z') || c == '+') {
			return false
		}
	}
	return true
}

func calcSW(n *Node) int64 {
	s := n.weight
	for _, c := range n.children {
		s += calcSW(c)
	}
	n.sw = s
	return s
}

func total(n *Node) int64 {
	s := n.weight
	for _, c := range n.children {
		s += total(c)
	}
	return s
}

func stats(n *Node, d int, nodes, leaves, height, widest *int64) {
	*nodes++
	if len(n.children) == 0 {
		*leaves++
	}
	if int64(d) > *height {
		*height = int64(d)
	}
	if int64(len(n.children)) > *widest {
		*widest = int64(len(n.children))
	}
	for _, c := range n.children {
		stats(c, d+1, nodes, leaves, height, widest)
	}
}

func level(n *Node, d, D int64, cnt, sum *int64) {
	if d == D {
		*cnt++
		*sum += n.weight
		return
	}
	if d > D {
		return
	}
	for _, c := range n.children {
		level(c, d+1, D, cnt, sum)
	}
}

func find(n *Node, name string, stack *[]string) bool {
	*stack = append(*stack, n.name)
	if n.name == name {
		return true
	}
	for _, c := range n.children {
		if find(c, name, stack) {
			return true
		}
	}
	*stack = (*stack)[:len(*stack)-1]
	return false
}

func writeNode(w *bufio.Writer, n *Node) {
	w.WriteString(n.name)
	w.WriteByte(':')
	w.WriteString(strconv.FormatInt(n.weight, 10))
	if len(n.children) > 0 {
		w.WriteByte('[')
		for i, c := range n.children {
			if i > 0 {
				w.WriteByte(' ')
			}
			writeNode(w, c)
		}
		w.WriteByte(']')
	}
}

func prune(n *Node, W int64) {
	kept := n.children[:0]
	for _, c := range n.children {
		if c.sw >= W {
			kept = append(kept, c)
		}
	}
	n.children = kept
	for _, c := range kept {
		prune(c, W)
	}
}

func sortAll(n *Node) {
	sort.SliceStable(n.children, func(i, j int) bool {
		a, b := n.children[i], n.children[j]
		if a.sw != b.sw {
			return a.sw > b.sw
		}
		return a.name < b.name
	})
	for _, c := range n.children {
		sortAll(c)
	}
}

func mirror(n *Node) {
	ch := n.children
	for i, j := 0, len(ch)-1; i < j; i, j = i+1, j-1 {
		ch[i], ch[j] = ch[j], ch[i]
	}
	for _, c := range ch {
		mirror(c)
	}
}

func foldKids(n *Node) {
	for i, c := range n.children {
		var names []string
		var w int64
		cur := c
		for {
			names = append(names, cur.name)
			w += cur.weight
			if len(cur.children) == 1 {
				cur = cur.children[0]
			} else {
				break
			}
		}
		m := &Node{name: strings.Join(names, "+"), weight: w, children: cur.children}
		foldKids(m)
		n.children[i] = m
	}
}

func cutIn(n *Node, name string) bool {
	for i, c := range n.children {
		if c.name == name {
			nc := make([]*Node, 0, len(n.children)-1+len(c.children))
			nc = append(nc, n.children[:i]...)
			nc = append(nc, c.children...)
			nc = append(nc, n.children[i+1:]...)
			n.children = nc
			return true
		}
		if cutIn(c, name) {
			return true
		}
	}
	return false
}

type op struct {
	kind string
	arg  string
	num  int64
}

func main() {
	data, err := io.ReadAll(os.Stdin)
	if err != nil {
		os.Exit(1)
	}
	s := string(data)
	if strings.IndexByte(s, '\r') >= 0 {
		os.Exit(1)
	}
	lines := strings.Split(s, "\n")
	if lines[len(lines)-1] == "" {
		lines = lines[:len(lines)-1]
	}
	if len(lines) == 0 {
		os.Exit(1)
	}
	root, p, ok := parseNode(lines[0], 0)
	if !ok || p != len(lines[0]) {
		os.Exit(1)
	}
	ops := make([]op, 0, len(lines))
	for _, line := range lines[1:] {
		parts := strings.Split(line, " ")
		switch parts[0] {
		case "total", "stats", "print", "sort", "mirror", "fold":
			if len(parts) != 1 {
				os.Exit(1)
			}
			ops = append(ops, op{kind: parts[0]})
		case "level", "prune":
			if len(parts) != 2 {
				os.Exit(1)
			}
			v, ok := parseNum(parts[1], 1000000000000000)
			if !ok {
				os.Exit(1)
			}
			ops = append(ops, op{kind: parts[0], num: v})
		case "find", "cut":
			if len(parts) != 2 || !validName(parts[1]) {
				os.Exit(1)
			}
			ops = append(ops, op{kind: parts[0], arg: parts[1]})
		default:
			os.Exit(1)
		}
	}

	w := bufio.NewWriterSize(os.Stdout, 1<<16)
	for _, o := range ops {
		switch o.kind {
		case "total":
			w.WriteString(strconv.FormatInt(total(root), 10))
			w.WriteByte('\n')
		case "stats":
			var nodes, leaves, height, widest int64
			stats(root, 0, &nodes, &leaves, &height, &widest)
			w.WriteString("nodes=" + strconv.FormatInt(nodes, 10) +
				" leaves=" + strconv.FormatInt(leaves, 10) +
				" height=" + strconv.FormatInt(height, 10) +
				" widest=" + strconv.FormatInt(widest, 10) + "\n")
		case "level":
			var cnt, sum int64
			level(root, 0, o.num, &cnt, &sum)
			w.WriteString(strconv.FormatInt(cnt, 10) + " " + strconv.FormatInt(sum, 10) + "\n")
		case "find":
			var stack []string
			if find(root, o.arg, &stack) {
				w.WriteString(strings.Join(stack, "/") + "\n")
			} else {
				w.WriteString("none\n")
			}
		case "print":
			writeNode(w, root)
			w.WriteByte('\n')
		case "prune":
			calcSW(root)
			prune(root, o.num)
		case "sort":
			calcSW(root)
			sortAll(root)
		case "mirror":
			mirror(root)
		case "fold":
			foldKids(root)
		case "cut":
			if root.name != o.arg {
				cutIn(root, o.arg)
			}
		}
	}
	w.Flush()
}
