import { request } from "@/api/client";
import type { RuleNumericConfig, RuleNumericConfigUpdate } from "@/api/types";

export function getRuleNumericConfig() {
  return request<RuleNumericConfig>("/api/v1/rule-config");
}

export function updateRuleNumericConfig(body: RuleNumericConfigUpdate) {
  return request<RuleNumericConfig>("/api/v1/rule-config", {
    method: "PATCH",
    body
  });
}

export function resetRuleNumericConfig() {
  return request<RuleNumericConfig>("/api/v1/rule-config/reset", {
    method: "POST"
  });
}
