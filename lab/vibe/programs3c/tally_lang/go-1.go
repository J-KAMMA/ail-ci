package main

import (
	"bufio"
	"fmt"
	"math/bits"
	"os"
	"strconv"
	"strings"
)

type parseFail struct{}
type runFail struct{}

const (
	tNum = iota
	tWord
	tOp
)

const (
	ekNum = iota
	ekVar
	ekUn
	ekBin
)

const (
	sSet = iota
	sOut
	sLoop
	sWhen
	sBreak
)

type token struct {
	kind int
	text string
	num  uint32
}

type Expr struct {
	kind int
	num  uint32
	name string
	op   string
	a, b *Expr
}

type Stmt struct {
	kind     int
	line     int
	name     string
	exprs    []*Expr
	body     []*Stmt
	elseBody []*Stmt
	inElse   bool
}

var (
	keywords = map[string]bool{
		"set": true, "out": true, "loop": true, "when": true,
		"else": true, "end": true, "break": true,
	}
	vars    = map[string]uint32{}
	root    []*Stmt
	stack   []*Stmt
	curLine int
	wr      *bufio.Writer
)

func pfail() { panic(parseFail{}) }
func rtfail() { panic(runFail{}) }

func isDigit(c byte) bool { return c >= '0' && c <= '9' }
func isLower(c byte) bool { return c >= 'a' && c <= 'z' }

func tokenize(s string) []token {
	var toks []token
	n := len(s)
	i := 0
	for i < n {
		c := s[i]
		switch {
		case c == ' ' || c == '\t' || c == '\r':
			i++
		case isDigit(c):
			j := i
			for j < n && isDigit(s[j]) {
				j++
			}
			if j < n && (isLower(s[j]) || s[j] == '_') {
				pfail()
			}
			var v uint64
			for k := i; k < j; k++ {
				v = v*10 + uint64(s[k]-'0')
				if v > 4294967295 {
					pfail()
				}
			}
			toks = append(toks, token{kind: tNum, text: s[i:j], num: uint32(v)})
			i = j
		case isLower(c) || c == '_':
			j := i + 1
			for j < n && (isLower(s[j]) || isDigit(s[j]) || s[j] == '_') {
				j++
			}
			toks = append(toks, token{kind: tWord, text: s[i:j]})
			i = j
		default:
			matched := ""
			if i+1 < n {
				two := s[i : i+2]
				if two == "<>" || two == "><" || two == "==" || two == "!=" {
					matched = two
				}
			}
			if matched == "" && strings.IndexByte("<>+-*/%~#!(),=", c) >= 0 {
				matched = s[i : i+1]
			}
			if matched == "" {
				pfail()
			}
			toks = append(toks, token{kind: tOp, text: matched})
			i += len(matched)
		}
	}
	return toks
}

type parser struct {
	toks  []token
	pos   int
	depth int
}

func (p *parser) isOp(s string) bool {
	return p.pos < len(p.toks) && p.toks[p.pos].kind == tOp && p.toks[p.pos].text == s
}

func (p *parser) isCmp() bool {
	return p.isOp("==") || p.isOp("!=") || p.isOp("<") || p.isOp(">")
}

func (p *parser) finish() {
	if p.pos != len(p.toks) {
		pfail()
	}
}

func (p *parser) parseExpr() *Expr {
	l := p.parseCmp()
	for p.isOp("<>") || p.isOp("><") {
		op := p.toks[p.pos].text
		p.pos++
		r := p.parseCmp()
		l = &Expr{kind: ekBin, op: op, a: l, b: r}
	}
	return l
}

func (p *parser) parseCmp() *Expr {
	l := p.parseAdd()
	if p.isCmp() {
		op := p.toks[p.pos].text
		p.pos++
		r := p.parseAdd()
		l = &Expr{kind: ekBin, op: op, a: l, b: r}
		if p.isCmp() {
			pfail()
		}
	}
	return l
}

