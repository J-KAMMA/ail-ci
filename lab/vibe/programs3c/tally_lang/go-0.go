package main

import (
	"bufio"
	"bytes"
	"fmt"
	"math/bits"
	"os"
	"strconv"
)

const (
	tNum = iota
	tWord
	tKw
	tOp
)

type token struct {
	kind int
	text string
	val  uint32
}

var keywords = map[string]bool{
	"set": true, "out": true, "loop": true, "when": true,
	"else": true, "end": true, "break": true,
}

var opList = []string{"<>", "><", "==", "!=", "<", ">", "+", "-", "*", "/", "%", "~", "#", "!", "(", ")", ",", "="}

func isWordStart(c byte) bool {
	return (c >= 'a' && c <= 'z') || c == '_'
}

func isWordChar(c byte) bool {
	return isWordStart(c) || (c >= '0' && c <= '9')
}

func validLine(b []byte) bool {
	if len(b) > 1000 {
		return false
	}
	for _, c := range b {
		if !(c == '\t' || c == '\r' || (c >= 0x20 && c <= 0x7E)) {
			return false
		}
	}
	return true
}

func tokenize(s []byte) ([]token, bool) {
	var toks []token
	n := len(s)
	i := 0
	for i < n {
		c := s[i]
		switch {
		case c == ' ' || c == '\t' || c == '\r':
			i++
		case c >= '0' && c <= '9':
			var v uint64
			for i < n && s[i] >= '0' && s[i] <= '9' {
				v = v*10 + uint64(s[i]-'0')
				if v > 4294967295 {
					return nil, false
				}
				i++
			}
			if i < n && ((s[i] >= 'a' && s[i] <= 'z') || s[i] == '_') {
				return nil, false
			}
			toks = append(toks, token{kind: tNum, val: uint32(v)})
		case isWordStart(c):
			start := i
			i++
			for i < n && isWordChar(s[i]) {
				i++
			}
			w := string(s[start:i])
			k := tWord
			if keywords[w] {
				k = tKw
			}
			toks = append(toks, token{kind: k, text: w})
		default:
			matched := false
			rest := s[i:]
			for _, op := range opList {
				if bytes.HasPrefix(rest, []byte(op)) {
					toks = append(toks, token{kind: tOp, text: op})
					i += len(op)
					matched = true
					break
				}
			}
			if !matched {
				return nil, false
			}
		}
	}
	return toks, true
}

// ---------- expressions ----------

type Expr interface {
	eval() uint32
}

type rtErr struct{}

type Num struct{ v uint32 }

func (e *Num) eval() uint32 { return e.v }

type Var struct{ name string }

func (e *Var) eval() uint32 {
	v, ok := vars[e.name]
	if !ok {
		panic(rtErr{})
	}
	return v
}

type Unary struct {
	op byte
	x  Expr
}

func (e *Unary) eval() uint32 {
	v := e.x.eval()
	switch e.op {
	case '-':
		return -v
	case '#':
		return uint32(bits.OnesCount32(v))
	case '!':
		if v == 0 {
			return 1
		}
		return 0
	}
	return 0
}

type Bin struct {
	op string
	l  Expr
	r  Expr
}

func b2u(b bool) uint32 {
	if b {
		return 1
	}
	return 0
}

func (e *Bin) eval() uint32 {
	x := e.l.eval()
	y := e.r.eval()
	switch e.op {
	case "<>":
		if x > y {
			return x
		}
		return y
	case "><":
		if x < y {
			return x
		}
		return y
	case "==":
		return b2u(x == y)
	case "!=":
		return b2u(x != y)
	case "<":
		return b2u(x < y)
	case ">":
		return b2u(x > y)
	case "+":
		return x + y
	case "-":
		return x - y
	case "*":
		return x * y
	case "/":
		if y == 0 {
			panic(rtErr{})
		}
		return x / y
	case "%":
		if y == 0 {
			panic(rtErr{})
		}
		return x % y
	case "~":
		s := y % 32
		if s == 0 {
			return x
		}
		return x<<s | x>>(32-s)
	}
	return 0
}

// ---------- parser ----------

type perr struct{}

type parser struct {
	toks  []token
	pos   int
	depth int
}

