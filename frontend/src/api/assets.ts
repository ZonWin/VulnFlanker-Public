import { request, type QueryParams } from "@/api/client";
import type {
  AssetDetail,
  AssetFirewallList,
  AssetFirewallRaw,
  AssetFirewallRuleList,
  AssetListPage,
  AssetMetadataUpdate,
  AssetOwnershipStatus,
  FirewallEngine,
  FirewallScope,
  LifecycleActionResult
} from "@/api/types";

export interface AssetOwnershipQuery extends QueryParams {
  business_system_id?: string;
  responsible_person_id?: string;
  responsibility_team_id?: string;
  ownership_status?: AssetOwnershipStatus;
  search?: string;
  criticality?: string;
  environment_type?: string;
  exposure_type?: string;
  platform?: string;
  os_family?: string;
  offset?: number;
  limit?: number;
}

export function getAssets(query: AssetOwnershipQuery = {}) {
  return request<AssetListPage>("/api/v1/assets", {
    query: { ...query, paged: true }
  });
}

export function getAsset(assetId: string) {
  return request<AssetDetail>(`/api/v1/assets/${assetId}`);
}

export function getAssetFirewalls(assetId: string) {
  return request<AssetFirewallList>(`/api/v1/assets/${assetId}/firewalls`);
}

export interface AssetFirewallRuleQuery extends QueryParams {
  scope?: FirewallScope;
  family?: string;
  action?: string;
  protocol?: string;
  search?: string;
  page?: number;
  page_size?: number;
}

export function getAssetFirewallRules(
  assetId: string,
  engine: FirewallEngine,
  query: AssetFirewallRuleQuery = {}
) {
  return request<AssetFirewallRuleList>(
    `/api/v1/assets/${assetId}/firewalls/${engine}/rules`,
    { query }
  );
}

export function getAssetFirewallRaw(
  assetId: string,
  engine: FirewallEngine,
  scope: FirewallScope
) {
  return request<AssetFirewallRaw>(
    `/api/v1/assets/${assetId}/firewalls/${engine}/raw`,
    { query: { scope } }
  );
}

export function bindAssetBusinessSystem(
  assetId: string,
  businessSystemId: string | null
) {
  return request<AssetDetail>(`/api/v1/assets/${assetId}/business-system`, {
    method: "PUT",
    body: { business_system_id: businessSystemId }
  });
}

export function bulkBindAssetBusinessSystems(
  assetIds: string[],
  businessSystemId: string | null
) {
  return request<{
    updated_count: number;
    asset_ids: string[];
    business_system_id: string | null;
  }>("/api/v1/assets/business-system-bindings", {
    method: "POST",
    body: { asset_ids: assetIds, business_system_id: businessSystemId }
  });
}

export function updateAsset(assetId: string, body: AssetMetadataUpdate) {
  return request<AssetDetail>(`/api/v1/assets/${assetId}`, {
    method: "PATCH",
    body
  });
}

export function deleteAsset(assetId: string, deleteAgent = false) {
  return request<LifecycleActionResult>(`/api/v1/assets/${assetId}`, {
    method: "DELETE",
    body: { delete_agent: deleteAgent }
  });
}
