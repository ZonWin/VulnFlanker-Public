import { request, type QueryParams } from "@/api/client";

export type TeamStatus = "active" | "inactive";
export type PersonStatus = "active" | "inactive";
export type BusinessSystemStatus = "draft" | "active" | "inactive";

export interface TeamSummary {
  id: string;
  code: string;
  name: string;
  status: TeamStatus;
}

export interface ResponsibilityTeam extends TeamSummary {
  description: string | null;
  version: number;
  person_count: number;
  business_system_count: number;
  asset_count: number;
  created_at: string;
  updated_at: string;
}

export interface PersonSummary {
  id: string;
  employee_no: string | null;
  name: string;
  email: string | null;
  status: PersonStatus;
  team: TeamSummary;
}

export interface Person extends PersonSummary {
  phone: string | null;
  user_id: string | null;
  notes: string | null;
  version: number;
  business_system_count: number;
  asset_count: number;
  created_at: string;
  updated_at: string;
}

export interface BusinessSystem {
  id: string;
  code: string;
  name: string;
  description: string | null;
  responsible_person: PersonSummary | null;
  status: BusinessSystemStatus;
  version: number;
  asset_count: number;
  created_at: string;
  updated_at: string;
}

export interface OwnershipSummary {
  team_count: number;
  person_count: number;
  business_system_count: number;
  asset_count: number;
  complete_asset_count: number;
  unassigned_asset_count: number;
  incomplete_asset_count: number;
}

export interface PagedResult<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface TeamQuery extends QueryParams {
  keyword?: string;
  status?: TeamStatus;
  has_members?: boolean;
  page?: number;
  page_size?: number;
  sort_by?: "code" | "name" | "status" | "created_at" | "updated_at";
  sort_order?: "asc" | "desc";
}

export interface PersonQuery extends QueryParams {
  keyword?: string;
  team_id?: string;
  status?: PersonStatus;
  has_email?: boolean;
  has_systems?: boolean;
  page?: number;
  page_size?: number;
  sort_by?: "name" | "employee_no" | "status" | "created_at" | "updated_at";
  sort_order?: "asc" | "desc";
}

export interface BusinessSystemQuery extends QueryParams {
  keyword?: string;
  responsible_person_id?: string;
  team_id?: string;
  status?: BusinessSystemStatus;
  has_assets?: boolean;
  page?: number;
  page_size?: number;
  sort_by?: "code" | "name" | "status" | "created_at" | "updated_at";
  sort_order?: "asc" | "desc";
}

export interface TeamCreate {
  code: string;
  name: string;
  description?: string | null;
}

export interface TeamUpdate {
  expected_version: number;
  name?: string;
  description?: string | null;
}

export interface PersonCreate {
  employee_no?: string | null;
  name: string;
  email?: string | null;
  phone?: string | null;
  team_id: string;
  user_id?: string | null;
  notes?: string | null;
  status?: PersonStatus;
}

export interface PersonUpdate extends Partial<Omit<PersonCreate, "status">> {
  expected_version: number;
}

export interface BusinessSystemCreate {
  code: string;
  name: string;
  description?: string | null;
  responsible_person_id?: string | null;
  status?: "draft" | "active";
}

export interface BusinessSystemUpdate {
  expected_version: number;
  name?: string;
  description?: string | null;
  responsible_person_id?: string | null;
}

export function getResponsibilityTeams(query: TeamQuery = {}) {
  return request<PagedResult<ResponsibilityTeam>>("/api/v1/responsibility-teams", {
    query
  });
}

export function createResponsibilityTeam(payload: TeamCreate) {
  return request<ResponsibilityTeam>("/api/v1/responsibility-teams", {
    method: "POST",
    body: payload
  });
}

export function updateResponsibilityTeam(teamId: string, payload: TeamUpdate) {
  return request<ResponsibilityTeam>(`/api/v1/responsibility-teams/${teamId}`, {
    method: "PATCH",
    body: payload
  });
}

export function setResponsibilityTeamStatus(
  teamId: string,
  action: "activate" | "deactivate",
  expectedVersion: number
) {
  return request<ResponsibilityTeam>(
    `/api/v1/responsibility-teams/${teamId}/${action}`,
    { method: "POST", body: { expected_version: expectedVersion } }
  );
}

export function transferTeamMembers(teamId: string, personIds: string[]) {
  return request<ResponsibilityTeam>(
    `/api/v1/responsibility-teams/${teamId}/transfer-members`,
    { method: "POST", body: { person_ids: personIds } }
  );
}

export function getPeople(query: PersonQuery = {}) {
  return request<PagedResult<Person>>("/api/v1/people", { query });
}

export function createPerson(payload: PersonCreate) {
  return request<Person>("/api/v1/people", { method: "POST", body: payload });
}

export function updatePerson(personId: string, payload: PersonUpdate) {
  return request<Person>(`/api/v1/people/${personId}`, {
    method: "PATCH",
    body: payload
  });
}

export function activatePerson(personId: string, expectedVersion: number) {
  return request<Person>(`/api/v1/people/${personId}/activate`, {
    method: "POST",
    body: { expected_version: expectedVersion }
  });
}

export function deactivatePerson(
  personId: string,
  expectedVersion: number,
  replacementPersonId?: string
) {
  return request<Person>(`/api/v1/people/${personId}/deactivate`, {
    method: "POST",
    body: {
      expected_version: expectedVersion,
      replacement_person_id: replacementPersonId || null
    }
  });
}

export function getBusinessSystems(query: BusinessSystemQuery = {}) {
  return request<PagedResult<BusinessSystem>>("/api/v1/business-systems", { query });
}

export function createBusinessSystem(payload: BusinessSystemCreate) {
  return request<BusinessSystem>("/api/v1/business-systems", {
    method: "POST",
    body: payload
  });
}

export function updateBusinessSystem(systemId: string, payload: BusinessSystemUpdate) {
  return request<BusinessSystem>(`/api/v1/business-systems/${systemId}`, {
    method: "PATCH",
    body: payload
  });
}

export function activateBusinessSystem(systemId: string, expectedVersion: number) {
  return request<BusinessSystem>(`/api/v1/business-systems/${systemId}/activate`, {
    method: "POST",
    body: { expected_version: expectedVersion }
  });
}

export function deactivateBusinessSystem(
  systemId: string,
  payload: {
    expected_version: number;
    replacement_system_id?: string | null;
    unassign_assets?: boolean;
  }
) {
  return request<BusinessSystem>(`/api/v1/business-systems/${systemId}/deactivate`, {
    method: "POST",
    body: payload
  });
}

export function getOwnershipSummary() {
  return request<OwnershipSummary>("/api/v1/ownership/summary");
}