func (p *parser) parseAdd() *Expr {
	l := p.parseMul()
	for p.isOp("+") || p.isOp("-") {
		op := p.toks[p.pos].text
		p.pos++
		r := p.parseMul()
		l = &Expr{kind: ekBin, op: op, a: l, b: r}
	}
	return l
}

func (p *parser) parseMul() *Expr {
	l := p.parseRot()
	for p.isOp("*") || p.isOp("/") || p.isOp("%") {
		op := p.toks[p.pos].text
		p.pos++
		r := p.parseRot()
		l = &Expr{kind: ekBin, op: op, a: l, b: r}
	}
	return l
}

func (p *parser) parseRot() *Expr {
	a := p.parseUnary()
	if p.isOp("~") {
		p.pos++
		b := p.parseRot()
		return &Expr{kind: ekBin, op: "~", a: a, b: b}
	}
	return a
}

func (p *parser) parseUnary() *Expr {
	if p.isOp("-") || p.isOp("#") || p.isOp("!") {
		op := p.toks[p.pos].text
		p.pos++
		return &Expr{kind: ekUn, op: op, a: p.parseUnary()}
	}
	return p.parsePrimary()
}

func (p *parser) parsePrimary() *Expr {
	if p.pos >= len(p.toks) {
		pfail()
	}
	t := p.toks[p.pos]
	switch t.kind {
	case tNum:
		p.pos++
		return &Expr{kind: ekNum, num: t.num}
	case tWord:
		if keywords[t.text] {
			pfail()
		}
		p.pos++
		return &Expr{kind: ekVar, name: t.text}
	}
	if t.kind == tOp && t.text == "(" {
		p.pos++
		p.depth++
		if p.depth > 32 {
			pfail()
		}
		e := p.parseExpr()
		if !p.isOp(")") {
			pfail()
		}
		p.pos++
		p.depth--
		return e
	}
	pfail()
	return nil
}

func addStmt(st *Stmt) {
	if len(stack) == 0 {
		root = append(root, st)
		return
	}
	top := stack[len(stack)-1]
	if top.inElse {
		top.elseBody = append(top.elseBody, st)
	} else {
		top.body = append(top.body, st)
	}
}

func handleLine(lineNo int, raw string) {
	if len(raw) > 1000 {
		pfail()
	}
	for i := 0; i < len(raw); i++ {
		c := raw[i]
		if c != '\t' && c != '\r' && (c < 0x20 || c > 0x7E) {
			pfail()
		}
	}
	s := raw
	if k := strings.IndexByte(s, ';'); k >= 0 {
		s = s[:k]
	}
	toks := tokenize(s)
	if len(toks) == 0 {
		return
	}
	p := &parser{toks: toks, pos: 1}
	head := toks[0]
	if head.kind != tWord || !keywords[head.text] {
		pfail()
	}
	switch head.text {
	case "set":
		if len(toks) < 2 || toks[1].kind != tWord || keywords[toks[1].text] {
			pfail()
		}
		name := toks[1].text
		p.pos = 2
		if !p.isOp("=") {
			pfail()
		}
		p.pos++
		e := p.parseExpr()
		p.finish()
		addStmt(&Stmt{kind: sSet, line: lineNo, name: name, exprs: []*Expr{e}})
	case "out":
		var es []*Expr
		es = append(es, p.parseExpr())
		for p.isOp(",") {
			p.pos++
			es = append(es, p.parseExpr())
		}
		p.finish()
		addStmt(&Stmt{kind: sOut, line: lineNo, exprs: es})
	case "loop", "when":
		e := p.parseExpr()
		p.finish()
		if len(stack) >= 16 {
			pfail()
		}
		kind := sLoop
		if head.text == "when" {
			kind = sWhen
		}
		st := &Stmt{kind: kind, line: lineNo, exprs: []*Expr{e}}
		addStmt(st)
		stack = append(stack, st)
	case "else":
		p.finish()
		if len(stack) == 0 {
			pfail()
		}
		top := stack[len(stack)-1]
		if top.kind != sWhen || top.inElse {
			pfail()
		}
		top.inElse = true
	case "end":
		p.finish()
		if len(stack) == 0 {
			pfail()
		}
		stack = stack[:len(stack)-1]
	case "break":
		p.finish()
		ok := false
		for _, f := range stack {
			if f.kind == sLoop {
				ok = true
			}
		}
		if !ok {
			pfail()
		}
		addStmt(&Stmt{kind: sBreak, line: lineNo})
	default:
		pfail()
	}
}