func (p *parser) fail() { panic(perr{}) }

func (p *parser) isOp(s string) bool {
	return p.pos < len(p.toks) && p.toks[p.pos].kind == tOp && p.toks[p.pos].text == s
}

func (p *parser) expectOp(s string) {
	if !p.isOp(s) {
		p.fail()
	}
	p.pos++
}

func (p *parser) end() {
	if p.pos != len(p.toks) {
		p.fail()
	}
}

func (p *parser) word() string {
	if p.pos < len(p.toks) && p.toks[p.pos].kind == tWord {
		t := p.toks[p.pos].text
		p.pos++
		return t
	}
	p.fail()
	return ""
}

func (p *parser) expr() Expr {
	return p.level1()
}

func (p *parser) level1() Expr {
	left := p.level2()
	for p.isOp("<>") || p.isOp("><") {
		op := p.toks[p.pos].text
		p.pos++
		right := p.level2()
		left = &Bin{op: op, l: left, r: right}
	}
	return left
}

func (p *parser) level2() Expr {
	left := p.level3()
	if p.isOp("==") || p.isOp("!=") || p.isOp("<") || p.isOp(">") {
		op := p.toks[p.pos].text
		p.pos++
		right := p.level3()
		return &Bin{op: op, l: left, r: right}
	}
	return left
}

func (p *parser) level3() Expr {
	left := p.level4()
	for p.isOp("+") || p.isOp("-") {
		op := p.toks[p.pos].text
		p.pos++
		right := p.level4()
		left = &Bin{op: op, l: left, r: right}
	}
	return left
}

func (p *parser) level4() Expr {
	left := p.level5()
	for p.isOp("*") || p.isOp("/") || p.isOp("%") {
		op := p.toks[p.pos].text
		p.pos++
		right := p.level5()
		left = &Bin{op: op, l: left, r: right}
	}
	return left
}

func (p *parser) level5() Expr {
	left := p.level6()
	if p.isOp("~") {
		p.pos++
		right := p.level5()
		return &Bin{op: "~", l: left, r: right}
	}
	return left
}

func (p *parser) level6() Expr {
	if p.isOp("-") || p.isOp("#") || p.isOp("!") {
		op := p.toks[p.pos].text
		p.pos++
		return &Unary{op: op[0], x: p.level6()}
	}
	return p.atom()
}

func (p *parser) atom() Expr {
	if p.pos >= len(p.toks) {
		p.fail()
	}
	t := p.toks[p.pos]
	switch t.kind {
	case tNum:
		p.pos++
		return &Num{v: t.val}
	case tWord:
		p.pos++
		return &Var{name: t.text}
	}
	if p.isOp("(") {
		p.pos++
		p.depth++
		if p.depth > 32 {
			p.fail()
		}
		e := p.expr()
		p.expectOp(")")
		p.depth--
		return e
	}
	p.fail()
	return nil
}

// ---------- statements ----------

const (
	kSet = iota
	kOut
	kLoop
	kWhen
	kBreak
)

type Stmt struct {
	kind     int
	line     int
	name     string
	exprs    []Expr
	body     []*Stmt
	elseBody []*Stmt
	hasElse  bool
	inElse   bool
}

type compiler struct {
	root  []*Stmt
	stack []*Stmt
}

func (c *compiler) add(s *Stmt) {
	if len(c.stack) == 0 {
		c.root = append(c.root, s)
		return
	}
	top := c.stack[len(c.stack)-1]
	if top.inElse {
		top.elseBody = append(top.elseBody, s)
	} else {
		top.body = append(top.body, s)
	}
}

func (c *compiler) hasLoop() bool {
	for _, s := range c.stack {
		if s.kind == kLoop {
			return true
		}
	}
	return false
}

