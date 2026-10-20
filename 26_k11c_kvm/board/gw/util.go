package main

import (
	"errors"
	"io"
	"net/http"
	"strconv"
	"strings"
)

var (
	errNoSession  = errors.New("没有活动连接，先 GET /offer")
	errNoCandidate = errors.New("offer 里没有 ICE candidate")
)

func readAll(r *http.Request) (string, error) {
	defer r.Body.Close()
	b, err := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	return string(b), err
}

func oneLine(s string) string {
	return strings.ReplaceAll(strings.TrimSpace(s), "\n", " ")
}

func itoa(v int) string { return strconv.Itoa(v) }

// hasCandidate 判断 SDP 里到底有没有 gather 出 ICE candidate。
// 没有 candidate 的 offer 协商会"成功"但永远连不上，必须当场报错。
func hasCandidate(sdp string) bool {
	for _, l := range strings.Split(sdp, "\n") {
		if strings.HasPrefix(strings.TrimSpace(l), "a=candidate:") {
			return true
		}
	}
	return false
}
