package main

import (
	"context"
	"strconv"
	"strings"

	"github.com/imroc/req/v3"
)

type TiCrawler struct {
	client *req.Client
}

func NewTiCrawler() Grabber {
	client := wrapAPIClient(newHTTPClient())
	client.SetCommonHeader("Referer", "https://ti.qianxin.com/")
	client.SetCommonHeader("Origin", "https://ti.qianxin.com")
	return &TiCrawler{client: client}
}

func (t *TiCrawler) ProviderInfo() *Provider {
	return &Provider{
		Name:        "qianxin-ti",
		DisplayName: "奇安信威胁情报中心",
		Link:        "https://ti.qianxin.com/",
	}
}

func (t *TiCrawler) GetUpdate(ctx context.Context, _ int) ([]*VulnInfo, error) {
	resp, err := t.client.R().SetContext(ctx).Post("https://ti.qianxin.com/alpha-api/v2/vuln/one-day")
	if err != nil {
		return nil, err
	}
	var body tiOneDayResponse
	if err = resp.UnmarshalJson(&body); err != nil {
		return nil, err
	}
	results := make([]*VulnInfo, 0, len(body.Data.KeyVulnAdd))
	for _, item := range body.Data.KeyVulnAdd {
		tags := make([]string, 0, len(item.Tag))
		for _, tag := range item.Tag {
			tagName := strings.TrimSpace(tag.Name)
			if tagName != "" {
				tags = append(tags, tagName)
			}
		}
		severity := Low
		switch item.RatingLevel {
		case "中危":
			severity = Medium
		case "高危":
			severity = High
		case "极危":
			severity = Critical
		}
		results = append(results, &VulnInfo{
			UniqueKey:   item.QvdCode,
			Title:       item.VulnName,
			Description: item.Description,
			Severity:    severity,
			CVE:         item.CveCode,
			Disclosure:  item.PublishTime,
			Tags:        tags,
			From:        "https://ti.qianxin.com/vulnerability/detail/" + strconv.Itoa(item.ID),
			Creator:     t,
		})
	}

	seen := map[string]bool{}
	unique := make([]*VulnInfo, 0, len(results))
	for _, item := range results {
		if item.UniqueKey == "" || seen[item.UniqueKey] {
			continue
		}
		seen[item.UniqueKey] = true
		unique = append(unique, item)
	}
	return unique, nil
}

func (t *TiCrawler) IsValuable(info *VulnInfo) bool {
	if info.Severity != High && info.Severity != Critical {
		return false
	}
	for _, tag := range info.Tags {
		if tag == "奇安信CERT验证" || tag == "POC公开" || tag == "EXP公开" || tag == "技术细节公布" {
			return true
		}
	}
	return false
}

type tiVulnDetail struct {
	ID          int    `json:"id"`
	VulnName    string `json:"vuln_name"`
	QvdCode     string `json:"qvd_code"`
	CveCode     string `json:"cve_code"`
	PublishTime string `json:"publish_time"`
	Description string `json:"description"`
	RatingLevel string `json:"rating_level"`
	Tag         []struct {
		Name string `json:"name"`
	} `json:"tag"`
}

type tiOneDayResponse struct {
	Data struct {
		KeyVulnAdd []tiVulnDetail `json:"key_vuln_add"`
	} `json:"data"`
}