func (c *compiler) line(lineNo int, toks []token) (ok bool) {
	if len(toks) == 0 {
		return true
	}
	defer func() {
		if recover() != nil {
			ok = false
		}
	}()
	p := &parser{toks: toks}
	head := toks[0]
	if head.kind != tKw {
		return false
	}
	p.pos = 1
	switch head.text {
	case "set":
		name := p.word()
		p.expectOp("=")
		e := p.expr()
		p.end()
		c.add(&Stmt{kind: kSet, line: lineNo, name: name, exprs: []Expr{e}})
	case "out":
		es := []Expr{p.expr()}
		for p.isOp(",") {
			p.pos++
			es = append(es, p.expr())
		}
		p.end()
		c.add(&Stmt{kind: kOut, line: lineNo, exprs: es})
	case "loop", "when":
		e := p.expr()
		p.end()
		if len(c.stack) >= 16 {
			return false
		}
		kind := kLoop
		if head.text == "when" {
			kind = kWhen
		}
		s := &Stmt{kind: kind, line: lineNo, exprs: []Expr{e}}
		c.add(s)
		c.stack = append(c.stack, s)
	case "else":
		p.end()
		if len(c.stack) == 0 {
			return false
		}
		top := c.stack[len(c.stack)-1]
		if top.kind != kWhen || top.hasElse {
			return false
		}
		top.hasElse = true
		top.inElse = true
	case "end":
		p.end()
		if len(c.stack) == 0 {
			return false
		}
		c.stack = c.stack[:len(c.stack)-1]
	case "break":
		p.end()
		if !c.hasLoop() {
			return false
		}
		c.add(&Stmt{kind: kBreak, line: lineNo})
	default:
		return false
	}
	return true
}

// ---------- execution ----------

var (
	vars    = map[string]uint32{}
	out     *bufio.Writer
	curLine int
)

const (
	ctrlNormal = iota
	ctrlBreak
)

func exec(body []*Stmt) int {
	for _, s := range body {
		switch s.kind {
		case kSet:
			curLine = s.line
			v := s.exprs[0].eval()
			vars[s.name] = v
		case kOut:
			curLine = s.line
			vals := make([]uint32, len(s.exprs))
			for i, e := range s.exprs {
				vals[i] = e.eval()
			}
			for i, v := range vals {
				if i > 0 {
					out.WriteByte(' ')
				}
				out.WriteString(strconv.FormatUint(uint64(v), 10))
			}
			out.WriteByte('\n')
		case kLoop:
			curLine = s.line
			n := uint64(s.exprs[0].eval())
			for i := uint64(0); i < n; i++ {
				if exec(s.body) == ctrlBreak {
					break
				}
			}
		case kWhen:
			curLine = s.line
			if s.exprs[0].eval() != 0 {
				if exec(s.body) == ctrlBreak {
					return ctrlBreak
				}
			} else if s.hasElse {
				if exec(s.elseBody) == ctrlBreak {
					return ctrlBreak
				}
			}
		case kBreak:
			return ctrlBreak
		}
	}
	return ctrlNormal
}

func runProgram(root []*Stmt) (failed bool) {
	defer func() {
		if r := recover(); r != nil {
			if _, ok := r.(rtErr); ok {
				failed = true
				return
			}
			panic(r)
		}
	}()
	exec(root)
	return false
}

func parseError(n int) {
	fmt.Printf("parse error line %d\n", n)
	os.Exit(2)
}

func main() {
	if len(os.Args) != 2 {
		os.Exit(1)
	}
	data, err := os.ReadFile(os.Args[1])
	if err != nil {
		os.Exit(1)
	}

	lines := bytes.Split(data, []byte{'\n'})
	if len(lines) > 0 && len(lines[len(lines)-1]) == 0 {
		lines = lines[:len(lines)-1]
	}

	c := &compiler{}
	for i, raw := range lines {
		lineNo := i + 1
		if !validLine(raw) {
			parseError(lineNo)
		}
		code := raw
		if idx := bytes.IndexByte(raw, ';'); idx >= 0 {
			code = raw[:idx]
		}
		toks, ok := tokenize(code)
		if !ok {
			parseError(lineNo)
		}
		if !c.line(lineNo, toks) {
			parseError(lineNo)
		}
	}
	if len(c.stack) > 0 {
		parseError(c.stack[len(c.stack)-1].line)
	}

	out = bufio.NewWriter(os.Stdout)
	failed := runProgram(c.root)
	if failed {
		out.Flush()
		fmt.Printf("runtime error line %d\n", curLine)
		os.Exit(3)
	}
	out.Flush()
	os.Exit(0)
}
