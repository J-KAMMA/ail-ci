package main

import (
	"bufio"
	"math/bits"
	"os"
	"strconv"
)

type tok struct {
	kind byte // 'n' number, 'w' word, 'k' keyword, 'o' operator
	s    string
	num  uint32
}

var keywords = map[string]bool{"set": true, "out": true, "loop": true, "when": true, "else": true, "end": true, "break": true}

type expr struct {
	op   string // "n","v", binary ops, or unary "neg","#","!"
	num  uint32
	idx  int
	l, r *expr
}

type stmt struct {
	kind string
	line int
	idx  int
	exs  []*expr
	body []*stmt
	els  []*stmt
}

type perr struct{}

var varIdx = map[string]int{}

func tokenize(s string) ([]tok, bool) {
	var ts []tok
	i := 0
	n := len(s)
	for i < n {
		c := s[i]
		switch {
		case c == ' ' || c == '\t' || c == '\r':
			i++
		case c >= '0' && c <= '9':
			j := i
			var v uint64
			for j < n && s[j] >= '0' && s[j] <= '9' {
				v = v*10 + uint64(s[j]-'0')
				if v > 4294967295 {
					return nil, false
				}
				j++
			}
			if j < n && ((s[j] >= 'a' && s[j] <= 'z') || s[j] == '_') {
				return nil, false
			}
			ts = append(ts, tok{kind: 'n', num: uint32(v)})
			i = j
		case (c >= 'a' && c <= 'z') || c == '_':
			j := i
			for j < n && ((s[j] >= 'a' && s[j] <= 'z') || s[j] == '_' || (s[j] >= '0' && s[j] <= '9')) {
				j++
			}
			w := s[i:j]
			if keywords[w] {
				ts = append(ts, tok{kind: 'k', s: w})
			} else {
				ts = append(ts, tok{kind: 'w', s: w})
			}
			i = j
		default:
			if i+1 < n {
				two := s[i : i+2]
				if two == "<>" || two == "><" || two == "==" || two == "!=" {
					ts = append(ts, tok{kind: 'o', s: two})
					i += 2
					continue
				}
			}
			switch c {
			case '<', '>', '+', '-', '*', '/', '%', '~', '#', '!', '(', ')', ',', '=':
				ts = append(ts, tok{kind: 'o', s: string(c)})
				i++
			default:
				return nil, false
			}
		}
	}
	return ts, true
}

type parser struct {
	ts    []tok
	p     int
	depth int
}

func (p *parser) isOp(s string) bool {
	return p.p < len(p.ts) && p.ts[p.p].kind == 'o' && p.ts[p.p].s == s
}

func (p *parser) fail() { panic(perr{}) }

func (p *parser) expr() *expr {
	l := p.l2()
	for p.isOp("<>") || p.isOp("><") {
		op := p.ts[p.p].s
		p.p++
		r := p.l2()
		l = &expr{op: op, l: l, r: r}
	}
	return l
}

func (p *parser) l2() *expr {
	l := p.l3()
	if p.isOp("==") || p.isOp("!=") || p.isOp("<") || p.isOp(">") {
		op := p.ts[p.p].s
		p.p++
		r := p.l3()
		l = &expr{op: op, l: l, r: r}
		if p.isOp("==") || p.isOp("!=") || p.isOp("<") || p.isOp(">") {
			p.fail()
		}
	}
	return l
}

func (p *parser) l3() *expr {
	l := p.l4()
	for p.isOp("+") || p.isOp("-") {
		op := p.ts[p.p].s
		p.p++
		r := p.l4()
		l = &expr{op: op, l: l, r: r}
	}
	return l
}

func (p *parser) l4() *expr {
	l := p.l5()
	for p.isOp("*") || p.isOp("/") || p.isOp("%") {
		op := p.ts[p.p].s
		p.p++
		r := p.l5()
		l = &expr{op: op, l: l, r: r}
	}
	return l
}

