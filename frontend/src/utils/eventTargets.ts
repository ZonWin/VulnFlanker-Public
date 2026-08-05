import type { SystemEvent } from "@/api/types";

export function systemEventTarget(event: SystemEvent): string | null {
  if (event.target_type === "asset" && event.target_id) {
    return `/assets/${event.target_id}`;
  }
  if (event.target_type === "risk_evaluation") {
    const ids = event.target_query.match_result_ids;
    if (Array.isArray(ids) && ids.length === 1 && typeof ids[0] === "string") {
      return `/matching/${ids[0]}`;
    }
    return "/risk-queue";
  }
  if (event.target_type === "intel_run") {
    const runId = event.target_id;
    return runId ? `/intel?run_id=${encodeURIComponent(runId)}` : "/intel";
  }
  return null;
}
