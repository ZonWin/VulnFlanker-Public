package main

import (
	"context"
	"fmt"
	"sort"
	"strings"
	"time"

	"github.com/imroc/req/v3"
)

const (
	kevURL      = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
	kevPageSize = 10
)

type KEVCrawler struct {
	client *req.Client
}

func NewKEVCrawler() Grabber {
	client := newHTTPClient()
	client.SetCommonHeader("Referer", "https://www.cisa.gov/known-exploited-vulnerabilities-catalog")
	return &KEVCrawler{client: client}
}

func (c *KEVCrawler) ProviderInfo() *Provider {
	return &Provider{
		Name:        "kev",
		DisplayName: "Known Exploited Vulnerabilities Catalog",
		Link:        "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
	}
}

func (c *KEVCrawler) IsValuable(info *VulnInfo) bool {
	return info.Severity == High || info.Severity == Critical
}

func (c *KEVCrawler) GetUpdate(ctx context.Context, pageLimit int) ([]*VulnInfo, error) {
	ctx, cancel := context.WithTimeout(ctx, 30*time.Second)
	defer cancel()

	var result kevResponse
	resp, err := c.client.R().SetContext(ctx).Get(kevURL)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode != 200 || !resp.IsSuccessState() {
		return nil, fmt.Errorf("unexpected KEV response status: %s", resp.Status)
	}
	if err := resp.UnmarshalJson(&result); err != nil {
		return nil, err
	}

	itemLimit := pageLimit * kevPageSize
	if itemLimit > len(result.Vulnerabilities) {
		itemLimit = len(result.Vulnerabilities)
	}
	sort.Slice(result.Vulnerabilities, func(i, j int) bool {
		return result.Vulnerabilities[i].DateAdded > result.Vulnerabilities[j].DateAdded
	})

	vulnInfos := make([]*VulnInfo, 0, itemLimit)
	for i := 0; i < itemLimit; i++ {
		vuln := result.Vulnerabilities[i]
		info := &VulnInfo{
			UniqueKey:   strings.TrimSpace(vuln.CveID) + "_KEV",
			Title:       strings.TrimSpace(vuln.VulnerabilityName),
			Description: strings.TrimSpace(vuln.ShortDescription),
			Severity:    Critical,
			CVE:         strings.TrimSpace(vuln.CveID),
			Solutions:   strings.TrimSpace(vuln.RequiredAction),
			Disclosure:  strings.TrimSpace(vuln.DateAdded),
			From:        "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
			Tags: []string{
				strings.TrimSpace(vuln.VendorProject),
				strings.TrimSpace(vuln.Product),
				"在野利用",
			},
			Creator: c,
		}
		if vuln.Notes != "" {
			for _, ref := range strings.Split(vuln.Notes, ";") {
				ref = strings.TrimSpace(ref)
				if ref != "" {
					info.References = append(info.References, ref)
				}
			}
		}
		vulnInfos = append(vulnInfos, info)
	}
	return vulnInfos, nil
}

type kevResponse struct {
	Title           string    `json:"title"`
	CatalogVersion  string    `json:"catalogVersion"`
	DateReleased    time.Time `json:"dateReleased"`
	Count           int       `json:"count"`
	Vulnerabilities []struct {
		CveID                      string `json:"cveID"`
		VendorProject              string `json:"vendorProject"`
		Product                    string `json:"product"`
		VulnerabilityName          string `json:"vulnerabilityName"`
		DateAdded                  string `json:"dateAdded"`
		ShortDescription           string `json:"shortDescription"`
		RequiredAction             string `json:"requiredAction"`
		DueDate                    string `json:"dueDate"`
		KnownRansomwareCampaignUse string `json:"knownRansomwareCampaignUse"`
		Notes                      string `json:"notes"`
	} `json:"vulnerabilities"`
}
