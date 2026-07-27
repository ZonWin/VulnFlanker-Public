package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"strings"
	"time"
)

type config struct {
	sources      string
	pageLimit    int
	limit        int
	valuableOnly bool
	proxy        string
	skipTLS      bool
	timeout      time.Duration
}

func main() {
	cfg := parseFlags()
	if cfg.proxy != "" {
		must(os.Setenv("HTTP_PROXY", cfg.proxy))
		must(os.Setenv("HTTPS_PROXY", cfg.proxy))
	}
	if cfg.skipTLS {
		must(os.Setenv("GO_SKIP_TLS_CHECK", "1"))
	}

	ctx, cancel := context.WithTimeout(context.Background(), cfg.timeout)
	defer cancel()

	grabbers, err := buildGrabbers(cfg.sources)
	if err != nil {
		fmt.Fprintf(os.Stderr, "watchvuln collector config error: %v\n", err)
		os.Exit(2)
	}

	encoder := json.NewEncoder(os.Stdout)
	totalOutput := 0
	errorCount := 0
	for _, grabber := range grabbers {
		provider := grabber.ProviderInfo()
		vulns, err := grabber.GetUpdate(ctx, cfg.pageLimit)
		if err != nil {
			errorCount++
			fmt.Fprintf(os.Stderr, "watchvuln source %s failed: %v\n", provider.Name, err)
			continue
		}
		fmt.Fprintf(os.Stderr, "watchvuln source %s collected %d records\n", provider.Name, len(vulns))
		for _, vuln := range vulns {
			if vuln == nil {
				continue
			}
			if vuln.Creator == nil {
				vuln.Creator = grabber
			}
			if cfg.valuableOnly && !grabber.IsValuable(vuln) {
				continue
			}
			if len(vuln.Reason) == 0 {
				vuln.Reason = []string{ReasonBuiltinCollection}
			}
			vuln.WatchVulnSource = provider.Name
			vuln.WatchVulnSourceDisplayName = provider.DisplayName
			if err := encoder.Encode(&RawMessage{
				Type:    RawMessageTypeVulnInfo,
				Content: vuln,
			}); err != nil {
				fmt.Fprintf(os.Stderr, "watchvuln encode failed: %v\n", err)
				os.Exit(1)
			}
			totalOutput++
			if cfg.limit > 0 && totalOutput >= cfg.limit {
				return
			}
		}
	}

	if totalOutput == 0 && errorCount > 0 {
		os.Exit(1)
	}
}

func parseFlags() config {
	var cfg config
	flag.StringVar(
		&cfg.sources,
		"sources",
		"avd,chaitin,oscs,ti,threatbook,seebug,struts2,kev,venustech",
		"enabled sources, comma-separated",
	)
	flag.IntVar(&cfg.pageLimit, "page-limit", 1, "page limit per source")
	flag.IntVar(&cfg.limit, "limit", 0, "maximum records to emit across all sources, 0 means unlimited")
	flag.BoolVar(&cfg.valuableOnly, "valuable-only", true, "emit only WatchVuln valuable records")
	flag.StringVar(&cfg.proxy, "proxy", "", "HTTP(S) proxy URL")
	flag.BoolVar(&cfg.skipTLS, "skip-tls-verify", false, "skip TLS certificate verification")
	flag.DurationVar(&cfg.timeout, "timeout", 300*time.Second, "collector timeout")
	flag.Parse()
	if cfg.pageLimit < 1 {
		cfg.pageLimit = 1
	}
	return cfg
}

func buildGrabbers(sources string) ([]Grabber, error) {
	var grabbers []Grabber
	for _, source := range strings.Split(sources, ",") {
		source = strings.ToLower(strings.TrimSpace(source))
		if source == "" {
			continue
		}
		switch source {
		case "avd", "aliyun-avd":
			grabbers = append(grabbers, NewAVDCrawler())
		case "chaitin":
			grabbers = append(grabbers, NewChaitinCrawler())
		case "nox", "ti", "qianxin-ti":
			grabbers = append(grabbers, NewTiCrawler())
		case "oscs":
			grabbers = append(grabbers, NewOSCSCrawler())
		case "seebug":
			grabbers = append(grabbers, NewSeebugCrawler())
		case "threatbook":
			grabbers = append(grabbers, NewThreatBookCrawler())
		case "struts2", "structs2":
			grabbers = append(grabbers, NewStruts2Crawler())
		case "kev", "cisa-kev":
			grabbers = append(grabbers, NewKEVCrawler())
		case "venustech":
			grabbers = append(grabbers, NewVenustechCrawler())
		default:
			return nil, fmt.Errorf("unsupported source %q", source)
		}
	}
	if len(grabbers) == 0 {
		return nil, fmt.Errorf("no watchvuln sources enabled")
	}
	return grabbers, nil
}

func must(err error) {
	if err != nil {
		panic(err)
	}
}
