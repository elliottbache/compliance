import type {
  ArchiveRequest,
  SiteAnalysis,
  SiteAttachmentsOut,
  SiteHistory,
} from "../types";

const DEFAULT_API_BASE_URL = "http://localhost:8000";
const AUTH_TOKEN_STORAGE_KEY = "compliance.authToken";

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL
).replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string, statusText: string) {
    super(`${status}: ${detail || statusText}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

type RecordId = number | string;

type QueryValue = string | number | boolean | null | undefined;

type QueryParams = Record<string, QueryValue>;

type TokenResponse = {
  access_token: string;
  token_type: string;
};

export type AuthCredentials = {
  email: string;
  password: string;
};

type AuthCredentialsProvider = () => Promise<AuthCredentials | null>;

export const ADMIN_RESOURCE_PATHS = {
  sites: "/sites",
  clients: "/clients",
  certifiers: "/certifiers",
  regulations: "/regulations",
  rules: "/rules",
  certifications: "/certifications",
  findings: "/findings",
  attachments: "/attachments",
} as const;

export type AdminResourceKey = keyof typeof ADMIN_RESOURCE_PATHS;

function buildUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
}

function getStoredAuthToken(): string | null {
  return window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
}

function storeAuthToken(token: string): void {
  window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
}

function clearAuthToken(): void {
  window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
}

function encodeRecordId(recordId: RecordId): string {
  return encodeURIComponent(String(recordId));
}

function mergeHeaders(
  defaultHeaders: HeadersInit,
  customHeaders?: HeadersInit,
): Headers {
  const headers = new Headers(defaultHeaders);

  if (customHeaders) {
    new Headers(customHeaders).forEach((value, key) => {
      headers.set(key, value);
    });
  }

  return headers;
}

function buildQueryString(params: QueryParams = {}): string {
  const searchParams = new URLSearchParams();

  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined) {
      continue;
    }

    searchParams.set(key, String(value));
  }

  const queryString = searchParams.toString();
  return queryString ? `?${queryString}` : "";
}

function addAuthHeader(headers: Headers): Headers {
  const token = getStoredAuthToken();

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  return headers;
}

function stringifyDetail(detail: unknown): string {
  if (typeof detail === "string") {
    return detail;
  }

  if (detail === null || detail === undefined) {
    return "";
  }

  try {
    return JSON.stringify(detail);
  } catch {
    return String(detail);
  }
}

async function readErrorDetail(response: Response): Promise<string> {
  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    try {
      const body: { detail?: unknown } = await response.json();
      return stringifyDetail(body.detail);
    } catch {
      return "";
    }
  }

  try {
    return await response.text();
  } catch {
    return "";
  }
}

export async function assertOk(response: Response): Promise<void> {
  if (response.ok) {
    return;
  }

  const detail = await readErrorDetail(response);
  throw new ApiError(response.status, detail, response.statusText);
}

let authRequest: Promise<boolean> | null = null;
let authCredentialsProvider: AuthCredentialsProvider | null = null;

export function setAuthCredentialsProvider(
  provider: AuthCredentialsProvider | null,
): void {
  authCredentialsProvider = provider;
}

async function postAuthToken(email: string, password: string): Promise<TokenResponse> {
  const formData = new URLSearchParams();
  formData.set("username", email);
  formData.set("password", password);

  const response = await fetch(buildUrl("/auth/token"), {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: formData,
  });

  await assertOk(response);
  return response.json() as Promise<TokenResponse>;
}

async function requestAuthToken(): Promise<boolean> {
  if (!authRequest) {
    authRequest = (async () => {
      const credentials = await authCredentialsProvider?.();
      if (!credentials) {
        return false;
      }

      const token = await postAuthToken(credentials.email, credentials.password);
      storeAuthToken(token.access_token);
      return true;
    })().finally(() => {
      authRequest = null;
    });
  }

  return authRequest;
}

async function fetchWithAuthRetry(
  path: string,
  options: RequestInit,
): Promise<Response> {
  const { headers, ...restOptions } = options;
  const requestHeaders = addAuthHeader(new Headers(headers));

  let response = await fetch(buildUrl(path), {
    ...restOptions,
    headers: requestHeaders,
  });

  if (response.status !== 401) {
    return response;
  }

  clearAuthToken();
  const hasToken = await requestAuthToken();
  if (!hasToken) {
    return response;
  }

  const retryHeaders = addAuthHeader(new Headers(headers));
  response = await fetch(buildUrl(path), {
    ...restOptions,
    headers: retryHeaders,
  });

  return response;
}

export async function fetchJson<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const { headers, ...restOptions } = options;

  const response = await fetchWithAuthRetry(path, {
    ...restOptions,
    headers: mergeHeaders(
      {
        Accept: "application/json",
      },
      headers,
    ),
  });

  await assertOk(response);
  return response.json() as Promise<T>;
}


export async function postJson<T>(
  path: string,
  body?: unknown,
  options: RequestInit = {},
): Promise<T> {
  const { headers, ...restOptions } = options;

  return fetchJson<T>(path, {
    ...restOptions,
    method: "POST",
    headers: mergeHeaders(
      {
        "Content-Type": "application/json",
      },
      headers,
    ),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export async function getSiteHistory(siteId: number): Promise<SiteHistory> {
  return fetchJson<SiteHistory>(`/sites/${siteId}/history`);
}

export async function getSiteAttachments(
  siteId: number,
): Promise<SiteAttachmentsOut> {
  return fetchJson<SiteAttachmentsOut>(`/sites/${siteId}/attachments`);
}

export async function createSiteAnalysis(
  siteId: number,
): Promise<SiteAnalysis> {
  return postJson<SiteAnalysis>(`/sites/${siteId}/analysis`);
}

export async function listAdminRecords<T>(
  resourcePath: string,
  options: { includeArchived?: boolean } = {},
): Promise<T[]> {
  const queryString = buildQueryString({
    include_archived: options.includeArchived ? true : undefined,
  });

  return fetchJson<T[]>(`${resourcePath}${queryString}`);
}

export async function createAdminRecord<TPayload, TResponse>(
  resourcePath: string,
  payload: TPayload,
): Promise<TResponse> {
  return postJson<TResponse>(resourcePath, payload);
}

export async function uploadAttachmentFile(
  attachmentId: number,
  file: File,
): Promise<void> {
  const formData = new FormData();
  formData.set("id", String(attachmentId));
  formData.set("file", file);

  const response = await fetchWithAuthRetry("/attachments/upload", {
    method: "POST",
    headers: addAuthHeader(new Headers({ Accept: "application/json" })),
    body: formData,
  });

  await assertOk(response);
}

function getFilenameFromContentDisposition(headerValue: string | null): string | null {
  if (!headerValue) {
    return null;
  }

  const utf8Match = /filename\*=UTF-8''([^;]+)/i.exec(headerValue);
  if (utf8Match) {
    return decodeURIComponent(utf8Match[1].replace(/^"|"$/g, ""));
  }

  const filenameMatch = /filename="?([^";]+)"?/i.exec(headerValue);
  return filenameMatch?.[1] ?? null;
}

function saveBlob(blob: Blob, filename: string): void {
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = objectUrl;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();

  URL.revokeObjectURL(objectUrl);
}

export async function downloadAttachmentFile(attachmentId: number): Promise<void> {
  const response = await fetchWithAuthRetry(
    `/attachments/${encodeRecordId(attachmentId)}/download`,
    {
      headers: {
        Accept: "application/octet-stream",
      },
    },
  );

  await assertOk(response);

  const filename =
    getFilenameFromContentDisposition(response.headers.get("content-disposition")) ??
    `attachment-${attachmentId}`;
  const blob = await response.blob();
  saveBlob(blob, filename);
}

export async function archiveAdminRecord<TResponse>(
  resourcePath: string,
  recordId: RecordId,
  archiveReason?: string,
): Promise<TResponse> {
  const reason = archiveReason?.trim();

  const payload: ArchiveRequest = {
    archive_reason: reason || null,
  };

  return postJson<TResponse>(
    `${resourcePath}/${encodeRecordId(recordId)}/archive`,
    payload,
  );
}

export async function restoreAdminRecord<TResponse>(
  resourcePath: string,
  recordId: RecordId,
): Promise<TResponse> {
  return postJson<TResponse>(
    `${resourcePath}/${encodeRecordId(recordId)}/restore`,
  );
}
