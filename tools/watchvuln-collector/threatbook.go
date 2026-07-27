package main

import (
	"context"
	"time"

	"github.com/imroc/req/v3"
)

type ThreatBookCrawler struct {
	client *req.Client
}

func NewThreatBookCrawler() Grabber {
	client := newHTTPClient()
	client.SetCommonHeader("Referer", "https://x.threatbook.com/v5/vulIntelligence")
	client.SetCommonHeader("Origin", "https://mp.weixin.qq.com/")
	client.SetCommonHeader("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6")
	return &ThreatBookCrawler{client: client}
}

func (t *ThreatBookCrawler) ProviderInfo() *Provider {
	return &Provider{
		Name:        "threatbook",
		DisplayName: "微步在线研究响应中心-漏洞通告",
		Link:        "https://x.threatbook.com/v5/vul/",
	}
}

func (t *ThreatBookCrawler) GetUpdate(ctx context.Context, _ int) ([]*VulnInfo, error) {
	ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	resp, err := t.client.R().SetContext(ctx).Get("https://x.threatbook.com/v5/node/vul_module/homePage")
	if err != nil {
		return nil, err
	}
	var body threatBookHomepage
	if err = resp.UnmarshalJson(&body); err != nil {
		return nil, err
	}
	results := make([]*VulnInfo, 0, len(body.Data.HighRisk))
	for _, item := range body.Data.HighRisk {
		disclosure := item.VulnPublishTime
		if disclosure == "" {
			disclosure = item.VulnUpdateTime
		}
		var tags []string
		if item.Is0Day {
			tags = append(tags, "0day")
		}
		if item.PocExist {
			tags = append(tags, "有Poc")
		}
		if item.Premium {
			tags = append(tags, "有漏洞分析")
		}
		if item.Solution {
			tags = append(tags, "有修复方案")
		}
		results = append(results, &VulnInfo{
			UniqueKey:  item.ID,
			Title:      item.VulnNameZh,
			Severity:   Critical,
			Disclosure: disclosure,
			Tags:       tags,
			From:       t.ProviderInfo().Link + item.ID,
			Creator:    t,
		})
	}
	return results, nil
}

func (t *ThreatBookCrawler) IsValuable(info *VulnInfo) bool {
	hasPoc := false
	hasAnalysis := false
	for _, tag := range info.Tags {
		if tag == "有Poc" {
			hasPoc = true
		}
		if tag == "有漏洞分析" {
			hasAnalysis = true
		}
	}
	if !hasPoc || !hasAnalysis || info.Disclosure == "" {
		return false
	}
	disclosure, err := time.Parse("2006-01-02", info.Disclosure)
	if err != nil {
		return false
	}
	return time.Since(disclosure) <= 14*24*time.Hour
}

type threatBookHomepage struct {
	Data struct {
		HighRisk []struct {
			ID              string `json:"id"`
			VulnNameZh      string `json:"vuln_name_zh"`
			VulnUpdateTime  string `json:"vuln_update_time"`
			VulnPublishTime string `json:"vuln_publish_time,omitempty"`
			PocExist        bool   `json:"pocExist"`
			Solution        bool   `json:"solution"`
			Premium         bool   `json:"premium"`
			Is0Day          bool   `json:"is0day,omitempty"`
		} `json:"highrisk"`
	} `json:"data"`
}
