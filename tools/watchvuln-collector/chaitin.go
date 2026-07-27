package main

import (
	"context"
	"fmt"
	"strings"
	"time"
	"unicode"

	"github.com/imroc/req/v3"
)

type ChaitinCrawler struct {
	client *req.Client
}

func NewChaitinCrawler() Grabber {
	client := wrapAPIClient(newHTTPClient())
	client.SetCommonHeader("Referer", "https://stack.chaitin.com/vuldb/index")
	client.SetCommonHeader("Origin", "https://stack.chaitin.com")
	return &ChaitinCrawler{client: client}
}

func (c *ChaitinCrawler) ProviderInfo() *Provider {
	return &Provider{
		Name:        "chaitin",
		DisplayName: "长亭漏洞库",
		Link:        "https://stack.chaitin.com/vuldb/index",
	}
}

func (c *ChaitinCrawler) GetUpdate(ctx context.Context, pageLimit int) ([]*VulnInfo, error) {
	var results []*VulnInfo
	urlTpl := "https://stack.chaitin.com/api/v2/vuln/list/?limit=15&offset=%d&search=CT-"
	for page := 0; page < pageLimit; page++ {
		var body chaitinResponse
		_, err := c.client.R().
			SetSuccessResult(&body).
			SetContext(ctx).
			Get(fmt.Sprintf(urlTpl, page*15))
		if err != nil {
			return results, err
		}
		for _, item := range body.Data.List {
			severity := Low
			switch item.Severity {
			case "medium":
				severity = Medium
			case "high":
				severity = High
			case "critical":
				severity = Critical
			}
			var refs []string
			if item.References != nil {
				for _, ref := range strings.Split(*item.References, "\n") {
					ref = strings.TrimSpace(ref)
					if ref != "" {
						refs = append(refs, ref)
					}
				}
			}
			cveID := ""
			if item.CveID != nil {
				cveID = strings.TrimSpace(*item.CveID)
			}
			results = append(results, &VulnInfo{
				UniqueKey:   item.CtID,
				Title:       item.Title,
				Description: item.Summary,
				Severity:    severity,
				CVE:         cveID,
				Disclosure:  item.CreatedAt.Format("2006-01-02"),
				References:  refs,
				From:        "https://stack.chaitin.com/vuldb/detail/" + item.ID,
				Creator:     c,
			})
		}
	}
	return results, nil
}

func (c *ChaitinCrawler) IsValuable(info *VulnInfo) bool {
	if info.Severity != High && info.Severity != Critical {
		return false
	}
	return containsChinese(info.Title)
}

func containsChinese(value string) bool {
	for _, item := range value {
		if unicode.Is(unicode.Han, item) {
			return true
		}
	}
	return false
}

type chaitinResponse struct {
	Data struct {
		List []struct {
			ID         string    `json:"id"`
			Title      string    `json:"title"`
			Summary    string    `json:"summary"`
			Severity   string    `json:"severity"`
			CtID       string    `json:"ct_id"`
			CveID      *string   `json:"cve_id"`
			References *string   `json:"references"`
			CreatedAt  time.Time `json:"created_at"`
		} `json:"list"`
	} `json:"data"`
	Code int `json:"code"`
}
