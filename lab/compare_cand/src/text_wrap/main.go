package main

import (
	"fmt"
	"io"
	"os"
)

func main() {
	data, _ := io.ReadAll(os.Stdin)
	n := len(data)

	e := 0
	for e < n && data[e] != 10 {
		e++
	}
	if e < 1 || e > 3 {
		os.Exit(2)
	}
	var w int64
	for k := 0; k < e; k++ {
		c := data[k]
		if c < 48 || c > 57 {
			os.Exit(2)
		}
		w = w*10 + int64(c-48)
	}
	if w < 10 || w > 200 {
		os.Exit(2)
	}

	pos := e + 1
	if e >= n {
		pos = n
	}
	var paragraphs, lines, words, longest, h int64
	emittedAny := false
	inPara := false
	firstLine := false
	var curLen int64

	for {
		e = pos
		for e < n && data[e] != 10 {
			e++
		}
		a := pos
		blank := true
		for k := a; k < e; k++ {
			if data[k] != 32 {
				blank = false
				break
			}
		}
		if blank {
			if inPara {
				inPara = false
				curLen = 0
			}
		} else {
			k := a
			for k < e {
				c := data[k]
				if c == 32 || c == 9 {
					k++
					continue
				}
				ws := k
				for k < e {
					c = data[k]
					if c == 32 || c == 9 {
						break
					}
					k++
				}
				wl := int64(k - ws)
				words++
				if !inPara {
					inPara = true
					firstLine = true
					paragraphs++
				}
				if curLen == 0 {
					if firstLine {
						if emittedAny {
							h = (h*131 + 10) % 1000000007
							h = (h*131 + 10) % 1000000007
						}
						emittedAny = true
						firstLine = false
					} else {
						h = (h*131 + 10) % 1000000007
					}
					lines++
					curLen = wl
				} else if curLen+1+wl <= w {
					h = (h*131 + 32) % 1000000007
					curLen += 1 + wl
				} else {
					h = (h*131 + 10) % 1000000007
					lines++
					curLen = wl
				}
				for p := ws; p < k; p++ {
					h = (h*131 + int64(data[p])) % 1000000007
				}
				if curLen > longest {
					longest = curLen
				}
			}
		}
		if e >= n {
			break
		}
		pos = e + 1
	}

	fmt.Printf("paragraphs %d lines %d words %d longest %d hash %d\n",
		paragraphs, lines, words, longest, h)
}
