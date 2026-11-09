package main

import (
	"bufio"
	"fmt"
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
	sub      int64
}

type op struct {
	kind string
	arg  string
	num  int64
}

func die() { os.Exit(1) }

func isDigit(c byte) bool { return c >= '0' && c <= '9' }

func validNum(s string, max int64) (int64, bool) {
	if len(s) < 1 || len(s) > 16 {
		return 0, false
	}
	for i := 0; i < len(s); i++ {
		if !isDigit(s[i]) {
			return 0, false
		}
	}
	if len(s) > 1 && s[0] == '0' {
		return 0, false
	}
	v, err := strconv.ParseInt(s, 10, 64)
	if err != nil || v > max {
		return 0, false
	}
	return v, true
}

func parseNode(s string, pos int) (*Node, int, bool) {
	start := pos
	for pos < len(s) && s[pos] >= 'a' && s[pos] <= 'z' {
		pos++
	}
	if l := pos - start; l < 1 || l > 16 {
		return nil, 0, false
	}
	n := &Node{name: s[start:pos]}
	if pos >= len(s) || s[pos] != ':' {
		return nil, 0, false
	}
	pos++
	ws := pos
	for pos < len(s) && isDigit(s[pos]) {
		pos++
	}
	w, ok := validNum(s[ws:pos], 1000000)
	if !ok {
		return nil, 0, false
	}
	n.weight = w
	if pos < len(s) && s[pos] == '[' {
		pos++
		for {
			c, np, ok2 := parseNode(s, pos)
			if !ok2 {
				return nil, 0, false
			}
			n.children = append(n.children, c)
			pos = np
			if pos >= len(s) {
				return nil, 0, false
			}
			if s[pos] == ' ' {
				pos++
				continue
			}
			if s[pos] == ']' {
				pos++
				break
			}
			return nil, 0, false
		}
	}
	return n, pos, true
}

