from __future__ import annotations

from app.matching.base import MatchContext, MatchRule, RuleResult, rule_confidence
from app.matching.product_aliases import product_aliases
from app.matching.utils import product_candidates


class ProductRule(MatchRule):
    rule_name = "product_rule"

    def evaluate(self, context: MatchContext) -> RuleResult:
        product = context.vulnerability.get("product")
        if not product:
            confidence = rule_confidence(context, self.rule_name, "missing_product", 0.2)
            return RuleResult(
                status="needs_review",
                confidence=confidence,
                reason="Vulnerability has no normalized product field.",
                evidence=[
                    {
                        "type": "product_match",
                        "summary": "No vulnerability product is available for candidate selection.",
                    }
                ],
                rule_name=self.rule_name,
            )

        aliases = product_aliases(product)
        candidates = product_candidates(context)
        if not candidates:
            confidence = rule_confidence(context, self.rule_name, "no_candidate", 0.82)
            return RuleResult(
                status="not_affected",
                confidence=confidence,
                reason=f"No asset component or exposure matched product {product}.",
                evidence=[
                    {
                        "type": "product_match",
                        "summary": f"No observed asset component or exposure matched {product}.",
                        "details": {"expected_product": product, "aliases": aliases},
                    }
                ],
                rule_name=self.rule_name,
            )

        confidence = rule_confidence(context, self.rule_name, "matched", 0.78)
        evidence = []
        for candidate in candidates:
            label = candidate.get("component_name") or candidate.get("product")
            product_matches = candidate.get("product_matches") or []
            evidence.append(
                {
                    "type": "product_match",
                    "summary": f"Observed {candidate['kind']} matched product {product}: {label}.",
                    "raw_ref": candidate.get("id"),
                    "confidence": confidence,
                    "details": {
                        "kind": candidate["kind"],
                        "name": label,
                        "version": candidate.get("version"),
                        "expected_product": product,
                        "aliases": aliases,
                        "matched_aliases": sorted(
                            {
                                str(match.get("expected"))
                                for match in product_matches
                                if match.get("expected")
                            }
                        ),
                        "matched_fields": product_matches,
                    },
                }
            )
        return RuleResult(
            status="affected",
            confidence=confidence,
            reason=f"Asset has observed evidence for product {product}.",
            evidence=evidence,
            rule_name=self.rule_name,
        )