func (p *parser) l5() *expr {
	l := p.l6()
	if p.isOp("~") {
		p.p++
		r := p.l5()
		return &expr{op: "~", l: l, r: r}
	}
	return l
}

func (p *parser) l6() *expr {
	if p.isOp("-") {
		p.p++
		return &expr{op: "neg", l: p.l6()}
	}
	if p.isOp("#") {
		p.p++
		return &expr{op: "#", l: p.l6()}
	}
	if p.isOp("!") {
		p.p++
		return &expr{op: "!", l: p.l6()}
	}
	return p.l7()
}

func (p *parser) l7() *expr {
	if p.p >= len(p.ts) {
		p.fail()
	}
	t := p.ts[p.p]
	switch {
	case t.kind == 'n':
		p.p++
		return &expr{op: "n", num: t.num}
	case t.kind == 'w':
		p.p++
		return &expr{op: "v", idx: getVar(t.s)}
	case t.kind == 'o' && t.s == "(":
		p.p++
		p.depth++
		if p.depth > 32 {
			p.fail()
		}
		e := p.expr()
		if !p.isOp(")") {
			p.fail()
		}
		p.p++
		p.depth--
		return e
	}
	p.fail()
	return nil
}

func getVar(s string) int {
	if i, ok := varIdx[s]; ok {
		return i
	}
	i := len(varIdx)
	varIdx[s] = i
	return i
}

func parseStmt(ts []tok, line int) (st *stmt, ok bool) {
	defer func() {
		if r := recover(); r != nil {
			if _, is := r.(perr); is {
				st, ok = nil, false
				return
			}
			panic(r)
		}
	}()
	p := &parser{ts: ts}
	t := ts[0]
	p.p = 1
	st = &stmt{kind: t.s, line: line}
	switch t.s {
	case "set":
		if p.p >= len(ts) || ts[p.p].kind != 'w' {
			p.fail()
		}
		st.idx = getVar(ts[p.p].s)
		p.p++
		if !p.isOp("=") {
			p.fail()
		}
		p.p++
		st.exs = []*expr{p.expr()}
	case "out":
		st.exs = append(st.exs, p.expr())
		for p.isOp(",") {
			p.p++
			st.exs = append(st.exs, p.expr())
		}
	case "loop", "when":
		st.exs = []*expr{p.expr()}
	case "else", "end", "break":
	default:
		p.fail()
	}
	if p.p != len(ts) {
		return nil, false
	}
	return st, true
}

type runErr struct{}

var vals []uint32
var defd []bool

func eval(e *expr) uint32 {
	switch e.op {
	case "n":
		return e.num
	case "v":
		if !defd[e.idx] {
			panic(runErr{})
		}
		return vals[e.idx]
	case "neg":
		return -eval(e.l)
	case "#":
		return uint32(bits.OnesCount32(eval(e.l)))
	case "!":
		if eval(e.l) == 0 {
			return 1
		}
		return 0
	}
	a := eval(e.l)
	b := eval(e.r)
	switch e.op {
	case "<>":
		if a > b {
			return a
		}
		return b
	case "><":
		if a < b {
			return a
		}
		return b
	case "==":
		return b2u(a == b)
	case "!=":
		return b2u(a != b)
	case "<":
		return b2u(a < b)
	case ">":
		return b2u(a > b)
	case "+":
		return a + b
	case "-":
		return a - b
	case "*":
		return a * b
	case "/":
		if b == 0 {
			panic(runErr{})
		}
		return a / b
	case "%":
		if b == 0 {
			panic(runErr{})
		}
		return a % b
	case "~":
		return bits.RotateLeft32(a, int(b%32))
	}
	return 0
}

func b2u(b bool) uint32 {
	if b {
		return 1
	}
	return 0
}

var out *bufio.Writer
var errLine int