func validOpName(s string) bool {
	if len(s) < 1 {
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

func parseOp(line string) (op, bool) {
	parts := strings.Split(line, " ")
	switch parts[0] {
	case "total", "stats", "print", "sort", "mirror", "fold":
		if len(parts) != 1 {
			return op{}, false
		}
		return op{kind: parts[0]}, true
	case "level", "prune":
		if len(parts) != 2 {
			return op{}, false
		}
		v, ok := validNum(parts[1], 1000000000000000)
		if !ok {
			return op{}, false
		}
		return op{kind: parts[0], num: v}, true
	case "find", "cut":
		if len(parts) != 2 || !validOpName(parts[1]) {
			return op{}, false
		}
		return op{kind: parts[0], arg: parts[1]}, true
	}
	return op{}, false
}

func computeSub(n *Node) int64 {
	s := n.weight
	for _, c := range n.children {
		s += computeSub(c)
	}
	n.sub = s
	return s
}

func totalRec(n *Node) int64 {
	s := n.weight
	for _, c := range n.children {
		s += totalRec(c)
	}
	return s
}

func prune(n *Node, w int64) {
	k := 0
	for _, c := range n.children {
		if c.sub >= w {
			n.children[k] = c
			k++
		}
	}
	n.children = n.children[:k]
	for _, c := range n.children {
		prune(c, w)
	}
}

func sortRec(n *Node) {
	sort.SliceStable(n.children, func(i, j int) bool {
		a, b := n.children[i], n.children[j]
		if a.sub != b.sub {
			return a.sub > b.sub
		}
		return a.name < b.name
	})
	for _, c := range n.children {
		sortRec(c)
	}
}

func mirrorRec(n *Node) {
	ch := n.children
	for i, j := 0, len(ch)-1; i < j; i, j = i+1, j-1 {
		ch[i], ch[j] = ch[j], ch[i]
	}
	for _, c := range ch {
		mirrorRec(c)
	}
}

func foldRec(n *Node) {
	for _, c := range n.children {
		parts := []string{c.name}
		for len(c.children) == 1 {
			gc := c.children[0]
			parts = append(parts, gc.name)
			c.weight += gc.weight
			c.children = gc.children
		}
		if len(parts) > 1 {
			c.name = strings.Join(parts, "+")
		}
		foldRec(c)
	}
}

func cutOp(root *Node, name string) {
	if root.name == name {
		return
	}
	var findCut func(n *Node) (*Node, int)
	findCut = func(n *Node) (*Node, int) {
		for i, c := range n.children {
			if c.name == name {
				return n, i
			}
			if p, j := findCut(c); p != nil {
				return p, j
			}
		}
		return nil, 0
	}
	p, j := findCut(root)
	if p == nil {
		return
	}
	c := p.children[j]
	nc := make([]*Node, 0, len(p.children)-1+len(c.children))
	nc = append(nc, p.children[:j]...)
	nc = append(nc, c.children...)
	nc = append(nc, p.children[j+1:]...)
	p.children = nc
}

func main() {
	data, _ := io.ReadAll(os.Stdin)
	s := string(data)
	if strings.Contains(s, "\r") {
		die()
	}
	lines := strings.Split(s, "\n")
	if len(lines) > 0 && lines[len(lines)-1] == "" {
		lines = lines[:len(lines)-1]
	}
	if len(lines) == 0 {
		die()
	}
	for _, l := range lines {
		if l == "" {
			die()
		}
	}
	root, pos, ok := parseNode(lines[0], 0)
	if !ok || pos != len(lines[0]) {
		die()
	}
	ops := make([]op, 0, len(lines)-1)
	for _, l := range lines[1:] {
		o, ok2 := parseOp(l)
		if !ok2 {
			die()
		}
		ops = append(ops, o)
	}

	w := bufio.NewWriterSize(os.Stdout, 1<<20)
	defer w.Flush()

	for _, o := range ops {
		switch o.kind {
		case "total":
			fmt.Fprintf(w, "%d\n", totalRec(root))
		case "stats":
			var nodes, leaves, height, widest int64
			var walk func(n *Node, d int64)
			walk = func(n *Node, d int64) {
				nodes++
				if len(n.children) == 0 {
					leaves++
				}
				if d > height {
					height = d
				}
				if int64(len(n.children)) > widest {
					widest = int64(len(n.children))
				}
				for _, c := range n.children {
					walk(c, d+1)
				}
			}
			walk(root, 0)
			fmt.Fprintf(w, "nodes=%d leaves=%d height=%d widest=%d\n", nodes, leaves, height, widest)
		case "level":
			var cnt, sum int64
			var lv func(n *Node, d int64)
			lv = func(n *Node, d int64) {
				if d == o.num {
					cnt++
					sum += n.weight
					return
				}
				for _, c := range n.children {
					lv(c, d+1)
				}
			}
			lv(root, 0)
			fmt.Fprintf(w, "%d %d\n", cnt, sum)
		case "find":
			var found []string
			var dfs func(n *Node, path []string) bool
			dfs = func(n *Node, path []string) bool {
				path = append(path, n.name)
				if n.name == o.arg {
					found = make([]string, len(path))
					copy(found, path)
					return true
				}
				for _, c := range n.children {
					if dfs(c, path) {
						return true
					}
				}
				return false
			}
			dfs(root, nil)
			if found != nil {
				fmt.Fprintf(w, "%s\n", strings.Join(found, "/"))
			} else {
				fmt.Fprintf(w, "none\n")
			}
		case "print":
			var sb strings.Builder
			var ser func(n *Node)
			ser = func(n *Node) {
				sb.WriteString(n.name)
				sb.WriteByte(':')
				sb.WriteString(strconv.FormatInt(n.weight, 10))
				if len(n.children) > 0 {
					sb.WriteByte('[')
					for i, c := range n.children {
						if i > 0 {
							sb.WriteByte(' ')
						}
						ser(c)
					}
					sb.WriteByte(']')
				}
			}
			ser(root)
			sb.WriteByte('\n')
			w.WriteString(sb.String())
		case "prune":
			computeSub(root)
			prune(root, o.num)
		case "sort":
			computeSub(root)
			sortRec(root)
		case "mirror":
			mirrorRec(root)
		case "fold":
			foldRec(root)
		case "cut":
			cutOp(root, o.arg)
		}
	}
}
