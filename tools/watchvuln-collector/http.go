package main

import (
	"context"
	"crypto/tls"
	"errors"
	"math/rand"
	"os"
	"sync"
	"time"

	"github.com/imroc/req/v3"
)

var (
	uaRand = rand.New(rand.NewSource(time.Now().UnixNano()))
	uaMu   sync.Mutex
)

func newHTTPClient() *req.Client {
	client := req.C()
	client.
		ImpersonateChrome().
		SetCommonHeader("User-Agent", randUserAgent()).
		SetTimeout(10 * time.Second).
		SetCommonRetryCount(3).
		SetCookieJar(nil).
		SetCommonRetryInterval(func(resp *req.Response, attempt int) time.Duration {
			if errors.Is(resp.Err, context.Canceled) {
				return 0
			}
			return 5 * time.Second
		}).
		SetCommonRetryHook(func(resp *req.Response, err error) {
			if err != nil && !errors.Is(err, context.Canceled) {
				client.Headers.Set("User-Agent", randUserAgent())
			}
		}).
		SetCommonRetryCondition(func(resp *req.Response, err error) bool {
			if err != nil {
				return !errors.Is(err, context.Canceled)
			}
			return false
		})
	if os.Getenv("GO_SKIP_TLS_CHECK") != "" {
		client.SetTLSClientConfig(&tls.Config{InsecureSkipVerify: true}) //nolint:gosec
	}
	return client
}

func wrapAPIClient(client *req.Client) *req.Client {
	return client.SetCommonHeaders(map[string]string{
		"Accept":             "application/json, text/plain, */*",
		"Accept-Language":    "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
		"Content-Type":       "application/json",
		"Sec-Fetch-Dest":     "empty",
		"Sec-Fetch-Mode":     "cors",
		"Sec-Fetch-Site":     "same-origin",
		"sec-ch-ua":          `"Microsoft Edge";v="137", "Not(A:Brand";v="8", "Chromium";v="137"`,
		"sec-ch-ua-mobile":   `?0`,
		"sec-ch-ua-platform": `"Windows"`,
	})
}

func randUserAgent() string {
	uaMu.Lock()
	defer uaMu.Unlock()
	if len(allUserAgents) == 0 {
		return ""
	}
	return allUserAgents[uaRand.Intn(len(allUserAgents))]
}

var allUserAgents = []string{
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0",
	"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
	"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15",
	"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0",
}