func tryLine(lineNo int, raw string) (ok bool) {
	defer func() {
		if r := recover(); r != nil {
			if _, is := r.(parseFail); is {
				ok = false
				return
			}
			panic(r)
		}
	}()
	handleLine(lineNo, raw)
	return true
}

func b2u(b bool) uint32 {
	if b {
		return 1
	}
	return 0
}

func evalExpr(e *Expr) uint32 {
	switch e.kind {
	case ekNum:
		return e.num
	case ekVar:
		v, ok := vars[e.name]
		if !ok {
			rtfail()
		}
		return v
	case ekUn:
		x := evalExpr(e.a)
		switch e.op {
		case "-":
			return 0 - x
		case "#":
			return uint32(bits.OnesCount32(x))
		case "!":
			return b2u(x == 0)
		}
		return x
	case ekBin:
		a := evalExpr(e.a)
		b := evalExpr(e.b)
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
				rtfail()
			}
			return a / b
		case "%":
			if b == 0 {
				rtfail()
			}
			return a % b
		case "~":
			s := b % 32
			if s == 0 {
				return a
			}
			return (a << s) | (a >> (32 - s))
		}
	}
	return 0
}

func execBlock(stmts []*Stmt) bool {
	for _, st := range stmts {
		switch st.kind {
		case sSet:
			curLine = st.line
			v := evalExpr(st.exprs[0])
			vars[st.name] = v
		case sOut:
			curLine = st.line
			vals := make([]uint32, len(st.exprs))
			for i, e := range st.exprs {
				vals[i] = evalExpr(e)
			}
			for i, v := range vals {
				if i > 0 {
					wr.WriteByte(' ')
				}
				wr.WriteString(strconv.FormatUint(uint64(v), 10))
			}
			wr.WriteByte('\n')
		case sLoop:
			curLine = st.line
			n := uint64(evalExpr(st.exprs[0]))
			for i := uint64(0); i < n; i++ {
				if execBlock(st.body) {
					break
				}
			}
		case sWhen:
			curLine = st.line
			c := evalExpr(st.exprs[0])
			var brk bool
			if c != 0 {
				brk = execBlock(st.body)
			} else {
				brk = execBlock(st.elseBody)
			}
			if brk {
				return true
			}
		case sBreak:
			return true
		}
	}
	return false
}

func runAll() (failed bool) {
	defer func() {
		if r := recover(); r != nil {
			if _, ok := r.(runFail); ok {
				failed = true
				return
			}
			panic(r)
		}
	}()
	execBlock(root)
	return false
}

func main() {
	if len(os.Args) != 2 {
		os.Exit(1)
	}
	data, err := os.ReadFile(os.Args[1])
	if err != nil {
		os.Exit(1)
	}
	lines := strings.Split(string(data), "\n")
	if len(lines) > 0 && lines[len(lines)-1] == "" {
		lines = lines[:len(lines)-1]
	}

	bad := 0
	for i, raw := range lines {
		if !tryLine(i+1, raw) {
			bad = i + 1
			break
		}
	}
	if bad == 0 && len(stack) > 0 {
		bad = stack[len(stack)-1].line
	}
	if bad != 0 {
		fmt.Printf("parse error line %d\n", bad)
		os.Exit(2)
	}

	wr = bufio.NewWriter(os.Stdout)
	failed := runAll()
	wr.Flush()
	if failed {
		fmt.Printf("runtime error line %d\n", curLine)
		os.Exit(3)
	}
	os.Exit(0)
}