// returns true if break requested
func exec(body []*stmt) bool {
	for _, s := range body {
		errLine = s.line
		switch s.kind {
		case "set":
			v := eval(s.exs[0])
			vals[s.idx] = v
			defd[s.idx] = true
		case "out":
			vs := make([]uint32, len(s.exs))
			for i, e := range s.exs {
				vs[i] = eval(e)
			}
			for i, v := range vs {
				if i > 0 {
					out.WriteByte(' ')
				}
				out.WriteString(strconv.FormatUint(uint64(v), 10))
			}
			out.WriteByte('\n')
		case "loop":
			n := eval(s.exs[0])
			for ; n > 0; n-- {
				if exec(s.body) {
					break
				}
			}
		case "when":
			c := eval(s.exs[0])
			var br bool
			if c != 0 {
				br = exec(s.body)
			} else {
				br = exec(s.els)
			}
			if br {
				return true
			}
		case "break":
			return true
		}
	}
	return false
}

type blk struct {
	st      *stmt
	inElse  bool
	hasElse bool
}

func main() {
	if len(os.Args) != 2 {
		os.Exit(1)
	}
	data, err := os.ReadFile(os.Args[1])
	if err != nil {
		os.Exit(1)
	}
	// split lines
	var lines []string
	start := 0
	for i := 0; i < len(data); i++ {
		if data[i] == '\n' {
			lines = append(lines, string(data[start:i]))
			start = i + 1
		}
	}
	if start < len(data) {
		lines = append(lines, string(data[start:]))
	}

	var top []*stmt
	var stack []*blk
	cur := func() *[]*stmt {
		if len(stack) == 0 {
			return &top
		}
		b := stack[len(stack)-1]
		if b.inElse {
			return &b.st.els
		}
		return &b.st.body
	}
	bad := func(n int) {
		os.Stdout.WriteString("parse error line " + strconv.Itoa(n) + "\n")
		os.Exit(2)
	}
	for li, ln := range lines {
		n := li + 1
		if len(ln) > 1000 {
			bad(n)
		}
		for i := 0; i < len(ln); i++ {
			c := ln[i]
			if !(c == '\t' || c == '\r' || (c >= 0x20 && c <= 0x7e)) {
				bad(n)
			}
		}
		for i := 0; i < len(ln); i++ {
			if ln[i] == ';' {
				ln = ln[:i]
				break
			}
		}
		ts, ok := tokenize(ln)
		if !ok {
			bad(n)
		}
		if len(ts) == 0 {
			continue
		}
		if ts[0].kind != 'k' {
			bad(n)
		}
		st, ok := parseStmt(ts, n)
		if !ok {
			bad(n)
		}
		switch st.kind {
		case "loop", "when":
			if len(stack) >= 16 {
				bad(n)
			}
			*cur() = append(*cur(), st)
			stack = append(stack, &blk{st: st})
		case "else":
			if len(stack) == 0 {
				bad(n)
			}
			b := stack[len(stack)-1]
			if b.st.kind != "when" || b.hasElse {
				bad(n)
			}
			b.hasElse = true
			b.inElse = true
		case "end":
			if len(stack) == 0 {
				bad(n)
			}
			stack = stack[:len(stack)-1]
		case "break":
			found := false
			for _, b := range stack {
				if b.st.kind == "loop" {
					found = true
				}
			}
			if !found {
				bad(n)
			}
			*cur() = append(*cur(), st)
		default:
			*cur() = append(*cur(), st)
		}
	}
	if len(stack) > 0 {
		bad(stack[len(stack)-1].st.line)
	}

	vals = make([]uint32, len(varIdx))
	defd = make([]bool, len(varIdx))
	out = bufio.NewWriterSize(os.Stdout, 65536)
	code := 0
	func() {
		defer func() {
			if r := recover(); r != nil {
				if _, ok := r.(runErr); ok {
					out.WriteString("runtime error line " + strconv.Itoa(errLine) + "\n")
					code = 3
					return
				}
				panic(r)
			}
		}()
		exec(top)
	}()
	out.Flush()
	os.Exit(code)
}
