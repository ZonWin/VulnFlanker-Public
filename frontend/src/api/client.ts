import { t } from "@/app/i18n";
export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(message: string, status: number, detail: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

type QueryValue = string | number | boolean | null | undefined;

export type QueryParams = Record<string, QueryValue>;

export interface RequestOptions extends Omit<RequestInit, "body"> {
  query?: QueryParams;
  body?: unknown;
}

function buildUrl(path: string, query?: QueryParams) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const requestPath = apiBaseUrl
    ? `${apiBaseUrl}${normalizedPath}`
    : normalizedPath;
  const url = new URL(requestPath, window.location.origin);

  Object.entries(query ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  });

  return url.toString();
}

function errorMessage(status: number, detail: unknown) {
  if (
    detail &&
    typeof detail === "object" &&
    "detail" in detail
  ) {
    if (typeof detail.detail === "string") {
      return detail.detail;
    }
    if (
      detail.detail &&
      typeof detail.detail === "object" &&
      "message" in detail.detail &&
      typeof detail.detail.message === "string"
    ) {
      return detail.detail.message;
    }
  }

  return t("请求失败，HTTP {{v0}}", { v0: status });
}

export function getApiErrorCode(error: unknown) {
  if (!(error instanceof ApiError)) {
    return undefined;
  }
  const payload = error.detail;
  if (!payload || typeof payload !== "object" || !("detail" in payload)) {
    return undefined;
  }
  const detail = payload.detail;
  if (!detail || typeof detail !== "object" || !("code" in detail)) {
    return undefined;
  }
  return typeof detail.code === "string" ? detail.code : undefined;
}

export async function request<T>(
  path: string,
  { query, body, headers, ...init }: RequestOptions = {}
): Promise<T> {
  const response = await fetch(buildUrl(path, query), {
    ...init,
    credentials: init.credentials ?? "include",
    headers: {
      Accept: "application/json",
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...headers
    },
    body: body !== undefined ? JSON.stringify(body) : undefined
  });

  const contentType = response.headers.get("content-type") ?? "";
  const data = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    if (
      response.status === 401 &&
      !path.includes("/auth/login") &&
      !path.includes("/auth/me")
    ) {
      window.dispatchEvent(new CustomEvent("vulnflanker:unauthorized"));
    }
    throw new ApiError(errorMessage(response.status, data), response.status, data);
  }

  return data as T;
}
